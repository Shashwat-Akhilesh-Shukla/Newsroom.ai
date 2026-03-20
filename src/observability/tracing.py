"""
LangSmith tracing integration for AI Newsroom.

Thin wrapper around the LangSmith SDK that:
- Configures the LangSmith client from environment variables
- Provides context managers / decorators for agent and workflow spans
- Gracefully no-ops when LANGCHAIN_API_KEY is not set
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_tracing_enabled: bool = False
_langsmith_client: Optional[Any] = None   # langsmith.Client if available
_project_name: str = "newsroom-dev"


# ---------------------------------------------------------------------------
# Public setup API
# ---------------------------------------------------------------------------

def setup_tracing(project_name: Optional[str] = None) -> bool:
    """
    Initialise the LangSmith client and enable tracing.

    Must be called once at application startup (before any agents run).
    Reads LANGCHAIN_API_KEY, LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT,
    and LANGCHAIN_ENDPOINT from the environment.

    Args:
        project_name: Override the LangSmith project name.
                      Falls back to $LANGCHAIN_PROJECT or 'newsroom-dev'.

    Returns:
        True  — tracing is active.
        False — key absent or langsmith not installed; tracing silently no-ops.
    """
    global _tracing_enabled, _langsmith_client, _project_name

    _project_name = (
        project_name
        or os.getenv("LANGCHAIN_PROJECT", "newsroom-dev")
    )

    api_key = os.getenv("LANGCHAIN_API_KEY", "")
    tracing_flag = os.getenv("LANGCHAIN_TRACING_V2", "false").lower()

    if not api_key or tracing_flag not in ("true", "1", "yes"):
        logger.info(
            "LangSmith tracing disabled "
            "(set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY to enable)"
        )
        _tracing_enabled = False
        return False

    try:
        from langsmith import Client  # type: ignore

        endpoint = os.getenv(
            "LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"
        )
        _langsmith_client = Client(api_url=endpoint, api_key=api_key)

        # Validate the connection with a lightweight call
        _langsmith_client.list_projects(limit=1)

        _tracing_enabled = True
        logger.info(
            f"LangSmith tracing enabled | project='{_project_name}'"
        )
        return True

    except ImportError:
        logger.warning(
            "langsmith package not installed. "
            "Run: pip install langsmith"
        )
        _tracing_enabled = False
        return False

    except Exception as exc:
        logger.warning(
            f"LangSmith tracing could not be initialised: {exc}. "
            "Continuing without tracing."
        )
        _tracing_enabled = False
        return False


def is_tracing_enabled() -> bool:
    """Return True if LangSmith tracing is active."""
    return _tracing_enabled


def get_langsmith_client() -> Optional[Any]:
    """Return the LangSmith Client instance, or None if tracing is off."""
    return _langsmith_client


# ---------------------------------------------------------------------------
# Shared metadata helpers
# ---------------------------------------------------------------------------

def create_run_metadata(
    agent_name: str,
    state: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the standard metadata dict attached to every agent span.

    Args:
        agent_name: Lowercase agent name (e.g. 'scout').
        state:      Current NewsroomState dict.
        extra:      Any additional key/value pairs to include.

    Returns:
        Metadata dictionary suitable for LangSmith run tags / metadata.
    """
    metadata: Dict[str, Any] = {
        "agent": agent_name,
        "workflow_stage": state.get("workflow_stage", "unknown"),
        "topic": state.get("topic", ""),
        "confidence": state.get("confidence", 0.0),
        "draft_version": state.get("draft_version", 0),
        "revision_count": state.get("revision_count", 0),
        "iteration_counts": state.get("iteration_counts", {}),
        "timestamp": datetime.utcnow().isoformat(),
    }
    if extra:
        metadata.update(extra)
    return metadata


def get_run_url(run_id: str) -> str:
    """
    Return a shareable LangSmith URL for a specific run.

    Args:
        run_id: UUID string of the LangSmith run.

    Returns:
        URL string, or a placeholder if tracing is off.
    """
    if not _tracing_enabled or not run_id:
        return "(LangSmith tracing not enabled)"
    project_encoded = _project_name.replace(" ", "%20")
    return (
        f"https://smith.langchain.com/projects/p/{project_encoded}"
        f"/runs/{run_id}"
    )


# ---------------------------------------------------------------------------
# Context manager for agent-level spans
# ---------------------------------------------------------------------------

@asynccontextmanager
async def trace_agent_execution(
    agent_name: str,
    state: Dict[str, Any],
    run_name: Optional[str] = None,
):
    """
    Async context manager that wraps an agent's process() call in a
    LangSmith span.  Transparently no-ops if tracing is disabled.

    Usage::

        async with trace_agent_execution("scout", state) as run_ctx:
            updated_state = await self.process(state)
            run_ctx["output"] = {"topic": updated_state.get("topic")}

    The caller may set ``run_ctx["output"]`` inside the block to attach
    structured output to the span.

    Yields:
        A mutable dict.  Set ``run_ctx["output"]`` to record run output.
        ``run_ctx["run_id"]`` is populated if tracing is active.
    """
    run_ctx: Dict[str, Any] = {"run_id": None, "output": {}}

    if not _tracing_enabled:
        yield run_ctx
        return

    try:
        from langsmith import traceable  # type: ignore  # noqa: F401
        from langsmith.run_helpers import get_current_run_tree  # type: ignore
    except ImportError:
        yield run_ctx
        return

    metadata = create_run_metadata(agent_name, state)
    invocation_name = run_name or f"agent:{agent_name}"

    # We open a new run manually so we can capture the run_id and attach
    # structured output after the process() call completes.
    client = _langsmith_client
    run_id_str: Optional[str] = None

    try:
        import uuid
        run_id_str = str(uuid.uuid4())
        run_ctx["run_id"] = run_id_str

        if client:
            client.create_run(
                id=run_id_str,
                name=invocation_name,
                run_type="chain",
                inputs={"state_summary": metadata},
                tags=[agent_name, "newsroom", metadata["workflow_stage"]],
                project_name=_project_name,
            )

        yield run_ctx

        # Patch output onto the run after yield
        if client and run_id_str:
            client.update_run(
                run_id_str,
                outputs=run_ctx.get("output", {}),
                end_time=datetime.utcnow(),
            )

    except Exception as exc:
        logger.debug(f"LangSmith span error for {agent_name}: {exc}")
        # Always yield to the caller even if LangSmith fails
        if "output" not in run_ctx:
            yield run_ctx
        # Patch error if we opened a run
        if client and run_id_str:
            try:
                client.update_run(
                    run_id_str,
                    error=str(exc),
                    end_time=datetime.utcnow(),
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Feedback helpers
# ---------------------------------------------------------------------------

def post_error_feedback(run_id: Optional[str], error_message: str) -> None:
    """
    Post a 0-score feedback entry for a failed agent run.

    Args:
        run_id:        LangSmith run UUID (may be None).
        error_message: The exception message to record.
    """
    if not _tracing_enabled or not run_id or not _langsmith_client:
        return
    try:
        _langsmith_client.create_feedback(
            run_id=run_id,
            key="error",
            score=0,
            comment=error_message,
        )
    except Exception as exc:
        logger.debug(f"Failed to post LangSmith error feedback: {exc}")
