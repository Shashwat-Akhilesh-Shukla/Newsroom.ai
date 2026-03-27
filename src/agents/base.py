"""
Base agent class for all AI Newsroom agents.

This module provides the abstract base class that all agents inherit from,
ensuring consistent interfaces and shared functionality.

Observability: Every agent's execute() call is wrapped in a LangSmith
span and produces an AgentMetrics record stored in state["metadata"]["metrics"].
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from ..state import NewsroomState, update_state_timestamp


class BaseAgent(ABC):
    """
    Abstract base class for all newsroom agents.

    All agents must implement:
    - process(): Main agent logic
    - validate_input(): Input validation
    - get_routing_decision(): Determine next agent
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize the base agent.

        Args:
            name: Agent name (e.g., "scout", "researcher")
            config: Configuration dictionary
        """
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"newsroom.agents.{name}")
        self.execution_count = 0

    @abstractmethod
    async def process(self, state: NewsroomState) -> NewsroomState:
        """
        Main processing logic for the agent.

        This is where the agent does its work:
        - Scout: Find trending topics
        - Researcher: Gather information
        - Skeptic: Evaluate quality
        - Writer: Create draft
        - Editor: Review content
        - Publisher: Publish article

        Args:
            state: Current newsroom state

        Returns:
            Updated newsroom state
        """
        pass

    @abstractmethod
    def validate_input(self, state: NewsroomState) -> bool:
        """
        Validate that the state has required fields for this agent.

        Args:
            state: Current newsroom state

        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def get_routing_decision(self, state: NewsroomState) -> str:
        """
        Determine which agent should run next.

        This is the key to LangGraph's conditional routing.
        Each agent decides where to go next based on its output.

        Args:
            state: Current newsroom state

        Returns:
            Name of the next agent or "END"
        """
        pass

    async def execute(self, state: NewsroomState) -> NewsroomState:
        """
        Execute the agent with LangSmith tracing, metrics, and error handling.

        This is the main entry point called by LangGraph.  Every call:
        - Opens a LangSmith child span (no-op if tracing is off)
        - Times the process() call
        - Records AgentMetrics into state["metadata"]["metrics"]
        - Posts error feedback to LangSmith on failure

        Args:
            state: Current newsroom state

        Returns:
            Updated newsroom state

        Raises:
            ValueError: If input validation fails
        """
        self.execution_count += 1
        self.logger.info(f"Executing {self.name} (run #{self.execution_count})")

        # Validate input
        if not self.validate_input(state):
            error_msg = f"{self.name} received invalid state"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        # Update current agent in state
        state["current_agent"] = self.name
        state = update_state_timestamp(state)

        # ------------------------------------------------------------------
        # Import observability (lazy — graceful if not installed)
        # ------------------------------------------------------------------
        try:
            from ..observability.tracing import (
                trace_agent_execution,
                post_error_feedback,
            )
            from ..observability.metrics import (
                collect_agent_metrics,
                metrics_to_langsmith_feedback,
            )
            _obs_available = True
        except Exception:
            _obs_available = False

        start_time = datetime.utcnow()
        langsmith_run_id: Optional[str] = None

        # Reset LLM metrics contextvars for the upcoming agent process logic
        from ..utils.llm_utils import reset_llm_metrics, get_llm_metrics
        reset_llm_metrics()

        if _obs_available:
            # ----------------------------------------------------------------
            # Instrumented path — wrapped in a LangSmith span
            # ----------------------------------------------------------------
            try:
                async with trace_agent_execution(self.name, state) as run_ctx:
                    langsmith_run_id = run_ctx.get("run_id")

                    try:
                        updated_state = await self.process(state)
                    except Exception as exc:
                        post_error_feedback(langsmith_run_id, str(exc))
                        self.logger.error(
                            f"Error in {self.name}: {exc}", exc_info=True
                        )
                        raise

                    end_time = datetime.utcnow()
                    next_agent = self.get_routing_decision(updated_state)

                    # Attach structured output to the LangSmith span
                    run_ctx["output"] = {
                        "topic": updated_state.get("topic", ""),
                        "confidence": updated_state.get("confidence", 0.0),
                        "routing_decision": next_agent,
                        "workflow_stage": updated_state.get("workflow_stage", ""),
                        "draft_version": updated_state.get("draft_version", 0),
                    }

            except Exception:
                # trace_agent_execution itself failed — fall back to bare run
                try:
                    updated_state = await self.process(state)
                except Exception as exc:
                    self.logger.error(
                        f"Error in {self.name}: {exc}", exc_info=True
                    )
                    raise
                end_time = datetime.utcnow()
                next_agent = self.get_routing_decision(updated_state)

        else:
            # ----------------------------------------------------------------
            # Plain path — no tracing
            # ----------------------------------------------------------------
            try:
                updated_state = await self.process(state)
            except Exception as exc:
                self.logger.error(f"Error in {self.name}: {exc}", exc_info=True)
                raise
            end_time = datetime.utcnow()
            next_agent = self.get_routing_decision(updated_state)

        # ------------------------------------------------------------------
        # Collect & store metrics
        # ------------------------------------------------------------------
        duration = (end_time - start_time).total_seconds()
        self.logger.info(f"{self.name} completed in {duration:.2f}s → {next_agent}")

        llm_usage = get_llm_metrics()

        if _obs_available:
            try:
                metrics = collect_agent_metrics(
                    agent_name=self.name,
                    run_number=self.execution_count,
                    started_at=start_time,
                    ended_at=end_time,
                    routing_decision=next_agent,
                    confidence_score=updated_state.get("confidence", 0.0),
                    langsmith_run_id=langsmith_run_id,
                    llm_call_count=llm_usage.get("call_count", 0),
                    token_input=llm_usage.get("prompt_tokens", 0),
                    token_output=llm_usage.get("completion_tokens", 0),
                )
                # Persist metrics inside state for downstream access
                if "metrics" not in updated_state["metadata"]:
                    updated_state["metadata"]["metrics"] = {}
                agent_key = self.name
                if agent_key not in updated_state["metadata"]["metrics"]:
                    updated_state["metadata"]["metrics"][agent_key] = []
                updated_state["metadata"]["metrics"][agent_key].append(
                    metrics.to_dict()
                )
                # Post numeric scores to LangSmith
                if langsmith_run_id:
                    metrics_to_langsmith_feedback(langsmith_run_id, metrics)
            except Exception as exc:
                self.logger.debug(f"Metrics collection failed: {exc}")

        # ------------------------------------------------------------------
        # Record routing history
        # ------------------------------------------------------------------
        if "routing_history" not in updated_state["metadata"]:
            updated_state["metadata"]["routing_history"] = []

        updated_state["metadata"]["routing_history"].append({
            "from": self.name,
            "to": next_agent,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_seconds": duration,
            "langsmith_run_id": langsmith_run_id,
        })

        return updated_state

    def log_decision(self, decision: str, reason: str):
        """
        Log an agent decision with reasoning.

        Args:
            decision: The decision made
            reason: Reasoning behind the decision
        """
        self.logger.info(f"Decision: {decision} | Reason: {reason}")

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value with fallback.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
