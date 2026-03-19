"""
Main entry point for AI Newsroom.

Run the complete multi-agent newsroom workflow.
"""

import logging
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables explicitly
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.graph import run_newsroom, stream_newsroom
from src.state import create_initial_state
from src.utils.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'newsroom_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='AI Newsroom - Multi-Agent Content Creation')
    parser.add_argument('--stream', action='store_true', help='Stream workflow execution')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--output', type=str, help='Output file for final article')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check configuration
    config = get_config()
    if not config.llm.api_key:
        logger.error("❌ No LLM API key found!")
        logger.error("Set PERPLEXITY_API_KEY in your environment")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("AI NEWSROOM - Multi-Agent Content Creation System")
    logger.info("=" * 70)
    logger.info(f"LLM Provider: {config.llm.provider}")
    logger.info(f"Model: {config.llm.model}")
    logger.info(f"Scout Confidence Threshold: {config.agents.scout_confidence_threshold}")
    logger.info(f"Max Revision Loops: {config.agents.max_revision_loops}")
    logger.info("=" * 70)
    
    # Create initial state
    initial_state = create_initial_state()
    
    try:
        if args.stream:
            # Stream mode - show progress
            logger.info("\n🚀 Starting workflow (streaming mode)...\n")
            
            final_state = None
            async for state_update in stream_newsroom(initial_state):
                # Log state updates
                for node_name, node_state in state_update.items():
                    logger.info(f"📍 {node_name.upper()}: {node_state.get('workflow_stage', 'processing')}")
                final_state = node_state
            
        else:
            # Standard mode - run to completion
            logger.info("\n🚀 Starting workflow...\n")
            final_state = await run_newsroom(initial_state)
        
        # Display results
        logger.info("\n" + "=" * 70)
        logger.info("WORKFLOW COMPLETE")
        logger.info("=" * 70)
        
        if final_state.get("publish_ready"):
            logger.info("✅ Status: PUBLISHED")
            logger.info(f"📝 Topic: {final_state.get('topic')}")
            logger.info(f"📊 Word Count: {len(final_state.get('draft', '').split())}")
            logger.info(f"🔄 Draft Versions: {final_state.get('draft_version', 0)}")
            logger.info(f"📚 Research Sources: {len(final_state.get('research_notes', []))}")
            
            # Save article if output specified
            if args.output:
                save_article(final_state, args.output)
            else:
                # Save to default location
                output_dir = Path("output")
                output_dir.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = output_dir / f"article_{timestamp}.md"
                save_article(final_state, str(output_file))
        
        else:
            logger.info("❌ Status: NOT PUBLISHED")
            logger.info(f"⚠️ Reason: Workflow ended at {final_state.get('workflow_stage', 'unknown')}")
            
            # Show feedback if available
            if final_state.get("critic_feedback"):
                logger.info("\n📋 Skeptic Feedback:")
                for feedback in final_state["critic_feedback"][-2:]:
                    logger.info(f"   {feedback}")
            
            if final_state.get("editor_comments"):
                logger.info("\n📋 Editor Comments:")
                for comment in final_state["editor_comments"][-2:]:
                    logger.info(f"   {comment}")
        
        logger.info("=" * 70)
        
        # Exit with appropriate code
        sys.exit(0 if final_state.get("publish_ready") else 1)
        
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Workflow interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        logger.error(f"\n\n❌ Workflow failed: {e}", exc_info=True)
        sys.exit(1)


def save_article(state: dict, output_path: str):
    """
    Save the final article to a file.
    
    Args:
        state: Final newsroom state
        output_path: Path to save the article
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create article with metadata
        article_content = []
        
        # Add frontmatter
        article_content.append("---")
        article_content.append(f"title: {state.get('topic', 'Untitled')}")
        
        publishing_metadata = state.get("publishing_metadata", {})
        if publishing_metadata:
            article_content.append(f"author: {publishing_metadata.get('author', 'AI Newsroom')}")
            article_content.append(f"date: {publishing_metadata.get('published_date', '')}")
            article_content.append(f"keywords: {', '.join(publishing_metadata.get('keywords', []))}")
            article_content.append(f"reading_time: {publishing_metadata.get('reading_time_minutes', 0)} min")
        
        article_content.append("---")
        article_content.append("")
        
        # Add the article
        article_content.append(state.get("draft", ""))
        
        # Add research notes as appendix
        if state.get("research_notes"):
            article_content.append("\n\n---\n")
            article_content.append("## References\n")
            
            for i, note in enumerate(state["research_notes"][:10], 1):
                citation = note.get("citation", "")
                url = note.get("url", "")
                if citation:
                    article_content.append(f"{i}. {citation}")
                    if url:
                        article_content.append(f"   {url}")
                    article_content.append("")
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(article_content))
        
        logger.info(f"💾 Article saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"Failed to save article: {e}")


if __name__ == "__main__":
    asyncio.run(main())
