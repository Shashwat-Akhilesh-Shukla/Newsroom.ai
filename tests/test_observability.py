"""
Tests for the LangSmith observability module.

These tests use mocks exclusively — no real LANGCHAIN_API_KEY or network
access is required.  They verify:

1. Tracing initialises (or no-ops) correctly
2. AgentMetrics are collected and costed correctly
3. WorkflowMetrics aggregation is accurate
4. trace_agent_execution context manager handles errors gracefully
5. RunIdFilter injects run_id into log records
6. JsonFormatter produces valid JSON log lines
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the project root is on the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_observability_state():
    """Reset module-level globals between tests."""
    try:
        import src.observability.tracing as t
        t._tracing_enabled = False
        t._langsmith_client = None
        t._project_name = "newsroom-test"
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. setup_tracing — no API key → graceful no-op
# ---------------------------------------------------------------------------

class TestSetupTracingNoKey:
    def setup_method(self):
        _clear_observability_state()

    def test_returns_false_when_no_key(self, monkeypatch):
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

        from src.observability.tracing import setup_tracing, is_tracing_enabled
        result = setup_tracing()

        assert result is False
        assert is_tracing_enabled() is False

    def test_returns_false_when_flag_is_false(self, monkeypatch):
        monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_test_key")
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

        from src.observability.tracing import setup_tracing, is_tracing_enabled
        result = setup_tracing()

        assert result is False
        assert is_tracing_enabled() is False


# ---------------------------------------------------------------------------
# 2. setup_tracing — with valid mock client
# ---------------------------------------------------------------------------

class TestSetupTracingWithMockClient:
    def setup_method(self):
        _clear_observability_state()

    def test_enabled_with_mock_client(self, monkeypatch):
        monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_test_key_abc123")
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_PROJECT", "newsroom-test")

        mock_client = MagicMock()
        mock_client.list_projects.return_value = iter([MagicMock()])

        with patch("src.observability.tracing.Client", return_value=mock_client):
            from src.observability.tracing import setup_tracing, is_tracing_enabled
            result = setup_tracing(project_name="newsroom-test")

        assert result is True
        assert is_tracing_enabled() is True

    def test_graceful_on_client_error(self, monkeypatch):
        """Client raises an exception — should return False, not crash."""
        monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_bad_key")
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")

        bad_client = MagicMock()
        bad_client.list_projects.side_effect = Exception("Connection refused")

        with patch("src.observability.tracing.Client", return_value=bad_client):
            from src.observability.tracing import setup_tracing, is_tracing_enabled
            result = setup_tracing()

        assert result is False
        assert is_tracing_enabled() is False

    def test_graceful_on_import_error(self, monkeypatch):
        """langsmith not installed — should return False."""
        monkeypatch.setenv("LANGCHAIN_API_KEY", "lsv2_test")
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")

        with patch("builtins.__import__", side_effect=ImportError("No module named 'langsmith'")):
            from src.observability import tracing as t
            # Reset so we can re-run setup_tracing
            t._tracing_enabled = False
            t._langsmith_client = None
            # Call directly — it should catch the ImportError
            result = t.setup_tracing()

        assert result is False


# ---------------------------------------------------------------------------
# 3. AgentMetrics — correct cost calculation
# ---------------------------------------------------------------------------

class TestAgentMetrics:
    def test_zero_cost_for_zero_tokens(self):
        from datetime import datetime
        from src.observability.metrics import collect_agent_metrics

        start = datetime(2026, 3, 20, 12, 0, 0)
        end = datetime(2026, 3, 20, 12, 0, 2)  # 2 seconds later

        m = collect_agent_metrics(
            agent_name="scout",
            run_number=1,
            started_at=start,
            ended_at=end,
            routing_decision="researcher",
            confidence_score=0.85,
            token_input=0,
            token_output=0,
        )

        assert m.agent_name == "scout"
        assert m.latency_ms == 2000.0
        assert m.estimated_cost_usd == 0.0
        assert m.routing_decision == "researcher"
        assert m.confidence_score == 0.85

    def test_cost_calculation_gemini_flash(self):
        """1M input + 1M output tokens with gemini-2.0-flash pricing."""
        from datetime import datetime
        from src.observability.metrics import collect_agent_metrics

        start = datetime(2026, 3, 20, 12, 0, 0)
        end = datetime(2026, 3, 20, 12, 0, 1)

        m = collect_agent_metrics(
            agent_name="writer",
            run_number=2,
            started_at=start,
            ended_at=end,
            token_input=1_000_000,
            token_output=1_000_000,
        )

        # $0.075/M input + $0.30/M output = $0.375 total
        assert abs(m.estimated_cost_usd - 0.375) < 1e-6

    def test_to_dict_round_trip(self):
        from datetime import datetime
        from src.observability.metrics import collect_agent_metrics

        start = datetime(2026, 3, 20, 12, 0, 0)
        end = datetime(2026, 3, 20, 12, 0, 5)

        m = collect_agent_metrics(
            agent_name="editor",
            run_number=3,
            started_at=start,
            ended_at=end,
            routing_decision="publisher",
            confidence_score=0.91,
            langsmith_run_id="test-run-uuid",
        )

        d = m.to_dict()
        assert d["agent_name"] == "editor"
        assert d["routing_decision"] == "publisher"
        assert d["langsmith_run_id"] == "test-run-uuid"
        assert isinstance(d["latency_ms"], float)


# ---------------------------------------------------------------------------
# 4. WorkflowMetrics — aggregation
# ---------------------------------------------------------------------------

class TestWorkflowMetrics:
    def test_ingest_multiple_agents(self):
        from datetime import datetime
        from src.observability.metrics import AgentMetrics, WorkflowMetrics

        wm = WorkflowMetrics(run_id="wf-001", topic="Quantum Computing")

        agents_data = [
            ("scout",      100.0, 500,   200,  2),
            ("researcher", 200.0, 1000,  400,  4),
            ("writer",     150.0, 800,   1200, 3),
        ]

        for name, lat, t_in, t_out, calls in agents_data:
            m = AgentMetrics(
                agent_name=name,
                latency_ms=lat,
                token_input=t_in,
                token_output=t_out,
                llm_call_count=calls,
                estimated_cost_usd=(t_in * 0.075 + t_out * 0.30) / 1_000_000,
            )
            wm.ingest_agent_metrics(m)

        assert wm.total_latency_ms == 450.0
        assert wm.total_tokens_in == 2300
        assert wm.total_tokens_out == 1800
        assert wm.total_llm_calls == 9
        assert wm.agent_steps == 3
        assert "scout" in wm.per_agent
        assert "researcher" in wm.per_agent

    def test_to_dict_completeness(self):
        from src.observability.metrics import WorkflowMetrics

        wm = WorkflowMetrics(run_id="wf-002", topic="AI Safety", published=True)
        d = wm.to_dict()

        required_keys = [
            "run_id", "topic", "published", "total_latency_ms",
            "total_tokens_in", "total_tokens_out", "total_cost_usd",
            "agent_steps", "per_agent",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# 5. trace_agent_execution — no-op when tracing disabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTraceAgentExecution:
    async def test_noop_when_disabled(self):
        from src.observability.tracing import trace_agent_execution

        _clear_observability_state()
        state = {"metadata": {}, "workflow_stage": "discovery", "topic": "", "confidence": 0.0,
                 "draft_version": 0, "revision_count": 0, "iteration_counts": {}}

        ran = False
        async with trace_agent_execution("scout", state) as ctx:
            ran = True
            # run_id should be None when tracing is off
            assert ctx["run_id"] is None

        assert ran, "Context manager body was never executed"

    async def test_does_not_raise_on_body_exception(self):
        """Even if the body raises, the context manager should propagate the error cleanly."""
        from src.observability.tracing import trace_agent_execution

        _clear_observability_state()
        state = {"metadata": {}, "workflow_stage": "discovery", "topic": "", "confidence": 0.0,
                 "draft_version": 0, "revision_count": 0, "iteration_counts": {}}

        with pytest.raises(ValueError, match="intentional"):
            async with trace_agent_execution("researcher", state):
                raise ValueError("intentional")


# ---------------------------------------------------------------------------
# 6. RunIdFilter — injects run_id into log records
# ---------------------------------------------------------------------------

class TestRunIdFilter:
    def test_injects_run_id(self):
        from src.utils.logging_config import RunIdFilter

        RunIdFilter.clear_run_id()
        RunIdFilter.set_run_id("test-run-777")

        filt = RunIdFilter()
        record = logging.LogRecord(
            name="newsroom.test",
            level=logging.INFO,
            pathname="test",
            lineno=0,
            msg="Hello",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.run_id == "test-run-777"  # type: ignore[attr-defined]
        RunIdFilter.clear_run_id()

    def test_empty_when_not_set(self):
        from src.utils.logging_config import RunIdFilter

        RunIdFilter.clear_run_id()
        filt = RunIdFilter()
        record = logging.LogRecord(
            name="newsroom.test",
            level=logging.INFO,
            pathname="test",
            lineno=0,
            msg="Hi",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.run_id == ""  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 7. JsonFormatter — produces valid JSON
# ---------------------------------------------------------------------------

class TestJsonFormatter:
    def test_output_is_valid_json(self):
        from src.utils.logging_config import JsonFormatter, RunIdFilter

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="newsroom.agents.scout",
            level=logging.INFO,
            pathname="scout.py",
            lineno=42,
            msg="Scout completed in 2.1s",
            args=(),
            exc_info=None,
        )
        # Simulate RunIdFilter enrichment
        record.run_id = "run-abc"  # type: ignore[attr-defined]

        output = formatter.format(record)
        parsed = json.loads(output)  # Must not raise

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "newsroom.agents.scout"
        assert "Scout completed" in parsed["msg"]
        assert parsed["run_id"] == "run-abc"
        assert "ts" in parsed

    def test_exception_included(self):
        from src.utils.logging_config import JsonFormatter

        formatter = JsonFormatter()
        try:
            raise RuntimeError("Something broke")
        except RuntimeError:
            record = logging.LogRecord(
                name="newsroom.test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
            record.run_id = ""  # type: ignore[attr-defined]
            output = formatter.format(record)
            parsed = json.loads(output)
            assert "exc" in parsed
            assert "RuntimeError" in parsed["exc"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
