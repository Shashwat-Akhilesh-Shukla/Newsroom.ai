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
from ..utils.api_clients import HackerNewsClient, ArXivClient
from ..utils.llm_utils import (
    generate_structured_output,
    create_research_synthesis_prompt,
    load_prompt_template,
    format_prompt
)
from ..utils.config import get_config

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
        self.arxiv_client = ArXivClient()
        
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
        
        # Step 1: Generate research plan
        research_plan = await self.generate_research_plan(topic, state)
        
        if not research_plan:
            self.logger.error("Failed to generate research plan")
            return state
        
        # Step 2: Gather information from sources
        sources = await self.gather_sources(topic, research_plan)
        
        if not sources:
            self.logger.warning("No sources gathered")
            return state
        
        # Step 3: Extract claims from sources
        all_claims = []
        for source in sources:
            claims = await self.extract_claims(source)
            all_claims.extend(claims)
        
        # Step 4: Synthesize research
        synthesis = await self.synthesize_research(topic, sources, all_claims)
        
        if not synthesis:
            self.logger.error("Failed to synthesize research")
            return state
        
        # Step 5: Update state with research findings
        state["research_summary"] = synthesis.get('summary', '')
        
        # Add research notes
        for finding in synthesis.get('main_findings', []):
            state = add_research_note(
                state,
                claim=finding.get('finding', ''),
                citation=', '.join(finding.get('sources', [])),
                source_url='',  # Will be populated from sources
                credibility_score=self._map_support_level(finding.get('support_level', 'weak'))
            )
        
        # Store metadata
        state["metadata"]["research_plan"] = research_plan
        state["metadata"]["sources_gathered"] = len(sources)
        state["metadata"]["claims_extracted"] = len(all_claims)
        state["metadata"]["synthesis"] = synthesis
        
        self.logger.info(f"Research complete: {len(state['research_notes'])} notes, "
                        f"{len(sources)} sources")
        
        return state
    
    def get_routing_decision(self, state: NewsroomState) -> str:
        """
        Researcher always routes to Skeptic for validation.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Next agent name (always "skeptic")
        """
        self.log_decision(
            "PROCEED_TO_SKEPTIC",
            f"Research complete with {len(state.get('research_notes', []))} notes"
        )
        return "skeptic"
    
    async def generate_research_plan(self, topic: str, state: NewsroomState) -> Optional[Dict[str, Any]]:
        """
        Generate a research plan using LLM.
        
        Args:
            topic: Research topic
            state: Current state (for context)
            
        Returns:
            Research plan or None if failed
        """
        try:
            # Get context from Scout analysis if available
            context = state.get("metadata", {}).get("scout_analysis", {})
            
            # Load prompt template
            template = load_prompt_template("researcher", "research_planning")
            prompt = format_prompt(
                template,
                topic=topic,
                context=json.dumps(context, indent=2)
            )
            
            # Generate plan
            config = get_config()
            plan = await generate_structured_output(
                prompt=prompt,
                system_prompt="You are a research strategist planning comprehensive research.",
                temperature=0.5,
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            self.logger.info(f"Generated research plan with {len(plan.get('arxiv_queries', []))} ArXiv queries")
            return plan
            
        except Exception as e:
            self.logger.error(f"Failed to generate research plan: {e}", exc_info=True)
            return None
    
    async def gather_sources(self, topic: str, research_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Gather sources based on research plan.
        
        Args:
            topic: Research topic
            research_plan: Research plan with queries
            
        Returns:
            List of sources
        """
        sources = []
        
        # Gather from ArXiv
        arxiv_queries = research_plan.get('arxiv_queries', [topic])
        for query in arxiv_queries[:3]:  # Limit queries
            papers = await self.arxiv_client.search_papers(query, max_results=5)
            for paper in papers:
                sources.append({
                    'type': 'arxiv',
                    'title': paper.get('title', ''),
                    'content': paper.get('summary', ''),
                    'url': paper.get('url', ''),
                    'authors': paper.get('authors', []),
                    'published': paper.get('published', ''),
                    'source_name': 'ArXiv'
                })
        
        # Gather from Hacker News discussions
        hn_topics = await self.hn_client.get_trending_topics(limit=20)
        for hn_topic in hn_topics:
            # Check if topic is relevant
            if self._is_relevant(topic, hn_topic.get('title', '')):
                sources.append({
                    'type': 'hackernews',
                    'title': hn_topic.get('title', ''),
                    'content': f"Score: {hn_topic.get('score', 0)}, Comments: {hn_topic.get('comments', 0)}",
                    'url': hn_topic.get('url', ''),
                    'source_name': 'Hacker News'
                })
        
        # Limit total sources
        sources = sources[:self.max_sources]
        
        self.logger.info(f"Gathered {len(sources)} sources")
        return sources
    
    async def extract_claims(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract claims from a source using LLM.
        
        Args:
            source: Source data
            
        Returns:
            List of extracted claims
        """
        try:
            # Load prompt template
            template = load_prompt_template("researcher", "claim_extraction")
            prompt = format_prompt(
                template,
                source_name=source.get('source_name', 'Unknown'),
                source_url=source.get('url', ''),
                content=source.get('content', '')[:2000]  # Limit content length
            )
            
            # Extract claims
            config = get_config()
            result = await generate_structured_output(
                prompt=prompt,
                system_prompt="You are a research analyst extracting key claims from sources.",
                temperature=0.3,
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            # Add source information to each claim
            claims = result.get('claims', [])
            for claim in claims:
                claim['source'] = source.get('source_name', 'Unknown')
                claim['source_url'] = source.get('url', '')
            
            return claims
            
        except Exception as e:
            self.logger.error(f"Failed to extract claims from source: {e}", exc_info=True)
            return []
    
    async def synthesize_research(
        self,
        topic: str,
        sources: List[Dict[str, Any]],
        claims: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Synthesize research findings using LLM.
        
        Args:
            topic: Research topic
            sources: List of sources
            claims: List of extracted claims
            
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
                    'url': source.get('url', '')
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
            
            self.logger.info(f"Synthesized research with {len(synthesis.get('main_findings', []))} findings")
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
