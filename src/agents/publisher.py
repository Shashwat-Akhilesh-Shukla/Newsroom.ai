"""
Publisher Agent - Final validation and publishing.

This agent performs final checks, SEO optimization, and publishing validation.
"""

import logging
import json
from typing import Dict, Any, Optional
import hashlib

from .base import BaseAgent
from ..state import NewsroomState, AgentDecision
from ..utils.llm_utils import (
    generate_structured_output,
    load_prompt_template,
    format_prompt
)
from ..utils.config import get_config
from ..utils.reddit_publisher import RedditPublisher, RedditPublishError

logger = logging.getLogger(__name__)


class PublisherAgent(BaseAgent):
    """
    Publisher agent that performs final validation and publishing.
    
    Responsibilities:
    - SEO optimization (meta tags, keywords, etc.)
    - Duplicate content detection
    - Final formatting validation
    - Publishing decision: PUBLISH or REJECT
    - Generate publishing metadata
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Publisher agent.
        
        Args:
            config: Optional configuration dictionary
        """
        if config is None:
            app_config = get_config()
            config = {
                'llm_provider': app_config.llm.provider,
                'llm_model': app_config.llm.model,
                'check_duplicates': True
            }
        
        super().__init__(name="publisher", config=config)
        
        self.check_duplicates = config.get('check_duplicates', True)
    
    def validate_input(self, state: NewsroomState) -> bool:
        """
        Validate that the state has an approved draft.
        
        Args:
            state: Current newsroom state
            
        Returns:
            True if valid, False otherwise
        """
        if not state.get("draft"):
            self.logger.error("No draft found in state")
            return False
        
        return True
    
    def process(self, state: NewsroomState) -> NewsroomState:
        """
        Main Publisher processing logic.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Updated newsroom state
        """
        draft = state["draft"]
        topic = state["topic"]
        
        self.logger.info(f"Publisher agent validating: '{topic}'")
        
        # Step 1: Generate SEO metadata
        seo_metadata = self.generate_seo_metadata(state)
        
        # Step 2: Check for duplicate content
        duplicate_check = self.check_duplicate_content(draft)
        
        # Step 3: Validate formatting
        format_check = self.validate_formatting(draft)
        
        # Step 4: Make publishing decision
        decision = self.make_decision(seo_metadata, duplicate_check, format_check)
        
        # Step 5: Generate publishing metadata
        if decision == AgentDecision.PUBLISH:
            publishing_metadata = self.generate_publishing_metadata(state, seo_metadata)
            state["publishing_metadata"] = publishing_metadata
            state["publish_ready"] = True

            # Step 6: Publish to Reddit via PRAW
            reddit_url = self._publish_to_reddit(state, publishing_metadata)
            if reddit_url:
                state["publishing_metadata"]["reddit_url"] = reddit_url
                self.logger.info(f"Published to Reddit: {reddit_url}")
        else:
            state["publish_ready"] = False
        
        # Update state
        state["publisher_decision"] = decision
        
        # Store metadata
        state["metadata"]["publisher_checks"] = {
            "seo_metadata": seo_metadata,
            "duplicate_check": duplicate_check,
            "format_check": format_check,
            "decision": decision
        }
        
        self.logger.info(f"Publisher decision: {decision}")
        
        return state
    
    def get_routing_decision(self, state: NewsroomState) -> str:
        """
        Determine routing based on Publisher's decision.

        Args:
            state: Current newsroom state

        Returns:
            Next agent name or END
        """
        decision = state.get("publisher_decision", AgentDecision.REJECT)

        if decision == AgentDecision.PUBLISH:
            self.log_decision(
                AgentDecision.PUBLISH,
                "All checks passed, article ready for publishing"
            )
            return "END"

        else:  # REJECT
            self.log_decision(
                AgentDecision.REJECT,
                "Publishing checks failed, sending back to Editor"
            )
            return "editor"

    def _publish_to_reddit(
        self,
        state: NewsroomState,
        publishing_metadata: Dict[str, Any],
    ) -> Optional[str]:
        """
        Attempt to post the article to Reddit via PRAW.

        Returns the post URL on success, or None if credentials are
        missing or posting fails (workflow continues either way).
        """
        import os
        required = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                    "REDDIT_USERNAME", "REDDIT_PASSWORD")
        if any(not os.getenv(v) for v in required):
            self.logger.warning(
                f"Missing Reddit credentials ({', '.join(required)}) — "
                "skipping Reddit publish."
            )
            return None

        try:
            publisher = RedditPublisher()
            url = publisher.publish(
                title=publishing_metadata.get("title", state.get("topic", "Untitled")),
                content_markdown=state.get("draft", ""),
            )
            return url
        except RedditPublishError as e:
            self.logger.error(f"Reddit publishing failed: {e}")
            return None
        except Exception as e:
            self.logger.error(
                f"Unexpected error during Reddit publish: {e}", exc_info=True
            )
            return None
    
    def generate_seo_metadata(self, state: NewsroomState) -> Dict[str, Any]:
        """
        Generate SEO metadata for the article.
        
        Args:
            state: Current newsroom state
            
        Returns:
            SEO metadata
        """
        try:
            draft = state["draft"]
            topic = state["topic"]
            
            # Load prompt template
            template = load_prompt_template("publisher", "seo_optimization")
            
            if not template:
                # Fallback prompt
                template = """You are an SEO expert optimizing an article for search engines.

Topic: {topic}

Article (first 500 words):
{article_preview}

Generate SEO metadata:

Return JSON:
```json
{{
  "title_tag": "60-70 character optimized title",
  "meta_description": "150-160 character compelling description",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "slug": "url-friendly-slug",
  "og_title": "Social media optimized title",
  "og_description": "Social media description"
}}
```"""
            
            # Get first 500 words for preview
            words = draft.split()[:500]
            article_preview = ' '.join(words)
            
            prompt = format_prompt(
                template,
                topic=topic,
                article_preview=article_preview
            )
            
            # Generate SEO metadata
            config = get_config()
            seo_metadata = generate_structured_output(
                prompt=prompt,
                system_prompt="You are an SEO expert who creates compelling, search-optimized metadata.",
                temperature=0.5,
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            self.logger.info(f"Generated SEO metadata: {seo_metadata.get('title_tag', 'N/A')}")
            return seo_metadata
            
        except Exception as e:
            self.logger.error(f"Failed to generate SEO metadata: {e}", exc_info=True)
            return {
                "title_tag": state["topic"],
                "meta_description": f"Article about {state['topic']}",
                "keywords": [],
                "slug": state["topic"].lower().replace(' ', '-')
            }
    
    def check_duplicate_content(self, draft: str) -> Dict[str, Any]:
        """
        Check for duplicate content.
        
        Args:
            draft: Article draft
            
        Returns:
            Duplicate check results
        """
        # Generate content hash
        content_hash = hashlib.sha256(draft.encode()).hexdigest()
        
        # In production, this would check against a database of published articles
        # For now, we'll just return the hash
        
        return {
            "content_hash": content_hash,
            "is_duplicate": False,  # Would check database in production
            "similarity_score": 0.0
        }
    
    def validate_formatting(self, draft: str) -> Dict[str, Any]:
        """
        Validate article formatting.
        
        Args:
            draft: Article draft
            
        Returns:
            Format validation results
        """
        issues = []
        
        # Check for basic formatting
        has_paragraphs = '\n\n' in draft or '\n' in draft
        if not has_paragraphs:
            issues.append("Article appears to be a single block of text")
        
        # Check length
        word_count = len(draft.split())
        if word_count < 300:
            issues.append(f"Article is too short ({word_count} words)")
        elif word_count > 3000:
            issues.append(f"Article is very long ({word_count} words)")
        
        # Check for headings (simple check for # or all caps lines)
        has_headings = '#' in draft or any(
            line.isupper() and len(line.split()) > 1 
            for line in draft.split('\n')
        )
        
        if not has_headings:
            issues.append("No clear headings or structure detected")
        
        return {
            "is_valid": len(issues) == 0,
            "word_count": word_count,
            "has_structure": has_headings,
            "issues": issues
        }
    
    def make_decision(
        self,
        seo_metadata: Dict[str, Any],
        duplicate_check: Dict[str, Any],
        format_check: Dict[str, Any]
    ) -> str:
        """
        Make publishing decision.
        
        Args:
            seo_metadata: SEO metadata
            duplicate_check: Duplicate check results
            format_check: Format validation results
            
        Returns:
            Decision: PUBLISH or REJECT
        """
        # Check for blockers
        if duplicate_check.get("is_duplicate"):
            self.logger.warning("Duplicate content detected")
            return AgentDecision.REJECT
        
        if not format_check.get("is_valid"):
            self.logger.warning(f"Format issues: {format_check.get('issues')}")
            return AgentDecision.REJECT
        
        # Check SEO metadata
        if not seo_metadata.get("title_tag"):
            self.logger.warning("Missing SEO title")
            return AgentDecision.REJECT
        
        # All checks passed
        return AgentDecision.PUBLISH
    
    def generate_publishing_metadata(
        self,
        state: NewsroomState,
        seo_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate complete publishing metadata.
        
        Args:
            state: Current newsroom state
            seo_metadata: SEO metadata
            
        Returns:
            Publishing metadata
        """
        from datetime import datetime
        
        return {
            "title": seo_metadata.get("title_tag", state["topic"]),
            "slug": seo_metadata.get("slug", state["topic"].lower().replace(' ', '-')),
            "meta_description": seo_metadata.get("meta_description", ""),
            "keywords": seo_metadata.get("keywords", []),
            "author": "AI Newsroom",
            "published_date": datetime.now().isoformat(),
            "word_count": len(state["draft"].split()),
            "reading_time_minutes": len(state["draft"].split()) // 200,  # ~200 wpm
            "seo": seo_metadata,
            "content_hash": state["metadata"]["publisher_checks"]["duplicate_check"]["content_hash"]
        }
