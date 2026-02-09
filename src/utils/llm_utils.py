"""
LLM utilities for AI Newsroom.

This module provides utilities for interacting with LLMs:
- LLM initialization and management
- Prompt template handling
- Token counting and cost tracking
- Retry logic with exponential backoff
"""

import time
import logging
from typing import Dict, Any, Optional, List
from functools import wraps

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.callbacks import get_openai_callback

logger = logging.getLogger(__name__)


class LLMManager:
    """Manager for LLM interactions."""
    
    def __init__(self, api_key: str, model: str = "gpt-4", temperature: float = 0.7):
        """
        Initialize LLM manager.
        
        Args:
            api_key: OpenAI API key
            model: Model name
            temperature: Temperature for generation
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.llm = self._initialize_llm()
        self.total_tokens = 0
        self.total_cost = 0.0
        
    def _initialize_llm(self) -> ChatOpenAI:
        """Initialize the LLM client."""
        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
        )
    
    def invoke(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> str:
        """
        Invoke the LLM with retry logic.
        
        Args:
            system_prompt: System message
            user_prompt: User message
            max_retries: Maximum number of retries
            retry_delay: Initial delay between retries (exponential backoff)
            
        Returns:
            LLM response text
            
        Raises:
            Exception: If all retries fail
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        for attempt in range(max_retries):
            try:
                with get_openai_callback() as cb:
                    response = self.llm.invoke(messages)
                    
                    # Track usage
                    self.total_tokens += cb.total_tokens
                    self.total_cost += cb.total_cost
                    
                    logger.info(
                        f"LLM call successful | Tokens: {cb.total_tokens} | "
                        f"Cost: ${cb.total_cost:.4f}"
                    )
                    
                    return response.content
                    
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff
                    delay = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error("All LLM retry attempts failed")
                    raise
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics.
        
        Returns:
            Dictionary with token count and cost
        """
        return {
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "model": self.model
        }


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts")
                        raise
        return wrapper
    return decorator


class PromptTemplate:
    """Simple prompt template manager."""
    
    def __init__(self, template: str):
        """
        Initialize prompt template.
        
        Args:
            template: Template string with {placeholders}
        """
        self.template = template
    
    def format(self, **kwargs) -> str:
        """
        Format the template with provided values.
        
        Args:
            **kwargs: Values to fill in placeholders
            
        Returns:
            Formatted prompt
        """
        return self.template.format(**kwargs)


# Common prompt templates
SCOUT_SYSTEM_PROMPT = """You are a Trend Scout agent for an AI newsroom.

Your job is to identify trending topics in AI, technology, and research that would make compelling articles.

Evaluate topics based on:
1. Novelty: Is this genuinely new or just hype?
2. Relevance: Does this matter to a technical audience?
3. Engagement: Is there active discussion around this?

Provide a confidence score (0-1) for each topic."""

RESEARCHER_SYSTEM_PROMPT = """You are a Research agent for an AI newsroom.

Your job is to conduct deep research on approved topics and gather high-quality information with citations.

For each topic:
1. Find authoritative sources (papers, documentation, expert blogs)
2. Extract key claims and findings
3. Provide proper citations with URLs
4. Assess source credibility

Be thorough and objective. Do NOT make relevance judgments - that's the Skeptic's job."""

SKEPTIC_SYSTEM_PROMPT = """You are a Skeptic agent for an AI newsroom.

Your job is to challenge research and filter out low-quality or irrelevant topics.

Evaluate research based on:
1. Evidence quality: Are claims well-supported?
2. Source credibility: Are sources authoritative?
3. Relevance: Does this warrant an article?
4. Novelty: Is this genuinely new information?

You can:
- APPROVE: Research is solid, proceed to writing
- REJECT: Topic is not worth pursuing
- NEED_MORE_EVIDENCE: Research is incomplete, needs more investigation

Be critical but fair."""

WRITER_SYSTEM_PROMPT = """You are a Writer agent for an AI newsroom.

Your job is to create engaging, accurate articles based on approved research.

Guidelines:
1. Write in a clear, professional tone
2. Use the inverted pyramid structure
3. Include all key findings from research
4. Cite sources appropriately
5. Make technical content accessible

Create a complete draft ready for editorial review."""

EDITOR_SYSTEM_PROMPT = """You are an Editor agent for an AI newsroom.

Your job is to review drafts with a critical eye and ensure quality.

Check for:
1. Accuracy: Are all claims supported by research?
2. Clarity: Is the writing clear and well-structured?
3. Logic: Does the argument flow logically?
4. Style: Does it match our editorial standards?
5. Completeness: Are all key points covered?

You can:
- ACCEPT: Article is ready for publishing
- REWRITE: Article needs revision (provide specific feedback)
- FACT_CHECK: Specific claims need verification

Be thorough and demanding."""

PUBLISHER_SYSTEM_PROMPT = """You are a Publisher agent for an AI newsroom.

Your job is to perform final validation and prepare articles for publication.

Check:
1. SEO: Title, meta description, keywords
2. Formatting: Proper structure and readability
3. Duplicates: Not already published elsewhere
4. Platform requirements: Meets publishing platform standards

You can:
- PUBLISH: Article is ready to go live
- REJECT: Article has issues that need fixing

This is the final gate - be meticulous."""
