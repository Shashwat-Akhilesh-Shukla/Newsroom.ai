"""
Skeptic/Critic Agent - Quality control and relevance checking.

This agent validates research quality, challenges hype, and ensures
topics are worth pursuing before content creation begins.
"""

import logging
import json
from typing import Dict, Any, Optional

from .base import BaseAgent
from ..state import NewsroomState, AgentDecision, increment_iteration
from ..utils.llm_utils import (
    generate_structured_output,
    load_prompt_template,
    format_prompt
)
from ..utils.config import get_config
from ..storage.memory import SystemMemory

logger = logging.getLogger(__name__)


class SkepticAgent(BaseAgent):
    """
    Skeptic agent that validates research quality and relevance.
    
    Responsibilities:
    - Evaluate research quality and credibility
    - Challenge hype and unsubstantiated claims
    - Validate evidence sufficiency
    - Make routing decisions: APPROVE, REJECT, or NEED_MORE_EVIDENCE
    - Provide detailed feedback for rejected topics
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Skeptic agent.
        
        Args:
            config: Optional configuration dictionary
        """
        if config is None:
            app_config = get_config()
            config = {
                'quality_threshold': 0.6,
                'min_sources': 2,
                'llm_provider': app_config.llm.provider,
                'llm_model': app_config.llm.model
            }
        
        super().__init__(name="skeptic", config=config)
        self.memory = SystemMemory()
        
        self.quality_threshold = config.get('quality_threshold', 0.6)
        self.min_sources = config.get('min_sources', 2)
    
    def validate_input(self, state: NewsroomState) -> bool:
        if not state.get("topic"):
            self.logger.error("No topic found in state")
            return False

        if not state.get("research_notes"):
            # Don't crash the pipeline — process() will issue a REJECT
            self.logger.warning("Skeptic received no research notes — will auto-reject")

        return True
    
    async def process(self, state: NewsroomState) -> NewsroomState:
        """
        Main Skeptic processing logic.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Updated newsroom state
        """
        topic = state["topic"]
        self.logger.info(f"Skeptic agent reviewing research on: '{topic}'")

        # No notes — reject immediately, no LLM call needed
        if not state.get("research_notes"):
            state["skeptic_decision"] = AgentDecision.REJECT
            state["critic_feedback"].append("No research notes available — topic rejected")
            self.logger.warning("Rejecting topic: no research notes after all retries")
            return state

        # Step 1: Evaluate research quality
        quality_assessment = await self.evaluate_research_quality(state)
        
        if not quality_assessment:
            self.logger.error("Failed to assess research quality")
            state["skeptic_decision"] = AgentDecision.REJECT
            state["critic_feedback"].append("Failed to assess research quality")
            return state
        
        # Step 2: Check for hype and unsubstantiated claims
        hype_check = self.check_for_hype(state, quality_assessment)
        
        # Step 3: Validate evidence sufficiency
        evidence_check = self.validate_evidence(state)
        
        # Step 4: Make decision
        decision = self.make_decision(state, quality_assessment, hype_check, evidence_check)
        
        # Store rejection reason into memory
        if decision == AgentDecision.REJECT:
            concerns = quality_assessment.get("concerns", [])
            primary_reason = concerns[0] if concerns else "Did not meet quality threshold."
            self.memory.add_skeptic_reason(primary_reason)
        
        # Step 5: Generate feedback
        feedback = self.generate_feedback(quality_assessment, hype_check, evidence_check, decision)
        
        # Update state
        state["skeptic_decision"] = decision
        state["critic_feedback"].append(feedback)
        
        # Store metadata
        state["metadata"]["skeptic_assessment"] = {
            "quality": quality_assessment,
            "hype_check": hype_check,
            "evidence_check": evidence_check,
            "decision": decision
        }
        
        self.logger.info(f"Skeptic decision: {decision}")
        
        return state
    
    def get_routing_decision(self, state: NewsroomState) -> str:
        """
        Determine routing based on Skeptic's decision.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Next agent name
        """
        decision = state.get("skeptic_decision", AgentDecision.REJECT)
        
        if decision == AgentDecision.APPROVE:
            self.log_decision(
                AgentDecision.APPROVE,
                "Research quality meets standards, proceeding to Writer"
            )
            return "writer"
        
        elif decision == AgentDecision.NEED_MORE_EVIDENCE:
            self.log_decision(
                AgentDecision.NEED_MORE_EVIDENCE,
                "Insufficient evidence, sending back to Researcher"
            )
            return "researcher"
        
        else:  # REJECT
            self.log_decision(
                AgentDecision.REJECT,
                "Topic rejected, sending back to Scout for new topic"
            )
            return "scout"
    
    async def evaluate_research_quality(self, state: NewsroomState) -> Optional[Dict[str, Any]]:
        """
        Evaluate the quality of research using LLM.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Quality assessment or None if failed
        """
        try:
            # Prepare research summary
            research_summary = {
                "topic": state["topic"],
                "research_summary": state.get("research_summary", ""),
                "num_sources": len(state.get("research_notes", [])),
                "main_findings": [
                    note.get("claim", "") 
                    for note in state.get("research_notes", [])[:5]
                ]
            }
            
            # Load prompt template
            template = load_prompt_template("skeptic", "quality_review")
            
            if not template:
                # Fallback prompt
                template = """You are a pragmatic news editor evaluating research for a tech blog.

Research Summary:
{research_summary}

Evaluate:
1. **Evidence Quality**: Are claims reasonably supported?
2. **Source Credibility**: Are sources decent?
3. **Novelty**: Is this interesting or just repackaged press releases?
4. **Completeness**: Are there enough facts for a good blog post?

Return JSON:
```json
{{
  "evidence_quality": 0.0-1.0,
  "source_credibility": 0.0-1.0,
  "novelty_score": 0.0-1.0,
  "completeness": 0.0-1.0,
  "overall_quality": 0.0-1.0,
  "concerns": ["concern1", "concern2"],
  "strengths": ["strength1", "strength2"],
  "recommendation": "approve/reject/need_more_evidence"
}}
```"""
            
            prompt = format_prompt(
                template,
                research_summary=json.dumps(research_summary, indent=2),
                common_rejections="\n".join([f"- {r}" for r in self.memory.get_common_rejections(limit=5)]) or "None yet."
            )
            
            # Get LLM assessment
            config = get_config()
            assessment = await generate_structured_output(
                prompt=prompt,
                system_prompt="You are a pragmatic news editor. You want interesting content and reasonable evidence, but you do not require PhD-level academic rigor.",
                temperature=0.3,
                provider=config.llm.provider,
                model=config.llm.model
            )
            
            self.logger.info(f"Quality assessment: {assessment.get('overall_quality', 0):.2f}")
            return assessment
            
        except Exception as e:
            self.logger.error(f"Failed to evaluate research quality: {e}", exc_info=True)
            return None
    
    def check_for_hype(self, state: NewsroomState, quality_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if the topic is overhyped or unsubstantiated.
        
        Args:
            state: Current newsroom state
            quality_assessment: Quality assessment results
            
        Returns:
            Hype check results
        """
        try:
            # Simple hype detection based on quality assessment
            novelty = quality_assessment.get("novelty_score", 0.5)
            evidence = quality_assessment.get("evidence_quality", 0.5)
            
            # Hype indicators - more forgiving now
            is_hype = novelty > 0.9 and evidence < 0.4
            
            return {
                "is_likely_hype": is_hype,
                "novelty_vs_evidence_gap": novelty - evidence,
                "concerns": quality_assessment.get("concerns", [])
            }
            
        except Exception as e:
            self.logger.error(f"Failed to check for hype: {e}")
            return {"is_likely_hype": False, "concerns": []}
    
    def validate_evidence(self, state: NewsroomState) -> Dict[str, Any]:
        """
        Validate that there is sufficient evidence.
        
        Args:
            state: Current newsroom state
            
        Returns:
            Evidence validation results
        """
        research_notes = state.get("research_notes", [])
        
        # Check number of sources
        num_sources = len(research_notes)
        has_enough_sources = num_sources >= self.min_sources
        
        # Check credibility scores
        credibility_scores = [
            note.get("credibility_score", 0.5) 
            for note in research_notes
        ]
        avg_credibility = sum(credibility_scores) / len(credibility_scores) if credibility_scores else 0
        
        return {
            "num_sources": num_sources,
            "has_enough_sources": has_enough_sources,
            "avg_credibility": avg_credibility,
            "high_credibility_sources": sum(1 for s in credibility_scores if s >= 0.8)
        }
    
    def make_decision(
        self,
        state: NewsroomState,
        quality_assessment: Dict[str, Any],
        hype_check: Dict[str, Any],
        evidence_check: Dict[str, Any]
    ) -> str:
        """
        Make final decision based on all checks.
        
        Args:
            quality_assessment: Quality assessment results
            hype_check: Hype check results
            evidence_check: Evidence validation results
            
        Returns:
            Decision: APPROVE, REJECT, or NEED_MORE_EVIDENCE
        """
        overall_quality = quality_assessment.get("overall_quality", 0)
        is_hype = hype_check.get("is_likely_hype", False)
        has_enough_sources = evidence_check.get("has_enough_sources", False)
        
        # Decision logic
        if is_hype:
            return AgentDecision.REJECT
        
        if not has_enough_sources:
            return AgentDecision.NEED_MORE_EVIDENCE
        
        threshold = state.get("skeptic_threshold_override") or self.quality_threshold
        if overall_quality >= threshold:
            return AgentDecision.APPROVE
        
        if overall_quality >= 0.4:
            return AgentDecision.NEED_MORE_EVIDENCE
        
        return AgentDecision.REJECT
    
    def generate_feedback(
        self,
        quality_assessment: Dict[str, Any],
        hype_check: Dict[str, Any],
        evidence_check: Dict[str, Any],
        decision: str
    ) -> str:
        """
        Generate detailed feedback for the decision.
        
        Args:
            quality_assessment: Quality assessment results
            hype_check: Hype check results
            evidence_check: Evidence validation results
            decision: Final decision
            
        Returns:
            Feedback string
        """
        feedback_parts = []
        
        # Decision header
        feedback_parts.append(f"**Decision: {decision}**\n")
        
        # Quality summary
        quality = quality_assessment.get("overall_quality", 0)
        feedback_parts.append(f"Overall Quality Score: {quality:.2f}\n")
        
        # Concerns
        concerns = quality_assessment.get("concerns", [])
        if concerns:
            feedback_parts.append("\n**Concerns:**")
            for concern in concerns:
                feedback_parts.append(f"- {concern}")
        
        # Strengths
        strengths = quality_assessment.get("strengths", [])
        if strengths:
            feedback_parts.append("\n**Strengths:**")
            for strength in strengths:
                feedback_parts.append(f"- {strength}")
        
        # Evidence check
        num_sources = evidence_check.get("num_sources", 0)
        feedback_parts.append(f"\nSources: {num_sources} (minimum: {self.min_sources})")
        
        # Hype warning
        if hype_check.get("is_likely_hype"):
            feedback_parts.append("\n⚠️ **Warning:** This topic appears to be overhyped relative to available evidence.")
        
        # Action items
        if decision == AgentDecision.NEED_MORE_EVIDENCE:
            feedback_parts.append("\n**Action Required:**")
            feedback_parts.append("- Gather more credible sources")
            feedback_parts.append("- Strengthen evidence for key claims")
        
        return "\n".join(feedback_parts)
