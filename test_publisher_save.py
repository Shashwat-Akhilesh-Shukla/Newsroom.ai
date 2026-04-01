import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.publisher import PublisherAgent
from src.state import create_initial_state

async def test_save():
    print("Initializing PublisherAgent...")
    agent = PublisherAgent()
    
    # Mock state
    state = create_initial_state("Test Topic Saving Document")
    state["draft"] = "This is a test drafted article. It should be saved to the output directory as a .doc file."
    state["research_notes"] = [
        {"citation": "Test Citation 1", "url": "http://test.com/1"},
        {"citation": "Test Citation 2", "url": "http://test.com/2"}
    ]
    
    print("Running PublisherAgent.process()...")
    # This should trigger save_approved_draft
    new_state = await agent.process(state)
    
    doc_path = new_state.get("metadata", {}).get("approved_doc_path")
    if doc_path and os.path.exists(doc_path):
        print(f"SUCCESS: Document was saved at {doc_path}!")
        with open(doc_path, "r", encoding="utf-8") as f:
            print("Document Content:")
            print(f.read())
    else:
        print("FAILED: Document was not saved!")
        print("Metadata:", new_state.get("metadata"))

if __name__ == "__main__":
    asyncio.run(test_save())
