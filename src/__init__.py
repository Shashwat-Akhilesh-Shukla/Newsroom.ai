"""AI Newsroom - Multi-Agent Content Creation System."""

__version__ = "0.1.0"

from .state import NewsroomState, create_initial_state
from .graph import create_newsroom_graph
from .main import main

__all__ = [
    "NewsroomState",
    "create_initial_state",
    "create_newsroom_graph",
    "main",
]
