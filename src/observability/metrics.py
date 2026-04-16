"""
Structured metrics collection for AI Newsroom agents.

Captures per-agent execution metrics (latency, token usage, cost) and
aggregates them at the workflow level.  Optionally posts scores back
to LangSmith as numeric feedback.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-agent metrics
# ---------------------------------------------------------------------------

@dataclass
class AgentMetrics:
    """
    Execution metrics for a single agent run.

    All fields default to safe zero-values so callers can fill in
    only what they know.
    """
    agent_name: str = ""
    run_number: int = 0
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: str = ""

    # Latency
    latency_ms: float = 0.0

    # LLM usage (summed across all LLM calls within this agent step)
    llm_call_count: int = 0
    token_input: int = 0
    token_output: int = 0
    estimated_cost_usd: float = 0.0

    # Routing
    routing_decision: str = ""

    # Quality signals
    confidence_score: float = 0.0

    # LangSmith correlation
    langsmith_run_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a dict suitable for state["metadata"]["metrics"]."""
        return {
            "agent_name": self.agent_name,
            "run_number": self.run_number,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "latency_ms": round(self.latency_ms, 2),
            "llm_call_count": self.llm_call_count,
            "token_input": self.token_input,
            "token_output": self.token_output,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "routing_decision": self.routing_decision,
            "confidence_score": round(self.confidence_score, 4),
            "langsmith_run_id": self.langsmith_run_id,
        }


# ---------------------------------------------------------------------------
# Workflow-level aggregate
# ---------------------------------------------------------------------------

@dataclass
class WorkflowMetrics:
    """
    Aggregate metrics for a complete newsroom workflow run.
    """
    run_id: str = ""
    topic: str = ""
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: str = ""

    # Totals
    total_latency_ms: float = 0.0
    total_llm_calls: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost_usd: float = 0.0

    # Outcome
    published: bool = False
    agent_steps: int = 0
    revision_loops: int = 0

    # Per-agent breakdown
    per_agent: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def ingest_agent_metrics(self, agent_metrics: AgentMetrics) -> None:
        """Accumulate one agent run into workflow totals."""
        self.total_latency_ms += agent_metrics.latency_ms
        self.total_llm_calls += agent_metrics.llm_call_count
        self.total_tokens_in += agent_metrics.token_input
        self.total_tokens_out += agent_metrics.token_output
        self.total_cost_usd += agent_metrics.estimated_cost_usd
        self.agent_steps += 1

        name = agent_metrics.agent_name
        if name not in self.per_agent:
            self.per_agent[name] = []
        self.per_agent[name].append(agent_metrics.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "topic": self.topic,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "total_latency_s": round(self.total_latency_ms / 1000, 2),
            "total_llm_calls": self.total_llm_calls,
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "published": self.published,
            "agent_steps": self.agent_steps,
            "revision_loops": self.revision_loops,
            "per_agent": self.per_agent,
        }

    def log_summary(self) -> None:
        """Log a human-readable workflow summary at INFO level."""
        logger.info("=" * 60)
        logger.info("WORKFLOW METRICS SUMMARY")
        logger.info(f"  Topic:           {self.topic or 'N/A'}")
        logger.info(f"  Published:       {self.published}")
        logger.info(f"  Total latency:   {self.total_latency_ms / 1000:.1f}s")
        logger.info(f"  Total LLM calls: {self.total_llm_calls}")
        logger.info(f"  Total tokens:    {self.total_tokens_in + self.total_tokens_out:,} "
                    f"(in={self.total_tokens_in:,} / out={self.total_tokens_out:,})")
        logger.info(f"  Est. cost:       ${self.total_cost_usd:.4f} USD")
        logger.info(f"  Agent steps:     {self.agent_steps}")
        logger.info(f"  Revision loops:  {self.revision_loops}")
        logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Collection helper
# ---------------------------------------------------------------------------

def collect_agent_metrics(
    agent_name: str,
    run_number: int,
    started_at: datetime,
    ended_at: datetime,
    routing_decision: str = "",
    confidence_score: float = 0.0,
    llm_call_count: int = 0,
    token_input: int = 0,
    token_output: int = 0,
    langsmith_run_id: Optional[str] = None,
) -> AgentMetrics:
    """
    Build an AgentMetrics instance from raw execution data.

    Cost is estimated automatically using gemini-2.5-flash pricing:
    $0.075 / 1M input tokens, $0.30 / 1M output tokens.
    """
    latency_ms = (ended_at - started_at).total_seconds() * 1000

    # Gemini 2.0 Flash pricing (per token)
    input_cost_per_token = 0.075 / 1_000_000
    output_cost_per_token = 0.30 / 1_000_000
    estimated_cost = (token_input * input_cost_per_token +
                      token_output * output_cost_per_token)

    return AgentMetrics(
        agent_name=agent_name,
        run_number=run_number,
        started_at=started_at.isoformat(),
        ended_at=ended_at.isoformat(),
        latency_ms=latency_ms,
        llm_call_count=llm_call_count,
        token_input=token_input,
        token_output=token_output,
        estimated_cost_usd=estimated_cost,
        routing_decision=routing_decision,
        confidence_score=confidence_score,
        langsmith_run_id=langsmith_run_id,
    )


# ---------------------------------------------------------------------------
# LangSmith feedback bridge
# ---------------------------------------------------------------------------

def metrics_to_langsmith_feedback(
    run_id: str,
    metrics: AgentMetrics,
) -> None:
    """
    Post numeric metric scores as LangSmith feedback entries.

    Each metric becomes a separate feedback record so you can filter,
    sort, and chart them in the LangSmith UI.

    Args:
        run_id:  LangSmith run UUID.
        metrics: Populated AgentMetrics instance.
    """
    try:
        from .tracing import get_langsmith_client, is_tracing_enabled  # type: ignore
    except ImportError:
        return

    if not is_tracing_enabled():
        return

    client = get_langsmith_client()
    if not client or not run_id:
        return

    feedback_pairs = [
        ("latency_s", metrics.latency_ms / 1000.0),
        ("estimated_cost_usd", metrics.estimated_cost_usd),
        ("confidence_score", metrics.confidence_score),
        ("token_total", float(metrics.token_input + metrics.token_output)),
    ]

    for key, score in feedback_pairs:
        # LangSmith limit: [-99999.9999, 99999.9999]
        safe_score = max(-99999.9999, min(99999.9999, score))
        try:
            client.create_feedback(
                run_id=run_id,
                key=key,
                score=safe_score,
                source_info={"agent": metrics.agent_name},
            )
        except Exception as exc:
            logger.debug(f"Failed to post feedback '{key}' to LangSmith: {exc}")
