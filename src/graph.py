"""
LangGraph workflow definition for AI Newsroom.

This module defines the complete multi-agent workflow with all routing logic.
Every execution is wrapped in a LangSmith root span so all agent sub-spans
nest under a single traceable tree in the LangSmith UI.
"""

import logging
import uuid
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
            "skeptic": "skeptic",
            "researcher": "researcher"  # Retry when 0 notes produced
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
            "END_PUBLISHED": END,   # PUBLISHER_PASS — article published
            "END_KILLED": END,      # EDITORIAL_VETO — article killed
            "editor": "editor"      # PUBLISHER_FAIL — back to editor
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


def route_researcher(state: NewsroomState) -> Literal["skeptic", "researcher"]:
    """
    Route from Researcher agent.

    Args:
        state: Current newsroom state

    Returns:
        'skeptic' normally, 'researcher' to retry when 0 notes produced
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


def route_publisher(state: NewsroomState) -> Literal["END_PUBLISHED", "END_KILLED", "editor"]:
    """
    Route from Publisher agent.

    Returns:
        'END_PUBLISHED' on success, 'END_KILLED' on editorial veto,
        'editor' on soft publishing failure
    """
    return publisher_agent.get_routing_decision(state)


async def run_newsroom(initial_state: NewsroomState = None) -> NewsroomState:
    """
    Run the complete newsroom workflow.

    This is the root LangSmith span — all agent sub-spans nest under it,
    forming a complete trace tree visible in the LangSmith UI.

    Args:
        initial_state: Optional initial state (uses default if None)

    Returns:
        Final state after workflow completion
    """
    logger.info("Starting newsroom workflow...")

    # Assign a run ID for cross-system correlation
    run_id = str(uuid.uuid4())

    # Create workflow
    app = create_newsroom_workflow()

    # Use provided state or create initial state
    if initial_state is None:
        initial_state = create_initial_state()

    # Store run_id in state so agents can reference this workflow run
    initial_state["metadata"]["langsmith_run_id"] = run_id
    initial_state["metadata"]["workflow_run_id"] = run_id

    # Resolve LangSmith trace URL (no-op if tracing is disabled)
    try:
        from .observability.tracing import get_run_url, is_tracing_enabled
        if is_tracing_enabled():
            trace_url = get_run_url(run_id)
            logger.info(f"🔍 LangSmith trace: {trace_url}")
    except Exception:
        pass

    # Run the workflow
    try:
        final_state = await app.ainvoke(initial_state)

        logger.info("Newsroom workflow completed successfully")

        # Log outcome
        if final_state.get("publish_ready"):
            logger.info(f"✅ Article published: '{final_state.get('topic')}'")
            logger.info(f"   Word count: {len(final_state.get('draft', '').split())}")
            logger.info(f"   Revisions: {final_state.get('draft_version', 0)}")
        else:
            logger.info(f"❌ Workflow ended without publishing")
            logger.info(f"   Last stage: {final_state.get('workflow_stage', 'unknown')}")

        # Log workflow metrics summary if available
        try:
            from .observability.metrics import WorkflowMetrics
            wm = WorkflowMetrics(
                run_id=run_id,
                topic=final_state.get("topic", ""),
                published=final_state.get("publish_ready", False),
                revision_loops=final_state.get("revision_count", 0),
            )
            # Ingest per-agent metrics stored in state
            from .observability.metrics import AgentMetrics
            from .observability.metrics import collect_agent_metrics
            for agent_name, runs in final_state.get("metadata", {}).get("metrics", {}).items():
                for run_data in runs:
                    from datetime import datetime
                    m = AgentMetrics(
                        agent_name=run_data.get("agent_name", agent_name),
                        latency_ms=run_data.get("latency_ms", 0),
                        token_input=run_data.get("token_input", 0),
                        token_output=run_data.get("token_output", 0),
                        estimated_cost_usd=run_data.get("estimated_cost_usd", 0),
                        llm_call_count=run_data.get("llm_call_count", 0),
                    )
                    wm.ingest_agent_metrics(m)
            wm.log_summary()
        except Exception:
            pass

        return final_state

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise


async def stream_newsroom(initial_state: NewsroomState = None):
    """
    Stream the newsroom workflow execution.

    Args:
        initial_state: Optional initial state

    Yields:
        State updates as the workflow progresses
    """
    logger.info("Starting newsroom workflow (streaming mode)...")

    run_id = str(uuid.uuid4())

    # Create workflow
    app = create_newsroom_workflow()

    # Use provided state or create initial state
    if initial_state is None:
        initial_state = create_initial_state()

    initial_state["metadata"]["langsmith_run_id"] = run_id
    initial_state["metadata"]["workflow_run_id"] = run_id

    try:
        from .observability.tracing import get_run_url, is_tracing_enabled
        if is_tracing_enabled():
            trace_url = get_run_url(run_id)
            logger.info(f"🔍 LangSmith trace: {trace_url}")
    except Exception:
        pass

    # Stream the workflow
    try:
        async for state in app.astream(initial_state):
            yield state

    except Exception as e:
        logger.error(f"Workflow streaming failed: {e}", exc_info=True)
        raise
