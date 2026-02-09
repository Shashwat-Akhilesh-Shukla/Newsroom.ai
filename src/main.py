"""
Main entry point for the AI Newsroom application.

This module provides the CLI interface and orchestrates the entire workflow.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from .utils.config import get_config
from .utils.logging_config import setup_logging, get_logger
from .graph import create_newsroom_graph
from .state import create_initial_state, get_state_summary


def main(topic: Optional[str] = None, config_file: Optional[str] = None):
    """
    Run the AI Newsroom pipeline.
    
    Args:
        topic: Optional topic to research (if not provided, Scout will find one)
        config_file: Optional path to .env file
    """
    # Load configuration
    config = get_config(config_file)
    
    # Setup logging
    setup_logging(
        log_level=config.get("log_level", "INFO"),
        log_file=config.get("log_file"),
        debug=config.is_debug
    )
    
    logger = get_logger(__name__)
    logger.info("=" * 60)
    logger.info("AI Newsroom Starting")
    logger.info("=" * 60)
    
    # Create initial state
    initial_state = create_initial_state(topic)
    logger.info(f"Initial state created:\n{get_state_summary(initial_state)}")
    
    # Create and compile the graph
    logger.info("Compiling LangGraph workflow...")
    graph = create_newsroom_graph()
    logger.info("Graph compiled successfully")
    
    # Execute the workflow
    logger.info("Starting workflow execution...")
    
    try:
        # Run the graph
        config_dict = {"configurable": {"thread_id": "newsroom-1"}}
        
        logger.info("Invoking graph...")
        final_state = graph.invoke(initial_state, config_dict)
        
        logger.info("=" * 60)
        logger.info("Workflow Completed Successfully")
        logger.info("=" * 60)
        logger.info(f"Final state:\n{get_state_summary(final_state)}")
        
        # Print results
        if final_state.get("publish_ready"):
            logger.info("\n" + "=" * 60)
            logger.info("PUBLISHED ARTICLE")
            logger.info("=" * 60)
            logger.info(f"Topic: {final_state['topic']}")
            logger.info(f"Draft:\n{final_state['draft']}")
            logger.info("=" * 60)
        else:
            logger.warning("Article was not published")
        
        return final_state
        
    except KeyboardInterrupt:
        logger.warning("Workflow interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}", exc_info=True)
        sys.exit(1)


def cli():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="AI Newsroom - Multi-Agent Content Creation System"
    )
    
    parser.add_argument(
        "--topic",
        type=str,
        help="Topic to research (optional, Scout will find one if not provided)"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Path to .env configuration file"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with verbose logging"
    )
    
    args = parser.parse_args()
    
    # Override debug setting if specified
    if args.debug:
        import os
        os.environ["DEBUG"] = "True"
    
    # Run the main function
    main(topic=args.topic, config_file=args.config)


if __name__ == "__main__":
    cli()
