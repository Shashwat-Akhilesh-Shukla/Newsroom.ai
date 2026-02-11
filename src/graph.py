"""
LangGraph workflow definition for AI Newsroom.

This module defines the complete multi-agent workflow with all routing logic.
"""

import logging
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from .state import NewsroomState, create_initial_state
from .agents.scout import ScoutAgent
from .agents.researcher import ResearcherAgent
from .agents.skeptic import SkepticAgent
from .agents.writer import WriterAgent
from .agents.editor import EditorAgent
from .agents.publisher import PublisherAgent

logger = logging.getLogger(__name__)


# Initialize all agents
scout_agent = ScoutAgent()
researcher_agent = ResearcherAgent()
skeptic_agent = SkepticAgent()
writer_agent = WriterAgent()
editor_agent = EditorAgent()
publisher_agent = PublisherAgent()


def create_newsroom_workflow() -> StateGraph:
    """
    Create the complete newsroom workflow graph.
    
    Returns:
        Compiled LangGraph workflow
    """
    # Create the graph
    workflow = StateGraph(NewsroomState)
    
    # Add all agents as nodes
    workflow.add_node("scout", scout_agent.execute)
    workflow.add_node("researcher", researcher_agent.execute)
    workflow.add_node("skeptic", skeptic_agent.execute)
    workflow.add_node("writer", writer_agent.execute)
    workflow.add_node("editor", editor_agent.execute)
    workflow.add_node("publisher", publisher_agent.execute)
    
    # Add conditional edges with routing functions
    workflow.add_conditional_edges(
        "scout",
        route_scout,
        {
            "researcher": "researcher",
            "scout": "scout",  # Loop back for rescan
            "END": END
        }
    )
    
    workflow.add_conditional_edges(
        "researcher",
        route_researcher,
        {
            "skeptic": "skeptic"
        }
    )
    
    workflow.add_conditional_edges(
        "skeptic",
        route_skeptic,
        {
            "writer": "writer",
            "researcher": "researcher",  # Need more evidence
            "scout": "scout"  # Rejected, find new topic
        }
    )
    
    workflow.add_conditional_edges(
        "writer",
        route_writer,
        {
            "editor": "editor"
        }
    )
    
    workflow.add_conditional_edges(
        "editor",
        route_editor,
        {
            "publisher": "publisher",
            "writer": "writer",  # Rewrite loop
            "researcher": "researcher"  # Fact-check
        }
    )
    
    workflow.add_conditional_edges(
        "publisher",
        route_publisher,
        {
            "END": END,
            "editor": "editor"  # Failed validation
        }
    )
    
    # Set entry point
    workflow.set_entry_point("scout")
    
    # Compile the graph
    app = workflow.compile()
    
    logger.info("Newsroom workflow created successfully")
    
    return app


# Routing functions

def route_scout(state: NewsroomState) -> Literal["researcher", "scout", "END"]:
    """
    Route from Scout agent.
    
    Args:
        state: Current newsroom state
        
    Returns:
        Next node name
    """
    return scout_agent.get_routing_decision(state)


def route_researcher(state: NewsroomState) -> Literal["skeptic"]:
    """
    Route from Researcher agent.
    
    Args:
        state: Current newsroom state
        
    Returns:
        Next node name (always skeptic)
    """
    return researcher_agent.get_routing_decision(state)


def route_skeptic(state: NewsroomState) -> Literal["writer", "researcher", "scout"]:
    """
    Route from Skeptic agent.
    
    Args:
        state: Current newsroom state
        
    Returns:
        Next node name
    """
    return skeptic_agent.get_routing_decision(state)


def route_writer(state: NewsroomState) -> Literal["editor"]:
    """
    Route from Writer agent.
    
    Args:
        state: Current newsroom state
        
    Returns:
        Next node name (always editor)
    """
    return writer_agent.get_routing_decision(state)


def route_editor(state: NewsroomState) -> Literal["publisher", "writer", "researcher"]:
    """
    Route from Editor agent.
    
    Args:
        state: Current newsroom state
        
    Returns:
        Next node name
    """
    return editor_agent.get_routing_decision(state)


def route_publisher(state: NewsroomState) -> Literal["END", "editor"]:
    """
    Route from Publisher agent.
    
    Args:
        state: Current newsroom state
        
    Returns:
        Next node name or END
    """
    return publisher_agent.get_routing_decision(state)


def run_newsroom(initial_state: NewsroomState = None) -> NewsroomState:
    """
    Run the complete newsroom workflow.
    
    Args:
        initial_state: Optional initial state (uses default if None)
        
    Returns:
        Final state after workflow completion
    """
    logger.info("Starting newsroom workflow...")
    
    # Create workflow
    app = create_newsroom_workflow()
    
    # Use provided state or create initial state
    if initial_state is None:
        initial_state = create_initial_state()
    
    # Run the workflow
    try:
        final_state = app.invoke(initial_state)
        
        logger.info("Newsroom workflow completed successfully")
        
        # Log summary
        if final_state.get("publish_ready"):
            logger.info(f"✅ Article published: '{final_state.get('topic')}'")
            logger.info(f"   Word count: {len(final_state.get('draft', '').split())}")
            logger.info(f"   Revisions: {final_state.get('draft_version', 0)}")
        else:
            logger.info(f"❌ Workflow ended without publishing")
            logger.info(f"   Last stage: {final_state.get('workflow_stage', 'unknown')}")
        
        return final_state
        
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise


def stream_newsroom(initial_state: NewsroomState = None):
    """
    Stream the newsroom workflow execution.
    
    Args:
        initial_state: Optional initial state
        
    Yields:
        State updates as the workflow progresses
    """
    logger.info("Starting newsroom workflow (streaming mode)...")
    
    # Create workflow
    app = create_newsroom_workflow()
    
    # Use provided state or create initial state
    if initial_state is None:
        initial_state = create_initial_state()
    
    # Stream the workflow
    try:
        for state in app.stream(initial_state):
            yield state
            
    except Exception as e:
        logger.error(f"Workflow streaming failed: {e}", exc_info=True)
        raise
