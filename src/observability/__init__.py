"""
Observability module for AI Newsroom.

Provides LangSmith-backed tracing, metrics collection, and evaluation capabilities.

Usage:
    from src.observability import setup_tracing, trace_agent_execution
    from src.observability import AgentMetrics, WorkflowMetrics
    from src.observability import NewsroomEvaluator

    # In main.py — call once at startup
    setup_tracing(project_name="newsroom-prod")
"""

from .tracing import (
    setup_tracing,
    is_tracing_enabled,
    get_run_url,
    trace_agent_execution,
    create_run_metadata,
)
from .metrics import (
    AgentMetrics,
    WorkflowMetrics,
    collect_agent_metrics,
    metrics_to_langsmith_feedback,
)
from .evaluation import NewsroomEvaluator

__all__ = [
    # Tracing
    "setup_tracing",
    "is_tracing_enabled",
    "get_run_url",
    "trace_agent_execution",
    "create_run_metadata",
    # Metrics
    "AgentMetrics",
    "WorkflowMetrics",
    "collect_agent_metrics",
    "metrics_to_langsmith_feedback",
    # Evaluation
    "NewsroomEvaluator",
]
