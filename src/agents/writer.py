"""
Writer Agent - Creates article drafts.

This agent generates article drafts based on approved research,
maintains consistent style, and handles revision requests from the Editor.
"""

import logging
import json
from typing import Dict, Any, Optional, List

from .base import BaseAgent
from ..state import NewsroomState
from ..utils.llm_utils import (
    generate_completion,
    load_prompt_template,
    format_prompt
)
from ..utils.config import get_config

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """
    Writer agent that creates article drafts from research.
    
    Responsibilities:
    - Generate article drafts from approved research
    - Follow style guide and maintain consistent tone
    - Incorporate citations properly
    - Handle revision requests from Editor
    - Extract verifiable claims for fact-checking
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Writer agent.
        
        Args:
            config: Optional configuration dictionary
        """
        if config is None:
            app_config = get_config()
            config = {
                'llm_provider': app_config.llm.provider,
                'llm_model': app_config.llm.model,
                'max_draft_length': 2000,
                'style': 'technical'
            }
        
        super().__init__(name="writer", config=config)
        
        self.max_draft_length = config.get('max_draft_length', 2000)
        self.style = config.get('style', 'technical')
    
    def validate_input(self, state: NewsroomState) -> bool:
        """
        Validate that the state has approved research.
        
        Args:
            state: Current newsroom state
            
        Returns:
            True if valid, False otherwise
        """
        if not state.get("topic"):
            self.logger.error("No topic found in state")
            return False
        
        if not state.get("research_summary"):
            self.logger.error("No research summary found in state")
            return False
        
        return True
    
    async def process(self, state: NewsroomState) -> NewsroomState:
        """
        Main Writer processing logic.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Updated newsroom state
        """
        topic = state["topic"]
        draft_version = state.get("draft_version", 0)
        
        self.logger.info(f"Writer agent creating draft v{draft_version + 1} for: '{topic}'")
        
        # Check if this is a revision
        is_revision = draft_version > 0
        editor_feedback = state.get("editor_comments", [])
        
        if is_revision:
            self.logger.info(f"Handling revision request with {len(editor_feedback)} comments")
            draft = await self.revise_draft(state, editor_feedback)
        else:
            self.logger.info("Creating initial draft")
            draft = await self.create_draft(state)
        
        if not draft:
            self.logger.error("Failed to create draft")
            return state
        
        # Extract claims for verification
        claims = self.extract_claims(draft)
        
        # Update state
        state["draft"] = draft
        state["draft_version"] = draft_version + 1
        state["claim_list"] = claims
        
        # Store metadata
        state["metadata"]["draft_metadata"] = {
            "version": draft_version + 1,
            "word_count": len(draft.split()),
            "is_revision": is_revision,
            "num_claims": len(claims)
        }
        
        self.logger.info(f"Draft v{draft_version + 1} complete: {len(draft.split())} words, {len(claims)} claims")
        
        return state
    
    def get_routing_decision(self, state: NewsroomState) -> str:
        """
        Writer always routes to Editor for review.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Next agent name (always "editor")
        """
        self.log_decision(
            "PROCEED_TO_EDITOR",
            f"Draft v{state.get('draft_version', 0)} ready for review"
        )
        return "editor"
    
    async def create_draft(self, state: NewsroomState) -> Optional[str]:
        """
        Create initial article draft.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Article draft or None if failed
        """
        try:
            # Load style guide
            style_guide = self._load_style_guide()
            
            # Prepare research context
            research_context = {
                "topic": state["topic"],
                "summary": state.get("research_summary", ""),
                "key_findings": [
                    {
                        "claim": note.get("claim", ""),
                        "citation": note.get("citation", "")
                    }
                    for note in state.get("research_notes", [])[:10]
                ]
            }
            
            # Load prompt template
            template = load_prompt_template("writer", "draft_creation")
            
            if not template:
                # Fallback prompt
                template = """You are a skilled technical writer creating an article.

Topic: {topic}

Research Summary:
{research_summary}

Style Guide:
{style_guide}

Write a comprehensive, well-structured article that:
1. Has an engaging introduction
2. Presents findings clearly with proper citations
3. Maintains a {style} tone
4. Includes a thoughtful conclusion
5. Is approximately {max_words} words

Write the complete article now."""
            
            prompt = format_prompt(
                template,
                topic=state["topic"],
                research_summary=json.dumps(research_context, indent=2),
                style_guide=style_guide,
                style=self.style,
                max_words=self.max_draft_length
            )
            
            # Generate draft
            config = get_config()
            draft = await generate_completion(
                prompt=prompt,
                system_prompt="You are an expert technical writer who creates clear, engaging, well-researched articles.",
                temperature=0.7,
                max_tokens=self.max_draft_length * 2,  # Tokens ≈ words * 1.5-2
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            return draft
            
        except Exception as e:
            self.logger.error(f"Failed to create draft: {e}", exc_info=True)
            return None
    
    async def revise_draft(self, state: NewsroomState, editor_feedback: List[str]) -> Optional[str]:
        """
        Revise existing draft based on editor feedback.
        
        Args:
            state: Current newsroom state
            editor_feedback: List of editor comments
            
        Returns:
            Revised draft or None if failed
        """
        try:
            current_draft = state.get("draft", "")
            
            # Create revision prompt
            prompt = f"""You are revising an article based on editor feedback.

Current Draft:
{current_draft}

Editor Feedback:
{chr(10).join(f"- {comment}" for comment in editor_feedback[-3:])}

Revise the article to address ALL the feedback while maintaining:
1. The core message and research findings
2. Proper citations
3. Clear, engaging writing
4. Logical flow

Provide the complete revised article."""
            
            # Generate revision
            config = get_config()
            revised_draft = await generate_completion(
                prompt=prompt,
                system_prompt="You are an expert technical writer who carefully addresses editorial feedback.",
                temperature=0.7,
                max_tokens=self.max_draft_length * 2,
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            return revised_draft
            
        except Exception as e:
            self.logger.error(f"Failed to revise draft: {e}", exc_info=True)
            return None
    
    def extract_claims(self, draft: str) -> List[str]:
        """
        Extract verifiable claims from the draft.
        
        Args:
            draft: Article draft
            
        Returns:
            List of claims
        """
        try:
            # Simple extraction: look for factual statements
            # In production, this would use more sophisticated NLP
            
            # For now, extract sentences with numbers, dates, or strong assertions
            import re
            
            sentences = draft.split('.')
            claims = []
            
            for sentence in sentences:
                sentence = sentence.strip()
                
                # Skip if too short
                if len(sentence.split()) < 5:
                    continue
                
                # Check for claim indicators
                has_number = bool(re.search(r'\d+', sentence))
                has_strong_verb = any(word in sentence.lower() for word in [
                    'is', 'are', 'was', 'were', 'shows', 'demonstrates', 
                    'proves', 'indicates', 'reveals', 'found'
                ])
                
                if has_number or has_strong_verb:
                    claims.append(sentence)
            
            return claims[:10]  # Limit to top 10 claims
            
        except Exception as e:
            self.logger.error(f"Failed to extract claims: {e}")
            return []
    
    def _load_style_guide(self) -> str:
        """Load style guide from config."""
        try:
            from pathlib import Path
            style_guide_path = Path(__file__).parent.parent.parent / "config" / "style_guide.md"
            
            if style_guide_path.exists():
                with open(style_guide_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                return self._get_default_style_guide()
                
        except Exception as e:
            self.logger.warning(f"Failed to load style guide: {e}")
            return self._get_default_style_guide()
    
    def _get_default_style_guide(self) -> str:
        """Get default style guide."""
        return """
# Style Guide

## Tone
- Technical but accessible
- Authoritative but not arrogant
- Engaging but not sensational

## Structure
- Clear introduction with hook
- Logical progression of ideas
- Proper use of headings and subheadings
- Strong conclusion

## Citations
- Inline citations for all claims
- Link to original sources
- Proper attribution

## Language
- Active voice preferred
- Clear, concise sentences
- Avoid jargon unless necessary
- Define technical terms
"""
