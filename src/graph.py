"""
LangGraph workflow definition for the AI Newsroom.

This module defines the complete multi-agent workflow using LangGraph,
including all nodes, edges, and routing logic.
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import NewsroomState, AgentDecision
from .utils.logging_config import get_logger

logger = get_logger(__name__)


def create_newsroom_graph():
    """
    Create the LangGraph workflow for the AI Newsroom.
    
    This graph has CYCLES - it's not a DAG!
    Agents can loop back based on quality gates and feedback.
    
    Returns:
        Compiled StateGraph
    """
    # Create graph with state
    workflow = StateGraph(NewsroomState)
    
    # Add nodes (agents will be added in later phases)
    # For now, we'll add placeholder nodes
    workflow.add_node("scout", scout_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("skeptic", skeptic_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("publisher", publisher_node)
    
    # Set entry point
    workflow.set_entry_point("scout")
    
    # Add conditional edges (routing logic)
    
    # Scout routing
    workflow.add_conditional_edges(
        "scout",
        route_from_scout,
        {
            "researcher": "researcher",  # High confidence
            "scout": "scout",  # Low confidence, rescan
        }
    )
    
    # Researcher always goes to Skeptic
    workflow.add_edge("researcher", "skeptic")
    
    # Skeptic routing (creates first major feedback loop)
    workflow.add_conditional_edges(
        "skeptic",
        route_from_skeptic,
        {
            "writer": "writer",  # APPROVE
            "scout": "scout",  # REJECT
            "researcher": "researcher",  # NEED_MORE_EVIDENCE
        }
    )
    
    # Writer always goes to Editor
    workflow.add_edge("writer", "editor")
    
    # Editor routing (creates revision loop)
    workflow.add_conditional_edges(
        "editor",
        route_from_editor,
        {
            "publisher": "publisher",  # ACCEPT
            "writer": "writer",  # REWRITE
            "researcher": "researcher",  # FACT_CHECK
        }
    )
    
    # Publisher routing (final gate)
    workflow.add_conditional_edges(
        "publisher",
        route_from_publisher,
        {
            END: END,  # PUBLISH
            "editor": "editor",  # REJECT
        }
    )
    
    # Compile with checkpointing for state persistence
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# Placeholder node functions (will be replaced with actual agents in later phases)

def scout_node(state: NewsroomState) -> NewsroomState:
    """Scout agent node (placeholder)."""
    logger.info("Scout node executing (placeholder)")
    state["current_agent"] = "scout"
    # Placeholder: Set a default confidence
    if state["confidence"] == 0.0:
        state["confidence"] = 0.8  # Placeholder value
    return state


def researcher_node(state: NewsroomState) -> NewsroomState:
    """Researcher agent node (placeholder)."""
    logger.info("Researcher node executing (placeholder)")
    state["current_agent"] = "researcher"
    return state


def skeptic_node(state: NewsroomState) -> NewsroomState:
    """Skeptic agent node (placeholder)."""
    logger.info("Skeptic node executing (placeholder)")
    state["current_agent"] = "skeptic"
    # Placeholder: Default to APPROVE
    state["skeptic_decision"] = AgentDecision.APPROVE.value
    return state


def writer_node(state: NewsroomState) -> NewsroomState:
    """Writer agent node (placeholder)."""
    logger.info("Writer node executing (placeholder)")
    state["current_agent"] = "writer"
    return state


def editor_node(state: NewsroomState) -> NewsroomState:
    """Editor agent node (placeholder)."""
    logger.info("Editor node executing (placeholder)")
    state["current_agent"] = "editor"
    # Placeholder: Default to ACCEPT
    state["editor_decision"] = AgentDecision.ACCEPT.value
    return state


def publisher_node(state: NewsroomState) -> NewsroomState:
    """Publisher agent node (placeholder)."""
    logger.info("Publisher node executing (placeholder)")
    state["current_agent"] = "publisher"
    state["publish_ready"] = True
    return state


# Routing functions

def route_from_scout(state: NewsroomState) -> Literal["researcher", "scout"]:
    """
    Route from Scout based on confidence.
    
    Args:
        state: Current state
        
    Returns:
        Next node name
    """
    from .utils.config import get_config
    config = get_config()
    threshold = config.get("scout_confidence_threshold", 0.7)
    
    if state["confidence"] >= threshold:
        logger.info(f"Scout confidence {state['confidence']:.2f} >= {threshold}, routing to researcher")
        return "researcher"
    else:
        logger.info(f"Scout confidence {state['confidence']:.2f} < {threshold}, rescanning")
        return "scout"


def route_from_skeptic(state: NewsroomState) -> Literal["writer", "scout", "researcher"]:
    """
    Route from Skeptic based on decision.
    
    Args:
        state: Current state
        
    Returns:
        Next node name
    """
    decision = state.get("skeptic_decision", AgentDecision.APPROVE.value)
    
    if decision == AgentDecision.APPROVE.value:
        logger.info("Skeptic APPROVED, routing to writer")
        return "writer"
    elif decision == AgentDecision.REJECT.value:
        logger.info("Skeptic REJECTED, routing back to scout")
        return "scout"
    else:  # NEED_MORE_EVIDENCE
        logger.info("Skeptic needs MORE EVIDENCE, routing to researcher")
        return "researcher"


def route_from_editor(state: NewsroomState) -> Literal["publisher", "writer", "researcher"]:
    """
    Route from Editor based on decision.
    
    Args:
        state: Current state
        
    Returns:
        Next node name
    """
    decision = state.get("editor_decision", AgentDecision.ACCEPT.value)
    
    if decision == AgentDecision.ACCEPT.value:
        logger.info("Editor ACCEPTED, routing to publisher")
        return "publisher"
    elif decision == AgentDecision.REWRITE.value:
        logger.info("Editor requested REWRITE, routing back to writer")
        return "writer"
    else:  # FACT_CHECK
        logger.info("Editor requested FACT_CHECK, routing to researcher")
        return "researcher"


def route_from_publisher(state: NewsroomState) -> Literal["__end__", "editor"]:
    """
    Route from Publisher based on decision.
    
    Args:
        state: Current state
        
    Returns:
        Next node name or END
    """
    if state.get("publish_ready", False):
        logger.info("Publisher APPROVED, ending workflow")
        return END
    else:
        logger.info("Publisher REJECTED, routing back to editor")
        return "editor"
