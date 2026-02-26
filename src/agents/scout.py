"""
Trend Scout Agent - Hunts for trending topics.

This agent monitors multiple sources for trending topics, analyzes them,
and routes high-confidence topics to the Research agent.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseAgent
from ..state import NewsroomState, AgentDecision, increment_iteration, check_max_iterations
from ..utils.api_clients import TrendAggregator
from ..utils.llm_utils import generate_structured_output, create_topic_analysis_prompt
from ..utils.config import get_config

logger = logging.getLogger(__name__)


class ScoutAgent(BaseAgent):
    """
    Scout agent that discovers and analyzes trending topics.
    
    Responsibilities:
    - Fetch trending topics from multiple sources
    - Analyze topic relevance and novelty
    - Calculate confidence scores
    - Route high-confidence topics to Researcher
    - Loop back for rescanning if confidence is low
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Scout agent.
        
        Args:
            config: Optional configuration dictionary
        """
        if config is None:
            app_config = get_config()
            config = {
                'confidence_threshold': app_config.agents.scout_confidence_threshold,
                'max_iterations': app_config.agents.max_scout_iterations,
                'llm_provider': app_config.llm.provider,
                'llm_model': app_config.llm.model,
            }

        super().__init__(name="scout", config=config)

        # Initialize trend aggregator (all sources are free, no API keys needed)
        self.aggregator = TrendAggregator()
        
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        self.max_iterations = config.get('max_iterations', 3)
    
    def validate_input(self, state: NewsroomState) -> bool:
        """
        Validate that the state is ready for Scout processing.
        
        Args:
            state: Current newsroom state
            
        Returns:
            True if valid, False otherwise
        """
        # Scout can start with minimal state
        return True
    
    def process(self, state: NewsroomState) -> NewsroomState:
        """
        Main Scout processing logic.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Updated newsroom state
        """
        self.logger.info("Scout agent starting topic discovery...")
        
        # Increment scout iteration count
        state = increment_iteration(state, "scout_loops")
        
        # Check if we've exceeded max iterations
        if check_max_iterations(state, "scout_loops", self.max_iterations):
            self.logger.warning(f"Scout exceeded max iterations ({self.max_iterations})")
            state["metadata"]["scout_failure"] = "Max iterations exceeded"
            state["confidence"] = 0.0
            return state
        
        # Step 1: Fetch trending topics from all sources
        all_trends = self.fetch_trending_topics()
        
        if not any(all_trends.values()):
            self.logger.error("No trends fetched from any source")
            state["confidence"] = 0.0
            return state
        
        # Step 2: Aggregate and deduplicate topics
        aggregated_topics = self.aggregate_topics(all_trends)
        
        if not aggregated_topics:
            self.logger.warning("No topics after aggregation")
            state["confidence"] = 0.0
            return state
        
        # Step 3: Analyze top topics
        analyzed_topics = []
        for topic in aggregated_topics[:5]:  # Analyze top 5
            analysis = self.analyze_topic(topic)
            if analysis:
                analyzed_topics.append({
                    'topic': topic,
                    'analysis': analysis
                })
        
        if not analyzed_topics:
            self.logger.warning("No topics passed analysis")
            state["confidence"] = 0.0
            return state
        
        # Step 4: Select best topic
        best_topic = max(analyzed_topics, key=lambda x: x['analysis'].get('overall_confidence', 0))
        
        # Step 5: Update state
        state["topic"] = best_topic['topic'].get('title', '')
        state["topic_keywords"] = best_topic['analysis'].get('keywords', [])
        state["confidence"] = best_topic['analysis'].get('overall_confidence', 0.0)
        
        # Store metadata
        state["metadata"]["scout_analysis"] = best_topic['analysis']
        state["metadata"]["all_trends"] = all_trends
        state["metadata"]["analyzed_topics"] = analyzed_topics
        
        self.logger.info(f"Selected topic: '{state['topic']}' with confidence {state['confidence']:.2f}")
        
        return state
    
    def get_routing_decision(self, state: NewsroomState) -> str:
        """
        Determine routing based on confidence score.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Next agent name or "END"
        """
        confidence = state.get("confidence", 0.0)
        
        if confidence >= self.confidence_threshold:
            self.log_decision(
                AgentDecision.PROCEED,
                f"Confidence {confidence:.2f} >= threshold {self.confidence_threshold}"
            )
            return "researcher"
        
        # Check if we've hit max iterations
        if check_max_iterations(state, "scout_loops", self.max_iterations):
            self.log_decision(
                "END",
                f"Max iterations reached, confidence still low: {confidence:.2f}"
            )
            return "END"
        
        # Rescan with adjusted parameters
        self.log_decision(
            AgentDecision.RESCAN,
            f"Confidence {confidence:.2f} < threshold {self.confidence_threshold}, rescanning..."
        )
        return "scout"  # Loop back to self
    
    def fetch_trending_topics(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch trending topics from all available sources.
        
        Returns:
            Dictionary of trends from each source
        """
        self.logger.info("Fetching trends from all sources...")
        
        try:
            trends = self.aggregator.get_all_trends(hn_limit=30, arxiv_limit=10)
            
            # Log what we got
            for source, items in trends.items():
                if items:
                    self.logger.info(f"  {source}: {len(items)} items")
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Failed to fetch trends: {e}", exc_info=True)
            return {}
    
    def aggregate_topics(self, all_trends: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Aggregate and deduplicate topics from multiple sources.
        
        Args:
            all_trends: Trends from all sources
            
        Returns:
            List of aggregated topics, ranked by relevance
        """
        aggregated = []
        seen_titles = set()
        
        # Process each source
        for source, trends in all_trends.items():
            for trend in trends:
                title = trend.get('title', trend.get('keyword', ''))
                
                if not title:
                    continue
                
                # Simple deduplication by title (case-insensitive)
                title_lower = title.lower()
                if title_lower in seen_titles:
                    continue
                
                seen_titles.add(title_lower)
                
                # Add source information
                trend['source'] = source
                aggregated.append(trend)
        
        # Sort by engagement metrics where available
        def get_engagement_score(topic):
            score = topic.get('score', 0)
            comments = topic.get('comments', 0)
            rank = topic.get('rank', 100)
            
            # Combine metrics (lower rank is better)
            return score + comments - rank
        
        aggregated.sort(key=get_engagement_score, reverse=True)
        
        self.logger.info(f"Aggregated {len(aggregated)} unique topics")
        return aggregated
    
    def analyze_topic(self, topic: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze a topic using LLM.
        
        Args:
            topic: Topic data
            
        Returns:
            Analysis results or None if failed
        """
        try:
            # Create analysis prompt
            prompt = create_topic_analysis_prompt(topic)
            
            # Get LLM analysis
            config = get_config()
            analysis = generate_structured_output(
                prompt=prompt,
                system_prompt="You are an expert content strategist analyzing topics for technical articles.",
                temperature=0.3,  # Lower temperature for more consistent analysis
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            self.logger.debug(f"Analysis for '{topic.get('title', 'unknown')}': {analysis.get('overall_confidence', 0):.2f}")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Failed to analyze topic: {e}", exc_info=True)
            return None
    
    def calculate_confidence(self, analysis: Dict[str, Any]) -> float:
        """
        Calculate overall confidence score from analysis.
        
        Args:
            analysis: LLM analysis results
            
        Returns:
            Confidence score (0-1)
        """
        # Weighted average of different factors
        weights = {
            'relevance': 0.25,
            'novelty': 0.20,
            'technical_depth': 0.20,
            'audience_interest': 0.20,
            'cross_platform_score': 0.15
        }
        
        confidence = 0.0
        for factor, weight in weights.items():
            confidence += analysis.get(factor, 0.0) * weight
        
        return min(max(confidence, 0.0), 1.0)  # Clamp to [0, 1]
