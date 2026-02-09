"""
Configuration management for AI Newsroom.

This module handles loading and validating configuration from environment
variables and config files.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Configuration manager for AI Newsroom."""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            env_file: Path to .env file (optional)
        """
        # Load environment variables
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        self._config = self._load_config()
        self._validate_required_keys()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        return {
            # LLM API Keys
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
            
            # External Service API Keys
            "twitter_api_key": os.getenv("TWITTER_API_KEY", ""),
            "twitter_api_secret": os.getenv("TWITTER_API_SECRET", ""),
            "twitter_access_token": os.getenv("TWITTER_ACCESS_TOKEN", ""),
            "twitter_access_secret": os.getenv("TWITTER_ACCESS_SECRET", ""),
            "github_token": os.getenv("GITHUB_TOKEN", ""),
            
            # Database Configuration
            "database_url": os.getenv("DATABASE_URL", "sqlite:///./newsroom.db"),
            
            # Redis Configuration
            "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            
            # Agent Configuration
            "scout_confidence_threshold": float(os.getenv("SCOUT_CONFIDENCE_THRESHOLD", "0.7")),
            "max_research_sources": int(os.getenv("MAX_RESEARCH_SOURCES", "10")),
            "max_revision_loops": int(os.getenv("MAX_REVISION_LOOPS", "3")),
            "skeptic_quality_threshold": float(os.getenv("SKEPTIC_QUALITY_THRESHOLD", "0.8")),
            
            # LLM Configuration
            "default_model": os.getenv("DEFAULT_MODEL", "gpt-4"),
            "scout_model": os.getenv("SCOUT_MODEL", "gpt-3.5-turbo"),
            "researcher_model": os.getenv("RESEARCHER_MODEL", "gpt-4"),
            "skeptic_model": os.getenv("SKEPTIC_MODEL", "gpt-4"),
            "writer_model": os.getenv("WRITER_MODEL", "gpt-4"),
            "editor_model": os.getenv("EDITOR_MODEL", "gpt-4"),
            "publisher_model": os.getenv("PUBLISHER_MODEL", "gpt-3.5-turbo"),
            
            # Publishing Configuration
            "medium_api_key": os.getenv("MEDIUM_API_KEY", ""),
            "medium_user_id": os.getenv("MEDIUM_USER_ID", ""),
            
            # Logging
            "log_level": os.getenv("LOG_LEVEL", "INFO"),
            "log_file": os.getenv("LOG_FILE", "logs/newsroom.log"),
            
            # Development
            "debug": os.getenv("DEBUG", "False").lower() == "true",
        }
    
    def _validate_required_keys(self):
        """Validate that required API keys are present."""
        required_keys = ["openai_api_key"]
        
        missing_keys = []
        for key in required_keys:
            if not self._config.get(key):
                missing_keys.append(key)
        
        if missing_keys:
            raise ValueError(
                f"Missing required configuration keys: {', '.join(missing_keys)}. "
                "Please set them in your .env file."
            )
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """
        Get configuration specific to an agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Dictionary of agent-specific configuration
        """
        return {
            "model": self._config.get(f"{agent_name}_model", self._config["default_model"]),
            "api_key": self._config["openai_api_key"],
            "debug": self._config["debug"],
        }
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()
    
    @property
    def is_debug(self) -> bool:
        """Check if debug mode is enabled."""
        return self._config["debug"]


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config(env_file: Optional[str] = None) -> Config:
    """
    Get the global configuration instance.
    
    Args:
        env_file: Path to .env file (optional, only used on first call)
        
    Returns:
        Config instance
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = Config(env_file)
    
    return _config_instance


def reload_config(env_file: Optional[str] = None):
    """
    Reload configuration from environment.
    
    Args:
        env_file: Path to .env file (optional)
    """
    global _config_instance
    _config_instance = Config(env_file)
