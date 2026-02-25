"""
Logging configuration for AI Newsroom.

This module sets up structured logging for the entire application.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    debug: bool = False
) -> None:
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        debug: Enable debug mode with verbose output
    """
    # Set level
    level = logging.DEBUG if debug else getattr(logging, log_level.upper())
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(levelname)-8s | %(name)s | %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_formatter if not debug else detailed_formatter)
    
    # File handler (if log file specified)
    handlers = [console_handler]
    
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(detailed_formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Set levels for specific loggers
    logging.getLogger("newsroom").setLevel(level)
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized | Level: {log_level} | Debug: {debug}")
    
    if log_file:
        logger.info(f"Logging to file: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class AgentLogger:
    """Specialized logger for agents with structured output."""
    
    def __init__(self, agent_name: str):
        """
        Initialize agent logger.
        
        Args:
            agent_name: Name of the agent
        """
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"newsroom.agents.{agent_name}")
    
    def log_execution_start(self, run_number: int):
        """Log agent execution start."""
        self.logger.info(f"[{self.agent_name.upper()}] Starting execution #{run_number}")
    
    def log_execution_end(self, run_number: int, duration: float):
        """Log agent execution end."""
        self.logger.info(
            f"[{self.agent_name.upper()}] Completed execution #{run_number} "
            f"in {duration:.2f}s"
        )
    
    def log_decision(self, decision: str, reason: str):
        """Log agent decision."""
        self.logger.info(
            f"[{self.agent_name.upper()}] Decision: {decision} | Reason: {reason}"
        )
    
    def log_state_update(self, field: str, value: any):
        """Log state update."""
        self.logger.debug(
            f"[{self.agent_name.upper()}] Updated state.{field} = {value}"
        )
    
    def log_error(self, error: str, exc_info: bool = True):
        """Log error."""
        self.logger.error(
            f"[{self.agent_name.upper()}] Error: {error}",
            exc_info=exc_info
        )
