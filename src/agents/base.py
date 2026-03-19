"""
Base agent class for all AI Newsroom agents.

This module provides the abstract base class that all agents inherit from,
ensuring consistent interfaces and shared functionality.
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
        Execute the agent with logging and error handling.
        
        This is the main entry point called by the graph.
        
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
        
        try:
            # Process the state
            start_time = datetime.utcnow()
            updated_state = await self.process(state)
            end_time = datetime.utcnow()
            
            # Log execution time
            duration = (end_time - start_time).total_seconds()
            self.logger.info(f"{self.name} completed in {duration:.2f}s")
            
            # Get routing decision
            next_agent = self.get_routing_decision(updated_state)
            self.logger.info(f"{self.name} routing to: {next_agent}")
            
            # Store routing decision in metadata
            if "routing_history" not in updated_state["metadata"]:
                updated_state["metadata"]["routing_history"] = []
            
            updated_state["metadata"]["routing_history"].append({
                "from": self.name,
                "to": next_agent,
                "timestamp": datetime.utcnow().isoformat(),
                "duration_seconds": duration
            })
            
            return updated_state
            
        except Exception as e:
            self.logger.error(f"Error in {self.name}: {str(e)}", exc_info=True)
            raise
    
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
