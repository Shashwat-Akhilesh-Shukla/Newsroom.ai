"""
LLM utilities for AI Newsroom.

Provides utilities for interacting with LLMs, including:
- Client initialization (Gemini API) with LangSmith tracing callbacks
- Prompt template loading
- Token counting
- Response parsing
"""

import os
import json
import logging
import yaml
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# LLM Client Management
# ============================================================================

def get_llm_client(
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
    api_key: Optional[str] = None,
    run_name: Optional[str] = None,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    response_mime_type: Optional[str] = None,
):
    """
    Initialize and return an LLM client.

    Currently supports:
        - 'gemini': Google Gemini via langchain-google-genai.
          Requires GEMINI_API_KEY environment variable.
          Default model: gemini-2.5-flash

    LangSmith tracing is attached automatically when LANGCHAIN_TRACING_V2
    is set and the langsmith package is installed.

    Args:
        provider: LLM provider ('gemini')
        model: Model name (default: 'gemini-2.5-flash')
        api_key: API key (if not provided, will use environment variable)
        run_name: Optional span name shown in LangSmith (e.g. 'scout_analysis')

    Returns:
        LLM client instance
    """
    # Build optional LangSmith callback list
    callbacks = []
    try:
        from langsmith.callbacks import LangSmithCallbackHandler  # type: ignore
        from src.observability.tracing import is_tracing_enabled
        if is_tracing_enabled():
            callbacks.append(LangSmithCallbackHandler())
    except Exception:
        pass  # tracing not available — proceed without callbacks

    if provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "Gemini API key not found. Set GEMINI_API_KEY environment variable."
                )

            kwargs: Dict[str, Any] = {
                "model": model,
                "google_api_key": api_key,
                "temperature": temperature,
            }
            if max_output_tokens is not None:
                kwargs["max_output_tokens"] = max_output_tokens
            if response_mime_type is not None:
                kwargs["model_kwargs"] = {"response_mime_type": response_mime_type}
            if callbacks:
                kwargs["callbacks"] = callbacks
            return ChatGoogleGenerativeAI(**kwargs)
        except ImportError:
            raise ImportError(
                "langchain-google-genai not installed. Run: pip install langchain-google-genai"
            )

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. Only 'gemini' is currently supported."
        )


async def generate_completion(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
    run_name: Optional[str] = None,
    response_mime_type: Optional[str] = None,
) -> str:
    """
    Generate a completion from the LLM.

    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        provider: LLM provider
        model: Model name
        run_name: Optional span name in LangSmith (e.g. 'scout_topic_analysis')

    Returns:
        Generated text
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm_client(
            provider=provider,
            model=model,
            run_name=run_name,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type=response_mime_type,
        )

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        # Pass run_name so LangSmith labels the span with a readable name
        invoke_kwargs: Dict[str, Any] = {}
        if run_name:
            invoke_kwargs["run_name"] = run_name

        response = await llm.ainvoke(messages, **invoke_kwargs)
        return response.content

    except Exception as e:
        logger.error(f"Failed to generate completion: {e}")
        raise


async def generate_structured_output(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """
    Generate structured JSON output from the LLM.
    
    Args:
        prompt: User prompt (should request JSON output)
        system_prompt: Optional system prompt
        temperature: Sampling temperature
        provider: LLM provider
        model: Model name
        
    Returns:
        Parsed JSON response
    """
    response = await generate_completion(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
        model=model,
        response_mime_type="application/json"
    )
    
    return extract_json_from_response(response)


def extract_json_from_response(response: str) -> Dict[str, Any]:
    """
    Extract JSON from LLM response.
    
    Handles cases where JSON is wrapped in markdown code blocks.
    
    Args:
        response: LLM response text
        
    Returns:
        Parsed JSON object
    """
    # Remove markdown code blocks if present
    text = response.strip()
    
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    
    if text.endswith("```"):
        text = text[:-3]
    
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        logger.debug(f"Response text: {text}")
        raise


# ============================================================================
# Prompt Template Management
# ============================================================================

def load_prompt_template(agent_name: str, template_name: str) -> str:
    """
    Load a prompt template from the config file.
    
    Args:
        agent_name: Name of the agent (e.g., 'scout', 'researcher')
        template_name: Name of the template (e.g., 'topic_analysis')
        
    Returns:
        Prompt template string
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "agent_prompts.yaml"
    
    if not config_path.exists():
        logger.warning(f"Prompt config file not found: {config_path}")
        return ""
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            prompts = yaml.safe_load(f)
        
        if agent_name not in prompts:
            logger.warning(f"No prompts found for agent: {agent_name}")
            return ""
        
        if template_name not in prompts[agent_name]:
            logger.warning(f"Template '{template_name}' not found for agent '{agent_name}'")
            return ""
        
        return prompts[agent_name][template_name]
        
    except Exception as e:
        logger.error(f"Failed to load prompt template: {e}")
        return ""


def format_prompt(template: str, **kwargs) -> str:
    """
    Format a prompt template with variables.
    
    Args:
        template: Prompt template with {variable} placeholders
        **kwargs: Variables to substitute
        
    Returns:
        Formatted prompt
    """
    try:
        return template.replace("{topic_data}", kwargs["topic_data"])
    except KeyError as e:
        logger.error(f"Missing variable in prompt template: {e}")
        raise


# ============================================================================
# Token Counting
# ============================================================================

def count_tokens(text: str, model: str = "gemini-2.5-flash") -> int:
    """
    Count tokens in text for a specific model.

    Uses cl100k_base encoding as a reasonable approximation for Gemini models.

    Args:
        text: Text to count tokens for
        model: Model name

    Returns:
        Approximate token count
    """
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    except ImportError:
        # Fallback: rough estimate (1 token ≈ 4 characters)
        logger.warning("tiktoken not installed. Using rough token estimate.")
        return len(text) // 4
    except Exception as e:
        logger.error(f"Failed to count tokens: {e}")
        return len(text) // 4


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "gemini-2.5-flash") -> float:
    """
    Estimate cost for LLM API call.

    Gemini pricing (approximate, per 1M tokens):
      - gemini-2.5-flash:       $0.075 input / $0.30 output
      - gemini-2.0-flash:       $0.075 input / $0.30 output
      - gemini-2.0-flash-lite:  $0.075 input / $0.30 output
      - gemini-1.5-pro:         $1.25 input  / $5.00 output
      - gemini-1.5-flash:       $0.075 input / $0.30 output

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name

    Returns:
        Estimated cost in USD
    """
    # Gemini pricing (per token)
    pricing = {
        "gemini-1.5-pro": {"input": 1.25 / 1_000_000, "output": 5.00 / 1_000_000},
        "gemini-1.5-flash": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
        "gemini-2.0-flash": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
        "gemini-2.5-flash": {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
    }

    # Find matching pricing (longest match wins)
    model_pricing = None
    for key in pricing:
        if key in model.lower():
            model_pricing = pricing[key]
            break

    if not model_pricing:
        logger.warning(f"Unknown model pricing: {model}. Defaulting to gemini-2.5-flash pricing.")
        model_pricing = pricing["gemini-2.5-flash"]

    input_cost = input_tokens * model_pricing["input"]
    output_cost = output_tokens * model_pricing["output"]

    return input_cost + output_cost


# ============================================================================
# Helper Functions
# ============================================================================

def create_topic_analysis_prompt(topic_data: Dict[str, Any]) -> str:
    """
    Create a prompt for analyzing a topic.
    
    Args:
        topic_data: Topic data from various sources
        
    Returns:
        Formatted prompt
    """
    template = load_prompt_template("scout", "topic_analysis")
    
    if not template:
        # Fallback template
        template = """Analyze the following topic and determine its relevance, novelty, and potential for a technical article.

Topic Data:
{topic_data}

Provide your analysis in JSON format with the following fields:
- relevance: float (0-1)
- novelty: float (0-1)
- technical_depth: float (0-1)
- audience_interest: float (0-1)
- reasoning: string

Respond with ONLY the JSON object, no additional text."""
    
    return format_prompt(template, topic_data=json.dumps(topic_data, indent=2))


def create_research_synthesis_prompt(topic: str, sources: List[Dict[str, Any]]) -> str:
    """
    Create a prompt for synthesizing research.
    
    Args:
        topic: Research topic
        sources: List of source materials
        
    Returns:
        Formatted prompt
    """
    template = load_prompt_template("researcher", "research_synthesis")
    
    if not template:
        # Fallback template
        template = """Synthesize research findings for the following topic.

Topic: {topic}

Sources:
{sources}

Extract key claims, supporting evidence, and citations. Structure your response as JSON with:
- main_claims: list of strings
- evidence: list of objects with {claim, source, credibility}
- open_questions: list of strings
- summary: string

Respond with ONLY the JSON object."""
    
    return format_prompt(
        template,
        topic=topic,
        sources=json.dumps(sources, indent=2)
    )
