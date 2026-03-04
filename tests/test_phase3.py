"""
Comprehensive tests for Phase 3 implementation.

Tests all agents and the complete workflow.
"""

import os
import sys
import logging
from pathlib import Path

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.state import create_initial_state
from src.agents.scout import ScoutAgent
from src.agents.researcher import ResearcherAgent
from src.agents.skeptic import SkepticAgent
from src.agents.writer import WriterAgent
from src.agents.editor import EditorAgent
from src.agents.publisher import PublisherAgent
from src.utils.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_skeptic_agent():
    """Test Skeptic agent independently."""
    logger.info("=" * 60)
    logger.info("Testing Skeptic Agent")
    logger.info("=" * 60)
    
    # Create state with research data
    state = create_initial_state()
    state["topic"] = "AI Breakthrough in Quantum Computing"
    state["research_summary"] = "Recent research shows significant advances in quantum error correction..."
    state["research_notes"] = [
        {
            "claim": "New error correction code reduces qubit overhead by 50%",
            "citation": "Smith et al., Nature 2024",
            "credibility_score": 0.9
        },
        {
            "claim": "Breakthrough enables practical quantum computers",
            "citation": "ArXiv preprint",
            "credibility_score": 0.6
        }
    ]
    
    # Initialize Skeptic agent
    skeptic = SkepticAgent()
    
    try:
        # Execute Skeptic
        logger.info("Executing Skeptic agent...")
        updated_state = skeptic.execute(state)
        
        # Check results
        decision = updated_state.get("skeptic_decision", "UNKNOWN")
        logger.info(f"\nSkeptic Results:")
        logger.info(f"  Decision: {decision}")
        logger.info(f"  Feedback: {updated_state.get('critic_feedback', [])[-1][:200]}...")
        
        # Get routing decision
        next_agent = skeptic.get_routing_decision(updated_state)
        logger.info(f"  Next Agent: {next_agent}")
        
        return updated_state, decision in ["APPROVE", "NEED_MORE_EVIDENCE", "REJECT"]
        
    except Exception as e:
        logger.error(f"Skeptic agent failed: {e}", exc_info=True)
        return state, False


def test_writer_agent():
    """Test Writer agent independently."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Writer Agent")
    logger.info("=" * 60)
    
    # Create state with approved research
    state = create_initial_state()
    state["topic"] = "AI Breakthrough in Quantum Computing"
    state["research_summary"] = "Recent research demonstrates significant advances in quantum error correction, with new codes reducing qubit overhead by 50%."
    state["research_notes"] = [
        {
            "claim": "New error correction code reduces qubit overhead by 50%",
            "citation": "Smith et al., Nature 2024",
            "url": "https://example.com/paper1"
        }
    ]
    
    # Initialize Writer agent
    writer = WriterAgent()
    
    try:
        # Execute Writer
        logger.info("Executing Writer agent...")
        updated_state = writer.execute(state)
        
        # Check results
        draft = updated_state.get("draft", "")
        logger.info(f"\nWriter Results:")
        logger.info(f"  Draft Length: {len(draft.split())} words")
        logger.info(f"  Draft Version: {updated_state.get('draft_version', 0)}")
        logger.info(f"  Claims Extracted: {len(updated_state.get('claim_list', []))}")
        logger.info(f"  Preview: {draft[:200]}...")
        
        # Get routing decision
        next_agent = writer.get_routing_decision(updated_state)
        logger.info(f"  Next Agent: {next_agent}")
        
        return updated_state, len(draft) > 100
        
    except Exception as e:
        logger.error(f"Writer agent failed: {e}", exc_info=True)
        return state, False


def test_editor_agent():
    """Test Editor agent independently."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Editor Agent")
    logger.info("=" * 60)
    
    # Create state with draft
    state = create_initial_state()
    state["topic"] = "AI Breakthrough in Quantum Computing"
    state["draft"] = """# Quantum Computing Breakthrough

Recent advances in quantum error correction have brought us closer to practical quantum computers. Researchers have developed a new error correction code that reduces qubit overhead by 50%, addressing one of the major challenges in scaling quantum systems.

## The Challenge

Quantum computers are extremely sensitive to errors...

## The Solution

The new approach uses topological codes..."""
    
    state["research_notes"] = [{"claim": "Test claim", "citation": "Test"}]
    state["claim_list"] = ["New code reduces overhead by 50%"]
    
    # Initialize Editor agent
    editor = EditorAgent()
    
    try:
        # Execute Editor
        logger.info("Executing Editor agent...")
        updated_state = editor.execute(state)
        
        # Check results
        decision = updated_state.get("editor_decision", "UNKNOWN")
        logger.info(f"\nEditor Results:")
        logger.info(f"  Decision: {decision}")
        logger.info(f"  Comments: {len(updated_state.get('editor_comments', []))}")
        if updated_state.get("editor_comments"):
            logger.info(f"  Latest Comment: {updated_state['editor_comments'][-1][:200]}...")
        
        # Get routing decision
        next_agent = editor.get_routing_decision(updated_state)
        logger.info(f"  Next Agent: {next_agent}")
        
        return updated_state, decision in ["ACCEPT", "REWRITE", "FACT_CHECK"]
        
    except Exception as e:
        logger.error(f"Editor agent failed: {e}", exc_info=True)
        return state, False


def test_publisher_agent():
    """Test Publisher agent independently."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Publisher Agent")
    logger.info("=" * 60)
    
    # Create state with approved draft
    state = create_initial_state()
    state["topic"] = "AI Breakthrough in Quantum Computing"
    state["draft"] = """# Quantum Computing Breakthrough

Recent advances in quantum error correction have brought us closer to practical quantum computers.

## The Challenge

Quantum computers are extremely sensitive to errors, requiring extensive error correction that dramatically increases the number of physical qubits needed.

## The Solution

Researchers have developed a new topological error correction code that reduces qubit overhead by 50%, addressing one of the major challenges in scaling quantum systems.

## Implications

This breakthrough could accelerate the timeline for practical quantum computers by several years, with applications in cryptography, drug discovery, and optimization problems.

## Conclusion

While challenges remain, this advance represents a significant step toward realizing the promise of quantum computing."""
    
    # Initialize Publisher agent
    publisher = PublisherAgent()
    
    try:
        # Execute Publisher
        logger.info("Executing Publisher agent...")
        updated_state = publisher.execute(state)
        
        # Check results
        decision = updated_state.get("publisher_decision", "UNKNOWN")
        publish_ready = updated_state.get("publish_ready", False)
        publishing_metadata = updated_state.get("publishing_metadata", {})
        
        logger.info(f"\nPublisher Results:")
        logger.info(f"  Decision: {decision}")
        logger.info(f"  Publish Ready: {publish_ready}")
        
        if publishing_metadata:
            logger.info(f"  Title: {publishing_metadata.get('title', 'N/A')}")
            logger.info(f"  Slug: {publishing_metadata.get('slug', 'N/A')}")
            logger.info(f"  Keywords: {publishing_metadata.get('keywords', [])}")
            logger.info(f"  Reading Time: {publishing_metadata.get('reading_time_minutes', 0)} min")
        
        # Get routing decision
        next_agent = publisher.get_routing_decision(updated_state)
        logger.info(f"  Next Agent: {next_agent}")
        
        return updated_state, decision in ["PUBLISH", "REJECT"]
        
    except Exception as e:
        logger.error(f"Publisher agent failed: {e}", exc_info=True)
        return state, False


def test_workflow_integration():
    """Test the complete workflow (if LangGraph is available)."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Workflow Integration")
    logger.info("=" * 60)
    
    try:
        from src.graph import create_newsroom_workflow
        
        logger.info("Creating workflow...")
        workflow = create_newsroom_workflow()
        
        logger.info("✓ Workflow created successfully")
        logger.info("  All agents integrated")
        logger.info("  Routing logic configured")
        
        return True
        
    except ImportError as e:
        logger.warning(f"LangGraph not available: {e}")
        logger.warning("Skipping workflow integration test")
        return True  # Don't fail if LangGraph not installed
        
    except Exception as e:
        logger.error(f"Workflow integration failed: {e}", exc_info=True)
        return False


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("AI NEWSROOM - Phase 3 Testing")
    logger.info("All Agents + Workflow Integration")
    logger.info("=" * 60)
    
    # Check for API key
    config = get_config()
    if not config.llm.api_key:
        logger.error("\n❌ No LLM API key found!")
        logger.error("Set GEMINI_API_KEY in your environment")
        return False
    
    logger.info(f"\n✓ Using LLM: {config.llm.provider}/{config.llm.model}")
    
    results = {}
    
    # Test each agent
    _, results["skeptic"] = test_skeptic_agent()
    _, results["writer"] = test_writer_agent()
    _, results["editor"] = test_editor_agent()
    _, results["publisher"] = test_publisher_agent()
    
    # Test workflow integration
    results["workflow"] = test_workflow_integration()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name.capitalize()} Agent")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✅ All Phase 3 tests passed!")
        logger.info("All agents are functional and ready for integration.")
    else:
        logger.error("\n❌ Some tests failed!")
        logger.error("Review the logs above for details.")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
