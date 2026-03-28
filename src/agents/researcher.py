"""
Research Agent - Deep research and citation gathering.

This agent conducts comprehensive research on topics from the Scout,
gathers information from multiple sources, and structures findings
with proper citations.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseAgent
from ..state import NewsroomState, ResearchNote, add_research_note
from ..utils.api_clients import (
    HackerNewsClient, ArXivClient, DuckDuckGoNewsClient, RedditClient, scrape_article_text
)
from ..utils.llm_utils import (
    generate_structured_output,
    create_research_synthesis_prompt,
    create_research_planning_prompt,
    load_prompt_template,
    format_prompt
)
from ..utils.config import get_config
from ..storage.memory import SystemMemory

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """
    Researcher agent that conducts deep research on topics.
    
    Responsibilities:
    - Conduct comprehensive research from multiple sources
    - Extract key claims with citations
    - Structure research notes
    - Calculate credibility scores
    - Always route to Skeptic for validation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Researcher agent.
        
        Args:
            config: Optional configuration dictionary
        """
        if config is None:
            app_config = get_config()
            config = {
                'max_sources': app_config.agents.max_research_sources,
                'llm_provider': app_config.llm.provider,
                'llm_model': app_config.llm.model
            }
        
        super().__init__(name="researcher", config=config)
        
        # Initialize API clients
        self.hn_client = HackerNewsClient()
        self.reddit_client = RedditClient()
        self.arxiv_client = ArXivClient()
        self.ddg_client = DuckDuckGoNewsClient()
        self.memory = SystemMemory()
        
        self.max_sources = config.get('max_sources', 10)
    
    def validate_input(self, state: NewsroomState) -> bool:
        """
        Validate that the state has a topic to research.
        
        Args:
            state: Current newsroom state
            
        Returns:
            True if valid, False otherwise
        """
        if not state.get("topic"):
            self.logger.error("No topic found in state")
            return False
        
        return True
    
    async def process(self, state: NewsroomState) -> NewsroomState:
        """
        Main Researcher processing logic.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Updated newsroom state
        """
        topic = state["topic"]
        self.logger.info(f"Researcher agent starting research on: '{topic}'")
        
        # Step 1: Generate Research Plan (Keywords and Queries)
        research_plan = await self.generate_research_plan(topic)
        keywords = research_plan.get("keywords", topic.split())

        # Step 2: Gather information from sources
        sources = await self.gather_sources(topic, research_plan, keywords)
        
        if not sources:
            self.logger.warning(f"Not enough relevant sources gathered ({len(sources)}). Need at least 2.")
            # We enforce minimum 2 relevant sources. If <2, we clear notes to trigger a retry.
            state["research_notes"] = []
            return state
        if len(sources) < 2:
            self.logger.warning("Only 1 source found — proceeding anyway")
        
        # Step 3: Synthesize research
        synthesis = await self.synthesize_research(topic, sources)
        
        if not synthesis:
            self.logger.error("Failed to synthesize research")
            return state
        
        # Step 4: Update state with structured research notes
        state["research_summary"] = synthesis.get('summary', '')
        
        # Add structured notes
        for finding in synthesis.get('structured_notes', []):
            state = add_research_note(
                state,
                claim=f"[{finding.get('category', 'FACTS')}] {finding.get('claim', '')}",
                citation=', '.join(finding.get('sources', [])),
                source_url='',  # Will be populated from sources
                credibility_score=self._map_support_level(finding.get('support_level', 'weak'))
            )
        
        # Store metadata
        state["metadata"]["sources_gathered"] = len(sources)
        state["metadata"]["synthesis"] = synthesis
        
        self.logger.info(f"Research complete: {len(state['research_notes'])} notes, "
                        f"{len(sources)} sources")
        
        return state
    
    def get_routing_decision(self, state: NewsroomState) -> str:
        """
        Route to Skeptic if research produced notes, otherwise retry (up to 2 times).

        Args:
            state: Current newsroom state

        Returns:
            Next agent name: "researcher" to retry, "skeptic" to proceed
        """
        notes = state.get("research_notes", [])
        retry_count = state.get("metadata", {}).get("researcher_retry_count", 0)

        if len(notes) == 0 and retry_count < 2:
            state["metadata"]["researcher_retry_count"] = retry_count + 1
            self.log_decision(
                "RETRY_RESEARCH",
                f"0 notes produced (attempt {retry_count + 1}/2) — retrying researcher"
            )
            return "researcher"

        self.log_decision(
            "PROCEED_TO_SKEPTIC",
            f"Research complete with {len(notes)} notes"
        )
        return "skeptic"
    

    
    async def generate_research_plan(self, topic: str) -> Dict[str, Any]:
        """Generate keywords and search queries."""
        try:
            prompt = create_research_planning_prompt(topic)
            config = get_config()
            plan = await generate_structured_output(
                prompt=prompt,
                system_prompt="You are a research strategist planning deep research on a topic.",
                temperature=0.3,
                provider=config.llm.provider,
                model=config.llm.model
            )
            self.logger.info(f"Generated research plan with {len(plan.get('keywords', []))} keywords")
            return plan
        except Exception as e:
            self.logger.error(f"Failed to generate research plan: {e}")
            return {"keywords": topic.split()}

    async def gather_sources(self, topic: str, research_plan: Dict[str, Any], keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Gather sources directly using generated queries and filter by keywords.
        """
        sources = []
        all_results = []
        
        # Gather from ArXiv
        arxiv_queries = research_plan.get("arxiv_queries", [topic])
        for query in arxiv_queries[:2]:
            papers = await self.arxiv_client.search_papers(query, max_results=3)
            for paper in papers:
                all_results.append({
                    'type': 'arxiv',
                    'title': paper.get('title', ''),
                    'content': paper.get('summary', ''),
                    'url': paper.get('url', ''),
                    'source_name': 'ArXiv'
                })

        # Gather from DuckDuckGo News
        news_queries = research_plan.get("news_queries", [topic])
        for query in news_queries[:2]:
            news_items = await self.ddg_client.search_news(query)
            for item in news_items[:3]:
                url = item.get('url', '')
                content = await scrape_article_text(url)
                if not content: content = item.get('title', '')
                all_results.append({
                    'type': 'news',
                    'title': item.get('title', ''),
                    'content': content,
                    'url': url,
                    'source_name': 'News'
                })
                
        # Gather from Reddit via DDG
        reddit_queries = research_plan.get("reddit_queries", [topic])
        for query in reddit_queries[:2]:
            reddit_items = await self.ddg_client.search_news(f"{query} site:reddit.com")
            for item in reddit_items[:3]:
                url = item.get('url', '')
                content = await self.reddit_client.get_post_with_comments(url, limit=5)
                if not content: content = item.get('title', '')
                all_results.append({
                    'type': 'reddit',
                    'title': item.get('title', ''),
                    'content': content,
                    'url': url,
                    'source_name': 'Reddit'
                })

        # Gather from HackerNews via DDG
        hn_queries = research_plan.get("hackernews_queries", [topic])
        for query in hn_queries[:2]:
            hn_items = await self.ddg_client.search_news(f"{query} site:news.ycombinator.com")
            for item in hn_items[:3]:
                url = item.get('url', '')
                content = ""
                import urllib.parse
                parsed_url = urllib.parse.urlparse(url)
                qs = urllib.parse.parse_qs(parsed_url.query)
                if 'id' in qs:
                    try:
                        story_id = int(qs['id'][0])
                        content = await self.hn_client.get_story_with_comments(story_id, max_comments=5)
                    except ValueError:
                        pass
                
                if not content: content = item.get('title', '')
                all_results.append({
                    'type': 'hackernews',
                    'title': item.get('title', ''),
                    'content': content,
                    'url': url,
                    'source_name': 'Hacker News'
                })

        # Filter sources by keyword relevance
        valid_sources = []
        for result in all_results:
            url = result.get('url', '')
            if url:
                valid_sources.append(result)
        
        relevant_sources = []
        for result in valid_sources:
            title_content = (result.get('title', '') + " " + result.get('content', '')).lower()
            
            # Count how many keywords match
            match_count = sum(1 for kw in keywords if kw.lower() in title_content)
            
            # Minimum requirement: at least 1 keyword match
            if match_count >= 1 or not keywords:
                relevant_sources.append(result)

        if len(relevant_sources) < 2:
            self.logger.warning("Relevance filter too strict — using top sources instead")
            relevant_sources = valid_sources[:3]

        # Limit total sources
        sources = relevant_sources[:self.max_sources]
        
        # Add retained sources to memory
        for source in sources:
            source_url = source.get('url')
            if source_url:
                self.memory.add_used_source(source_url)
        
        self.logger.info(f"Gathered {len(sources)} relevant sources after keyword filtering")
        return sources
    

    
    async def synthesize_research(
        self,
        topic: str,
        sources: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Synthesize research findings using LLM.
        
        Args:
            topic: Research topic
            sources: List of sources
            
        Returns:
            Synthesis results or None if failed
        """
        try:
            # Prepare sources summary
            sources_summary = []
            for source in sources:
                sources_summary.append({
                    'title': source.get('title', ''),
                    'type': source.get('type', ''),
                    'url': source.get('url', ''),
                    'content': source.get('content', '')[:3000]
                })
            
            # Create synthesis prompt
            prompt = create_research_synthesis_prompt(topic, sources_summary)
            
            # Generate synthesis
            config = get_config()
            synthesis = await generate_structured_output(
                prompt=prompt,
                system_prompt="You are a research synthesizer creating comprehensive summaries.",
                temperature=0.5,
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            self.logger.info(f"Synthesized research with {len(synthesis.get('structured_notes', []))} findings")
            return synthesis
            
        except Exception as e:
            self.logger.error(f"Failed to synthesize research: {e}", exc_info=True)
            return None
    
    def _is_relevant(self, topic: str, title: str) -> bool:
        """
        Check if a title is relevant to the topic.
        
        Args:
            topic: Main topic
            title: Title to check
            
        Returns:
            True if relevant, False otherwise
        """
        # Simple keyword matching (could be improved with embeddings)
        topic_words = set(topic.lower().split())
        title_words = set(title.lower().split())
        
        # Check for word overlap
        overlap = topic_words.intersection(title_words)
        return len(overlap) >= 2
    
    def _map_support_level(self, support_level: str) -> float:
        """
        Map support level to credibility score.
        
        Args:
            support_level: 'strong', 'moderate', or 'weak'
            
        Returns:
            Credibility score (0-1)
        """
        mapping = {
            'strong': 0.9,
            'moderate': 0.7,
            'weak': 0.5
        }
        return mapping.get(support_level.lower(), 0.5)
