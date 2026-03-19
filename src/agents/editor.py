"""
Editor Agent - Brutal content review.

This agent reviews article drafts, checks for quality issues,
and can force rewrites or request fact-checking.
"""

import logging
import json
from typing import Dict, Any, Optional, List

from .base import BaseAgent
from ..state import NewsroomState, AgentDecision, increment_iteration, check_max_iterations
from ..utils.llm_utils import (
    generate_structured_output,
    load_prompt_template,
    format_prompt
)
from ..utils.config import get_config

logger = logging.getLogger(__name__)


class EditorAgent(BaseAgent):
    """
    Editor agent that reviews and critiques article drafts.
    
    Responsibilities:
    - Review drafts for quality, logic, and accuracy
    - Check for hallucinations and unsupported claims
    - Enforce editorial standards
    - Make routing decisions: ACCEPT, REWRITE, or FACT_CHECK
    - Provide detailed, actionable feedback
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Editor agent.
        
        Args:
            config: Optional configuration dictionary
        """
        if config is None:
            app_config = get_config()
            config = {
                'quality_threshold': 0.85,
                'max_revisions': app_config.agents.max_revision_loops,
                'llm_provider': app_config.llm.provider,
                'llm_model': app_config.llm.model
            }
        
        super().__init__(name="editor", config=config)
        
        self.quality_threshold = config.get('quality_threshold', 0.85)
        self.max_revisions = config.get('max_revisions', 3)
    
    def validate_input(self, state: NewsroomState) -> bool:
        """
        Validate that the state has a draft to review.
        
        Args:
            state: Current newsroom state
            
        Returns:
            True if valid, False otherwise
        """
        if not state.get("draft"):
            self.logger.error("No draft found in state")
            return False
        
        return True
    
    async def process(self, state: NewsroomState) -> NewsroomState:
        """
        Main Editor processing logic.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Updated newsroom state
        """
        draft = state["draft"]
        draft_version = state.get("draft_version", 0)
        
        self.logger.info(f"Editor agent reviewing draft v{draft_version}")
        
        # Increment revision count
        state = increment_iteration(state, "revision_loops")
        
        # Step 1: Review draft quality
        review = await self.review_draft(state)
        
        if not review:
            self.logger.error("Failed to review draft")
            state["editor_decision"] = AgentDecision.REWRITE
            state["editor_comments"].append("Failed to complete review - please revise")
            return state
        
        # Step 2: Check for logic holes
        logic_check = self.check_logic(draft, review)
        
        # Step 3: Validate claims
        claims_check = self.validate_claims(state)
        
        # Step 4: Make decision
        decision = self.make_decision(review, logic_check, claims_check, state)
        
        # Step 5: Generate feedback
        feedback = self.generate_feedback(review, logic_check, claims_check, decision)
        
        # Update state
        state["editor_decision"] = decision
        state["editor_comments"].append(feedback)
        
        # Store metadata
        state["metadata"]["editor_review"] = {
            "version_reviewed": draft_version,
            "review": review,
            "logic_check": logic_check,
            "claims_check": claims_check,
            "decision": decision
        }
        
        self.logger.info(f"Editor decision: {decision}")
        
        return state
    
    def get_routing_decision(self, state: NewsroomState) -> str:
        """
        Determine routing based on Editor's decision.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Next agent name
        """
        decision = state.get("editor_decision", AgentDecision.REWRITE)
        
        if decision == AgentDecision.ACCEPT:
            self.log_decision(
                AgentDecision.ACCEPT,
                "Draft meets editorial standards, proceeding to Publisher"
            )
            return "publisher"
        
        elif decision == AgentDecision.FACT_CHECK:
            self.log_decision(
                AgentDecision.FACT_CHECK,
                "Claims need verification, sending to Researcher"
            )
            return "researcher"
        
        else:  # REWRITE
            # Check if we've exceeded max revisions
            if check_max_iterations(state, "revision_loops", self.max_revisions):
                self.log_decision(
                    "MAX_REVISIONS",
                    f"Max revisions ({self.max_revisions}) reached, accepting draft as-is"
                )
                return "publisher"
            
            self.log_decision(
                AgentDecision.REWRITE,
                f"Draft needs revision (attempt {state['iteration_counts'].get('revision_loops', 0)}/{self.max_revisions})"
            )
            return "writer"
    
    async def review_draft(self, state: NewsroomState) -> Optional[Dict[str, Any]]:
        """
        Review draft quality using LLM.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Review results or None if failed
        """
        try:
            draft = state["draft"]
            topic = state["topic"]
            
            # Load prompt template
            template = load_prompt_template("editor", "content_review")
            
            if not template:
                # Fallback prompt
                template = """You are a brutal but fair editor reviewing an article draft.

Topic: {topic}

Draft:
{draft}

Review the draft for:
1. **Clarity**: Is the writing clear and easy to follow?
2. **Logic**: Are arguments well-structured and logical?
3. **Evidence**: Are claims properly supported?
4. **Engagement**: Is it interesting to read?
5. **Technical Accuracy**: Are technical details correct?

Return JSON:
```json
{{
  "clarity_score": 0.0-1.0,
  "logic_score": 0.0-1.0,
  "evidence_score": 0.0-1.0,
  "engagement_score": 0.0-1.0,
  "technical_accuracy": 0.0-1.0,
  "overall_quality": 0.0-1.0,
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "specific_issues": ["issue1", "issue2"],
  "recommendation": "accept/rewrite/fact_check"
}}
```"""
            
            prompt = format_prompt(
                template,
                topic=topic,
                draft=draft[:3000]  # Limit draft length for prompt
            )
            
            # Get LLM review
            config = get_config()
            review = await generate_structured_output(
                prompt=prompt,
                system_prompt="You are a perfectionist editor who demands excellence and catches every flaw.",
                temperature=0.3,
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            self.logger.info(f"Draft quality: {review.get('overall_quality', 0):.2f}")
            return review
            
        except Exception as e:
            self.logger.error(f"Failed to review draft: {e}", exc_info=True)
            return None
    
    def check_logic(self, draft: str, review: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for logic holes and inconsistencies.
        
        Args:
            draft: Article draft
            review: Review results
            
        Returns:
            Logic check results
        """
        # Extract logic issues from review
        specific_issues = review.get("specific_issues", [])
        logic_score = review.get("logic_score", 0.5)
        
        logic_issues = [
            issue for issue in specific_issues 
            if any(word in issue.lower() for word in ['logic', 'contradict', 'inconsistent', 'unclear'])
        ]
        
        return {
            "has_logic_issues": logic_score < 0.7,
            "logic_score": logic_score,
            "issues": logic_issues
        }
    
    def validate_claims(self, state: NewsroomState) -> Dict[str, Any]:
        """
        Validate that claims are properly supported.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Claims validation results
        """
        claims = state.get("claim_list", [])
        research_notes = state.get("research_notes", [])
        
        # Simple check: do we have research to support claims?
        num_claims = len(claims)
        num_sources = len(research_notes)
        
        # Rough heuristic: should have at least 1 source per 2 claims
        has_enough_support = num_sources >= (num_claims / 2)
        
        return {
            "num_claims": num_claims,
            "num_sources": num_sources,
            "has_enough_support": has_enough_support,
            "needs_fact_check": num_claims > num_sources * 2
        }
    
    def make_decision(
        self,
        review: Dict[str, Any],
        logic_check: Dict[str, Any],
        claims_check: Dict[str, Any],
        state: NewsroomState
    ) -> str:
        """
        Make editorial decision.
        
        Args:
            review: Review results
            logic_check: Logic check results
            claims_check: Claims validation results
            state: Current newsroom state
            
        Returns:
            Decision: ACCEPT, REWRITE, or FACT_CHECK
        """
        overall_quality = review.get("overall_quality", 0)
        has_logic_issues = logic_check.get("has_logic_issues", False)
        needs_fact_check = claims_check.get("needs_fact_check", False)
        
        # Decision logic
        if needs_fact_check:
            return AgentDecision.FACT_CHECK
        
        if overall_quality >= self.quality_threshold and not has_logic_issues:
            return AgentDecision.ACCEPT
        
        if overall_quality < 0.5 or has_logic_issues:
            return AgentDecision.REWRITE
        
        # Borderline case - check revision count
        revision_count = state.get("iteration_counts", {}).get("revision_loops", 0)
        if revision_count >= self.max_revisions - 1:
            return AgentDecision.ACCEPT  # Accept to avoid infinite loop
        
        return AgentDecision.REWRITE
    
    def generate_feedback(
        self,
        review: Dict[str, Any],
        logic_check: Dict[str, Any],
        claims_check: Dict[str, Any],
        decision: str
    ) -> str:
        """
        Generate detailed editorial feedback.
        
        Args:
            review: Review results
            logic_check: Logic check results
            claims_check: Claims validation results
            decision: Editorial decision
            
        Returns:
            Feedback string
        """
        feedback_parts = []
        
        # Decision header
        feedback_parts.append(f"**Editorial Decision: {decision}**\n")
        
        # Quality summary
        quality = review.get("overall_quality", 0)
        feedback_parts.append(f"Overall Quality: {quality:.2f}\n")
        
        # Strengths
        strengths = review.get("strengths", [])
        if strengths:
            feedback_parts.append("**Strengths:**")
            for strength in strengths[:3]:
                feedback_parts.append(f"✓ {strength}")
            feedback_parts.append("")
        
        # Weaknesses
        weaknesses = review.get("weaknesses", [])
        if weaknesses:
            feedback_parts.append("**Issues to Address:**")
            for weakness in weaknesses[:3]:
                feedback_parts.append(f"✗ {weakness}")
            feedback_parts.append("")
        
        # Specific issues
        specific_issues = review.get("specific_issues", [])
        if specific_issues:
            feedback_parts.append("**Specific Problems:**")
            for issue in specific_issues[:3]:
                feedback_parts.append(f"- {issue}")
            feedback_parts.append("")
        
        # Logic issues
        if logic_check.get("has_logic_issues"):
            feedback_parts.append("⚠️ **Logic Issues Detected**")
            for issue in logic_check.get("issues", [])[:2]:
                feedback_parts.append(f"- {issue}")
            feedback_parts.append("")
        
        # Claims check
        if claims_check.get("needs_fact_check"):
            feedback_parts.append("⚠️ **Fact-Check Required**")
            feedback_parts.append(f"The draft has {claims_check['num_claims']} claims but only {claims_check['num_sources']} sources.")
            feedback_parts.append("")
        
        return "\n".join(feedback_parts)
