"""
System Budget Manager / Editor-in-Chief Agent.

This agent acts as a governor above all other agents. It tracks system metrics
(LLM calls, tokens, cost, time, loops) and enforces budget constraints. It can
intelligently override standard routing decisions when constraints are breached.
"""

import logging
from typing import Dict, Any, Optional, Literal
from datetime import datetime

from .base import BaseAgent
from ..state import NewsroomState
from ..utils.config import get_config

logger = logging.getLogger(__name__)


class ManagerAgent(BaseAgent):
    """
    Editor-in-Chief / Budget Manager Agent.
    
    Responsibilities:
    - Track global system metrics from state["metadata"]["metrics"]
    - Enforce limits: Max loops, Cost threshold, Time elapsed
    - Provide routing overrides to halt the system or alter logic
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Manager agent.
        
        Args:
            config: Optional configuration dictionary
        """
        if config is None:
            # Fallback configuration limits
            config = {
                "max_cost_usd": 0.50,          # Stop system if we spend more than $0.50
                "max_time_seconds": 600,       # 10 minutes total execution time
                "max_scout_loops_overall": 2,  # Stop if Scout rescan hits 2
            }

        super().__init__(name="manager", config=config)

        self.max_cost_usd = config.get("max_cost_usd", 0.50)
        self.max_time_seconds = config.get("max_time_seconds", 600)
        self.max_scout_loops = config.get("max_scout_loops_overall", 2)
        
        # We can dynamically adjust the skeptic stringency
        # Track standard limits
        self.consecutive_skeptic_rejections = 0

    def validate_input(self, state: NewsroomState) -> bool:
        """Manager only depends on generic state attributes to read metrics."""
        return "metadata" in state

    async def process(self, state: NewsroomState) -> NewsroomState:
        """
        The manager doesn't run as a standard node that mutates primary content.
        It evaluates the budget to update overrides directly.
        This won't be called directly in the main sequence, but we satisfy BaseAgent.
        """
        return state

    def get_routing_decision(self, state: NewsroomState) -> str:
        """Returns the fallback next path, though not used primarily in our setup."""
        return "END"

    def evaluate_routing(self, current_agent: str, state: NewsroomState) -> Optional[str]:
        """
        Evaluate if the BudgetManager needs to override the standard routing decision.
        
        Returns:
            The forced routing decision (e.g. "END", "writer", etc.), or None if no override.
        """
        # Calculate totals
        totals = self._calculate_totals(state)
        
        # Rule 1: Overall Budget Exhausted
        if totals["cost_usd"] > self.max_cost_usd:
            self.logger.warning(
                f"BUDGET OVERRIDE: Exploded cost threshold "
                f"(${totals['cost_usd']:.2f} > ${self.max_cost_usd:.2f}). Stopping system."
            )
            state["metadata"]["budget_override"] = "Cost limit exceeded"
            return "END"

        # Rule 2: Max time elapsed
        time_elapsed = totals["time_elapsed_seconds"]
        if time_elapsed > self.max_time_seconds:
            self.logger.warning(
                f"BUDGET OVERRIDE: Max time exceeded "
                f"({time_elapsed:.1f}s > {self.max_time_seconds}s)."
            )
            
            # If we're researching and ran out of time, try publishing whatever we have
            if current_agent == "researcher":
                self.logger.warning("Forcing route to writer due to timeout.")
                state["metadata"]["budget_override"] = "Time limit exceeded -> forced writer"
                return "writer"
                
            state["metadata"]["budget_override"] = "Time limit exceeded"
            return "END"

        # Rule 3: Scout loop exhaustion ("We already tried 2 topics -> stop")
        scout_loops = state.get("iteration_counts", {}).get("scout_loops", 0)
        if current_agent == "scout" and scout_loops >= self.max_scout_loops:
            # We don't want the scout to retry finding a new topic if we tried 2 already
            std_decision = state.get("metadata", {}).get("routing_history", [{}])[-1].get("to")
            # But we evaluate routing BEFORE standard routing, so we just check if it's the 2nd loop
            if scout_loops > self.max_scout_loops:
                self.logger.warning(
                    f"BUDGET OVERRIDE: Max scout loops reached. Stopping system."
                )
                state["metadata"]["budget_override"] = f"Tried {self.max_scout_loops} topics"
                return "END"

        # Rule 4: Skeptic rejection fatigue ("Skeptic too strict -> lower threshold")
        if current_agent == "skeptic":
            # Just observe and adjust threshold if needed (no override of routing usually)
            self._adjust_skeptic_threshold(state)

        return None

    def _calculate_totals(self, state: NewsroomState) -> Dict[str, Any]:
        """Aggregate metrics from state."""
        metrics = state.get("metadata", {}).get("metrics", {})
        
        total_cost = 0.0
        total_tokens = 0
        total_llm_calls = 0

        for agent_name, runs in metrics.items():
            for run in runs:
                total_cost += run.get("estimated_cost_usd", 0.0)
                total_tokens += run.get("token_input", 0) + run.get("token_output", 0)
                total_llm_calls += run.get("llm_call_count", 0)

        created_at_iso = state.get("created_at")
        time_elapsed = 0.0
        if created_at_iso:
            try:
                created_at = datetime.fromisoformat(created_at_iso)
                time_elapsed = (datetime.utcnow() - created_at).total_seconds()
            except ValueError:
                pass

        return {
            "cost_usd": total_cost,
            "tokens": total_tokens,
            "llm_calls": total_llm_calls,
            "time_elapsed_seconds": time_elapsed
        }

    def _adjust_skeptic_threshold(self, state: NewsroomState) -> None:
        """
        Dynamically lower the skeptic threshold if we keep getting rejected.
        """
        # Count recent skeptic rejections
        rejections = 0
        routing_history = state.get("metadata", {}).get("routing_history", [])
        
        for event in reversed(routing_history):
            if event["from"] == "skeptic":
                if event["to"] in ["scout", "researcher"]:
                    rejections += 1
                else:
                    break

        # Let's say if we get 2 rejections in a row, we lower the threshold
        if rejections >= 2:
            current_override = state.get("metadata", {}).get("skeptic_threshold_override")
            new_threshold = current_override - 0.1 if current_override else 0.5
            # Don't go below 0.3
            new_threshold = max(new_threshold, 0.3)
            
            if current_override != new_threshold:
                self.logger.warning(
                    f"BUDGET MANAGER: Skeptic is too strict ({rejections} rejections). "
                    f"Lowering quality threshold to {new_threshold:.2f}."
                )
                state["metadata"]["skeptic_threshold_override"] = new_threshold
