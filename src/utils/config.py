"""
Configuration management for AI Newsroom.

Loads configuration from environment variables and provides
validated access to settings.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM configuration settings."""
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    temperature: float = 0.7
    max_tokens: int = 2000
    api_key: Optional[str] = None


@dataclass
class AgentConfig:
    """Agent-specific configuration settings."""
    scout_confidence_threshold: float = 0.7
    max_scout_iterations: int = 3
    max_research_sources: int = 10
    max_revision_loops: int = 3


@dataclass
class APIConfig:
    """External API configuration."""
    # No paid API keys needed — Reddit and DuckDuckGo are used instead.
    pass


@dataclass
class CacheConfig:
    """Caching configuration."""
    enable_cache: bool = True
    cache_ttl_hours: int = 24


class Config:
    """Main configuration class."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.llm = self._load_llm_config()
        self.agents = self._load_agent_config()
        self.apis = self._load_api_config()
        self.cache = self._load_cache_config()
        
        self._validate_config()
    
    def _load_llm_config(self) -> LLMConfig:
        """Load LLM configuration from environment."""
        return LLMConfig(
            provider=os.getenv("LLM_PROVIDER", "gemini"),
            model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
            api_key=os.getenv("GEMINI_API_KEY"),
        )
    
    def _load_agent_config(self) -> AgentConfig:
        """Load agent configuration from environment."""
        return AgentConfig(
            scout_confidence_threshold=float(os.getenv("SCOUT_CONFIDENCE_THRESHOLD", "0.7")),
            max_scout_iterations=int(os.getenv("MAX_SCOUT_ITERATIONS", "3")),
            max_research_sources=int(os.getenv("MAX_RESEARCH_SOURCES", "10")),
            max_revision_loops=int(os.getenv("MAX_REVISION_LOOPS", "3"))
        )
    
    def _load_api_config(self) -> APIConfig:
        """Load API configuration from environment."""
        return APIConfig()
    
    def _load_cache_config(self) -> CacheConfig:
        """Load cache configuration from environment."""
        return CacheConfig(
            enable_cache=os.getenv("ENABLE_CACHE", "true").lower() == "true",
            cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "24"))
        )
    
    def _validate_config(self):
        """Validate required configuration."""
        if not self.llm.api_key:
            logger.warning("No LLM API key found. Set GEMINI_API_KEY environment variable.")

        if self.agents.scout_confidence_threshold < 0 or self.agents.scout_confidence_threshold > 1:
            raise ValueError("SCOUT_CONFIDENCE_THRESHOLD must be between 0 and 1")

        logger.info(f"Configuration loaded: LLM={self.llm.provider}/{self.llm.model}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens
            },
            "agents": {
                "scout_confidence_threshold": self.agents.scout_confidence_threshold,
                "max_scout_iterations": self.agents.max_scout_iterations,
                "max_research_sources": self.agents.max_research_sources,
                "max_revision_loops": self.agents.max_revision_loops
            },
            "apis": {},
            "cache": {
                "enable_cache": self.cache.enable_cache,
                "cache_ttl_hours": self.cache.cache_ttl_hours
            }
        }


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config():
    """Reload configuration from environment."""
    global _config
    _config = Config()
    return _config
