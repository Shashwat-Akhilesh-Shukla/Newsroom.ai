"""
Logging configuration for AI Newsroom.

This module sets up structured logging for the entire application, including:
- RunIdFilter: injects the active LangSmith run_id into every log record
- JsonFormatter: optional production formatter for log aggregators
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# ---------------------------------------------------------------------------
# Enrichment: inject LangSmith run_id into every log record
# ---------------------------------------------------------------------------

class RunIdFilter(logging.Filter):
    """
    A logging.Filter that injects the active LangSmith run_id into every
    LogRecord as ``run_id``.  This allows log aggregators (Datadog,
    CloudWatch, etc.) to correlate log lines with LangSmith traces.

    Usage::

        RunIdFilter.set_run_id("abc-123")
        # all subsequent log records will have record.run_id = "abc-123"
    """

    _current_run_id: str = ""

    @classmethod
    def set_run_id(cls, run_id: str) -> None:
        """Set the active workflow run ID (call from graph.py at run start)."""
        cls._current_run_id = run_id

    @classmethod
    def clear_run_id(cls) -> None:
        """Clear the run ID at workflow completion."""
        cls._current_run_id = ""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.run_id = self.__class__._current_run_id  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# Optional: structured JSON formatter for production log aggregators
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Output example::

        {"ts": "2026-03-20T15:01:00", "level": "INFO", "logger": "newsroom.agents.scout",
         "msg": "Scout completed in 2.1s", "run_id": "abc-123"}

    Activate via::

        handler.setFormatter(JsonFormatter())
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "run_id": getattr(record, "run_id", ""),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------

def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    debug: bool = False,
    json_format: bool = False,
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level:   Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file:    Path to log file (optional)
        debug:       Enable debug mode with verbose output
        json_format: Emit JSON-formatted lines instead of human-readable text
                     (useful when running in Docker / feeding into log aggregators)
    """
    # Set level
    level = logging.DEBUG if debug else getattr(logging, log_level.upper())

    run_id_filter = RunIdFilter()

    if json_format:
        formatter = JsonFormatter()
    else:
        # Create human-readable formatters
        detailed_formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        simple_formatter = logging.Formatter(
            fmt='%(levelname)-8s | %(name)s | %(message)s'
        )
        formatter = simple_formatter if not debug else detailed_formatter

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(run_id_filter)

    # File handler (if log file specified)
    handlers = [console_handler]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(
            JsonFormatter() if json_format else logging.Formatter(
                fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
        file_handler.addFilter(run_id_filter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True
    )

    # Set levels for specific loggers
    logging.getLogger("newsroom").setLevel(level)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("langsmith").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialised | level={log_level} | debug={debug} | json={json_format}")

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
