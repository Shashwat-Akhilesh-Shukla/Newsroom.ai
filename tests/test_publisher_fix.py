import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.publisher import PublisherAgent
from src.state import create_initial_state, AgentDecision

async def test_fix():
    print("Initializing PublisherAgent...")
    agent = PublisherAgent()
    
    # Mocking external calls to force PUBLISH decision
    async def mock_generate_seo_metadata(state):
        return {"title_tag": "Mock SEO Title", "slug": "mock-seo-title"}
    
    # Override the methods
    agent.generate_seo_metadata = mock_generate_seo_metadata
    agent.check_duplicate_content = lambda draft: {"is_duplicate": False, "content_hash": "mockhash"}
    agent.validate_formatting = lambda draft: {"is_valid": True, "issues": []}
    
    # Mock state
    state = create_initial_state("Test Topic Saving Document")
    state["draft"] = "This is a test drafted article.\n\nIt has paragraphs and structure to pass validation."
    state["research_notes"] = []
    
    print("Running PublisherAgent.process()...")
    try:
        new_state = await agent.process(state)
        
        if new_state.get("publish_ready"):
            print("SUCCESS: publish_ready is True! The KeyError didn't happen.")
            print("Publishing metadata:", new_state.get("publishing_metadata"))
        else:
            print("FAILED: publish_ready is False. Workflow did not enter PUBLISH.")
            print("Publisher Decision:", new_state.get("publisher_decision"))
            
    except Exception as e:
        print(f"FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fix())
