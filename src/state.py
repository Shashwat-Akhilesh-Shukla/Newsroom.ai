"""
State management for the AI Newsroom multi-agent system.

This module defines the NewsroomState that persists across all agents
and provides utilities for state validation and manipulation.
"""

from typing import TypedDict, List, Dict, Optional, Literal
from datetime import datetime
from enum import Enum


class AgentDecision(str, Enum):
    """Possible routing decisions from agents."""
    # Scout decisions
    PROCEED = "proceed"
    RESCAN = "rescan"
    
    # Skeptic decisions
    APPROVE = "approve"
    REJECT = "reject"
    NEED_MORE_EVIDENCE = "need_more_evidence"
    
    # Editor decisions
    ACCEPT = "accept"
    REWRITE = "rewrite"
    FACT_CHECK = "fact_check"
    
    # Publisher decisions
    PUBLISH = "publish"
    REJECT_PUBLISH = "reject_publish"


class ResearchNote(TypedDict):
    """Structure for research findings."""
    claim: str
    citation: str
    source_url: str
    credibility_score: float
    timestamp: str


class NewsroomState(TypedDict):
    """
    The main state object that persists across all agents.
    
    This is the single source of truth for the entire workflow.
    Each agent reads the full state and mutates only its slice.
    """
    # Topic information
    topic: str
    topic_keywords: List[str]
    confidence: float
    
    # Research data
    research_notes: List[ResearchNote]
    research_summary: str
    
    # Quality control
    critic_feedback: List[str]
    skeptic_decision: Optional[str]
    
    # Content creation
    draft: str
    draft_version: int
    claim_list: List[str]
    
    # Editorial review
    editor_comments: List[str]
    editor_decision: Optional[str]
    revision_count: int
    
    # Publishing
    publish_ready: bool
    publisher_decision: Optional[str]
    seo_metadata: Dict[str, str]
    
    # Workflow metadata
    metadata: Dict[str, any]
    current_agent: str
    workflow_stage: str
    iteration_counts: Dict[str, int]
    budget_manager_decision: Optional[str]
    skeptic_threshold_override: Optional[float]
    
    # Timestamps
    created_at: str
    updated_at: str


def create_initial_state(topic: Optional[str] = None) -> NewsroomState:
    """
    Create a new NewsroomState with default values.
    
    Args:
        topic: Optional initial topic to research
        
    Returns:
        NewsroomState with initialized fields
    """
    now = datetime.utcnow().isoformat()
    
    return NewsroomState(
        # Topic information
        topic=topic or "",
        topic_keywords=[],
        confidence=0.0,
        
        # Research data
        research_notes=[],
        research_summary="",
        
        # Quality control
        critic_feedback=[],
        skeptic_decision=None,
        
        # Content creation
        draft="",
        draft_version=0,
        claim_list=[],
        
        # Editorial review
        editor_comments=[],
        editor_decision=None,
        revision_count=0,
        
        # Publishing
        publish_ready=False,
        publisher_decision=None,
        seo_metadata={},
        
        # Workflow metadata
        metadata={},
        current_agent="scout",
        workflow_stage="discovery",
        iteration_counts={
            "scout_loops": 0,
            "research_loops": 0,
            "revision_loops": 0,
        },
        budget_manager_decision=None,
        skeptic_threshold_override=None,
        
        # Timestamps
        created_at=now,
        updated_at=now,
    )


def update_state_timestamp(state: NewsroomState) -> NewsroomState:
    """Update the state's timestamp."""
    state["updated_at"] = datetime.utcnow().isoformat()
    return state


def validate_state(state: NewsroomState) -> bool:
    """
    Validate that the state has all required fields.
    
    Args:
        state: The state to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "topic", "confidence", "research_notes", "draft",
        "editor_comments", "publish_ready", "metadata",
        "current_agent", "workflow_stage"
    ]
    
    for field in required_fields:
        if field not in state:
            return False
    
    return True


def increment_iteration(state: NewsroomState, loop_name: str) -> NewsroomState:
    """
    Increment an iteration counter and update timestamp.
    
    Args:
        state: Current state
        loop_name: Name of the loop counter to increment
        
    Returns:
        Updated state
    """
    if loop_name in state["iteration_counts"]:
        state["iteration_counts"][loop_name] += 1
    else:
        state["iteration_counts"][loop_name] = 1
    
    return update_state_timestamp(state)


def check_max_iterations(state: NewsroomState, loop_name: str, max_iterations: int) -> bool:
    """
    Check if a loop has exceeded maximum iterations.
    
    Args:
        state: Current state
        loop_name: Name of the loop to check
        max_iterations: Maximum allowed iterations
        
    Returns:
        True if max iterations exceeded, False otherwise
    """
    current_count = state["iteration_counts"].get(loop_name, 0)
    return current_count >= max_iterations


def add_research_note(
    state: NewsroomState,
    claim: str,
    citation: str,
    source_url: str,
    credibility_score: float = 0.8
) -> NewsroomState:
    """
    Add a research note to the state.
    
    Args:
        state: Current state
        claim: The claim or finding
        citation: Citation information
        source_url: URL of the source
        credibility_score: Credibility score (0-1)
        
    Returns:
        Updated state
    """
    note = ResearchNote(
        claim=claim,
        citation=citation,
        source_url=source_url,
        credibility_score=credibility_score,
        timestamp=datetime.utcnow().isoformat()
    )
    
    state["research_notes"].append(note)
    return update_state_timestamp(state)


def get_state_summary(state: NewsroomState) -> str:
    """
    Generate a human-readable summary of the current state.
    
    Args:
        state: Current state
        
    Returns:
        String summary of the state
    """
    return f"""
Newsroom State Summary:
-----------------------
Topic: {state['topic']}
Confidence: {state['confidence']:.2f}
Current Agent: {state['current_agent']}
Workflow Stage: {state['workflow_stage']}
Research Notes: {len(state['research_notes'])}
Draft Version: {state['draft_version']}
Revision Count: {state['revision_count']}
Publish Ready: {state['publish_ready']}
Iterations: {state['iteration_counts']}
Last Updated: {state['updated_at']}
    """.strip()
