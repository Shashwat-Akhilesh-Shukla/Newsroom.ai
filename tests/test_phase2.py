"""
Simple test script to verify Scout → Researcher flow.

This script tests the Phase 2 implementation without requiring
a full LangGraph setup.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.state import create_initial_state
from src.agents.scout import ScoutAgent
from src.agents.researcher import ResearcherAgent
from src.utils.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_scout_agent():
    """Test Scout agent independently."""
    logger.info("=" * 60)
    logger.info("Testing Scout Agent")
    logger.info("=" * 60)
    
    # Create initial state
    state = create_initial_state()
    
    # Initialize Scout agent
    scout = ScoutAgent()
    
    try:
        # Execute Scout
        logger.info("Executing Scout agent...")
        updated_state = scout.execute(state)
        
        # Check results
        logger.info(f"\nScout Results:")
        logger.info(f"  Topic: {updated_state.get('topic', 'None')}")
        logger.info(f"  Confidence: {updated_state.get('confidence', 0):.2f}")
        logger.info(f"  Keywords: {updated_state.get('topic_keywords', [])}")
        
        # Get routing decision
        next_agent = scout.get_routing_decision(updated_state)
        logger.info(f"  Next Agent: {next_agent}")
        
        return updated_state, next_agent == "researcher"
        
    except Exception as e:
        logger.error(f"Scout agent failed: {e}", exc_info=True)
        return state, False


def test_researcher_agent(state):
    """Test Researcher agent with Scout output."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Researcher Agent")
    logger.info("=" * 60)
    
    # Initialize Researcher agent
    researcher = ResearcherAgent()
    
    try:
        # Execute Researcher
        logger.info("Executing Researcher agent...")
        updated_state = researcher.execute(state)
        
        # Check results
        logger.info(f"\nResearcher Results:")
        logger.info(f"  Research Notes: {len(updated_state.get('research_notes', []))}")
        logger.info(f"  Research Summary: {updated_state.get('research_summary', 'None')[:200]}...")
        
        # Get routing decision
        next_agent = researcher.get_routing_decision(updated_state)
        logger.info(f"  Next Agent: {next_agent}")
        
        return updated_state, next_agent == "skeptic"
        
    except Exception as e:
        logger.error(f"Researcher agent failed: {e}", exc_info=True)
        return state, False


def test_api_clients():
    """Test API clients independently."""
    logger.info("=" * 60)
    logger.info("Testing API Clients")
    logger.info("=" * 60)
    
    from src.utils.api_clients import HackerNewsClient, ArXivClient, GoogleTrendsClient
    
    # Test Hacker News
    logger.info("\nTesting Hacker News API...")
    hn_client = HackerNewsClient()
    try:
        topics = hn_client.get_trending_topics(limit=5)
        logger.info(f"  ✓ Fetched {len(topics)} topics from Hacker News")
        if topics:
            logger.info(f"  Sample: {topics[0].get('title', 'N/A')}")
    except Exception as e:
        logger.error(f"  ✗ Hacker News failed: {e}")
    
    # Test ArXiv
    logger.info("\nTesting ArXiv API...")
    arxiv_client = ArXivClient()
    try:
        papers = arxiv_client.search_papers("machine learning", max_results=3)
        logger.info(f"  ✓ Fetched {len(papers)} papers from ArXiv")
        if papers:
            logger.info(f"  Sample: {papers[0].get('title', 'N/A')}")
    except Exception as e:
        logger.error(f"  ✗ ArXiv failed: {e}")
    
    # Test Google Trends
    logger.info("\nTesting Google Trends API...")
    trends_client = GoogleTrendsClient()
    if trends_client.available:
        try:
            trends = trends_client.get_trending_searches()
            logger.info(f"  ✓ Fetched {len(trends)} trends from Google")
            if trends:
                logger.info(f"  Sample: {trends[0].get('keyword', 'N/A')}")
        except Exception as e:
            logger.error(f"  ✗ Google Trends failed: {e}")
    else:
        logger.warning("  ⚠ Google Trends not available (pytrends not installed)")


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("AI NEWSROOM - Phase 2 Testing")
    logger.info("Scout & Researcher Agents")
    logger.info("=" * 60)
    
    # Check for API key
    config = get_config()
    if not config.llm.api_key:
        logger.error("\n❌ No LLM API key found!")
        logger.error("Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your environment")
        logger.error("Example: export OPENAI_API_KEY='your-key-here'")
        return False
    
    logger.info(f"\n✓ Using LLM: {config.llm.provider}/{config.llm.model}")
    
    # Test API clients first
    test_api_clients()
    
    # Test Scout agent
    scout_state, scout_success = test_scout_agent()
    
    if not scout_success:
        logger.error("\n❌ Scout agent test failed!")
        return False
    
    logger.info("\n✓ Scout agent test passed!")
    
    # Test Researcher agent
    researcher_state, researcher_success = test_researcher_agent(scout_state)
    
    if not researcher_success:
        logger.error("\n❌ Researcher agent test failed!")
        return False
    
    logger.info("\n✓ Researcher agent test passed!")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Topic: {researcher_state.get('topic', 'None')}")
    logger.info(f"Confidence: {researcher_state.get('confidence', 0):.2f}")
    logger.info(f"Research Notes: {len(researcher_state.get('research_notes', []))}")
    logger.info(f"Workflow Stage: {researcher_state.get('workflow_stage', 'None')}")
    logger.info("\n✅ All tests passed! Scout → Researcher flow is working.")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
