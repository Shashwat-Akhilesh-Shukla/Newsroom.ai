"""
Persistent Memory Layer for AI Newsroom.

This module provides a unified interface to store and retrieve historical data 
across multiple workflow runs, transforming the stateless pipeline into a learning 
system. It is backed by a simple JSON file for portability and ease of use.
"""

import json
import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default path relative to project root
DEFAULT_MEMORY_PATH = Path("data") / "system_memory.json"


class SystemMemory:
    """
    Singleton persistence manager for workflow memory.
    
    Tracks:
    - Rejected topics and reasons
    - Published topics and performance scores
    - Used sources (URLs)
    - Common skeptic rejection reasons
    """

    _instance = None

    def __new__(cls, file_path: Optional[str | Path] = None):
        if cls._instance is None:
            cls._instance = super(SystemMemory, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, file_path: Optional[str | Path] = None):
        if self._initialized:
            return
            
        self.file_path = Path(file_path) if file_path else DEFAULT_MEMORY_PATH
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.memory_data = {
            "rejected_topics": {},    # topic_title -> reason
            "published_topics": {},   # topic_title -> { metadata }
            "used_sources": {},       # url -> usage_count
            "skeptic_reasons": {}     # reason -> count
        }
        
        self._load()
        self._initialized = True
        logger.info(f"Initialized SystemMemory at {self.file_path}")

    def _load(self):
        """Load memory from disk."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # Merge data carefully to allow schema updates
                    for key in self.memory_data:
                        if key in data:
                            self.memory_data[key] = data[key]
            except Exception as e:
                logger.error(f"Failed to load system memory: {e}")

    def _save(self):
        """Save memory to disk."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.memory_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save system memory: {e}")

    # --- Topic Tracking ---

    def mark_topic_rejected(self, topic: str, reason: str):
        """Mark a topic as rejected."""
        if topic:
            topic_lower = topic.lower().strip()
            self.memory_data["rejected_topics"][topic_lower] = reason
            self._save()

    def mark_topic_published(self, topic: str, metadata: Optional[Dict[str, Any]] = None):
        """Mark a topic as successfully published."""
        if topic:
            topic_lower = topic.lower().strip()
            self.memory_data["published_topics"][topic_lower] = metadata or {}
            self._save()

    def is_topic_processed(self, topic: str) -> bool:
        """Check if a topic was already rejected or published."""
        if not topic:
            return False
        topic_lower = topic.lower().strip()
        return (topic_lower in self.memory_data["rejected_topics"] or 
                topic_lower in self.memory_data["published_topics"])

    def get_published_topics(self, limit: int = 10) -> List[str]:
        """Return recently published topics for LLM context."""
        topics = list(self.memory_data["published_topics"].keys())
        return topics[-limit:]

    # --- Source Tracking ---

    def add_used_source(self, url: str):
        """Record that a source URL was used."""
        if url:
            url_clean = url.strip().split("#")[0]  # Remove fragments
            current = self.memory_data["used_sources"].get(url_clean, 0)
            self.memory_data["used_sources"][url_clean] = current + 1
            self._save()

    def is_source_used(self, url: str) -> bool:
        """Check if a source URL was already used in a previous workflow."""
        if not url:
            return False
        url_clean = url.strip().split("#")[0]
        return url_clean in self.memory_data["used_sources"]

    # --- Skeptic Reasons ---

    def add_skeptic_reason(self, reason: str):
        """Record a common skeptic rejection reason."""
        if reason:
            current = self.memory_data["skeptic_reasons"].get(reason, 0)
            self.memory_data["skeptic_reasons"][reason] = current + 1
            self._save()

    def get_common_rejections(self, limit: int = 5) -> List[str]:
        """Get the most common skeptic rejection reasons."""
        reasons = self.memory_data["skeptic_reasons"]
        # Sort by count descending
        sorted_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)
        return [r[0] for r in sorted_reasons[:limit]]

    # --- Global Summary for Prompts ---

    def get_scout_memory_context(self) -> str:
        """Return a formatted string representing memory context for the Scout agent."""
        published = self.get_published_topics(limit=5)
        # Randomly sample some rejected topics to avoid bloating the prompt
        all_rejected = list(self.memory_data["rejected_topics"].keys())
        rejected = all_rejected[-5:] if len(all_rejected) > 0 else []

        context_lines = []
        if published:
            context_lines.append("Previously PUBLISHED (Successful) topics:")
            context_lines.extend([f"- {t}" for t in published])
        
        if rejected:
            context_lines.append("\nPreviously REJECTED (Failed) topics (DO NOT USE THESE):")
            for t in rejected:
                reason = self.memory_data["rejected_topics"].get(t, "Low quality")
                context_lines.append(f"- {t} (Reason: {reason})")
                
        if not context_lines:
            return "No previous memory. Proceed freely."

        return "\n".join(context_lines)
