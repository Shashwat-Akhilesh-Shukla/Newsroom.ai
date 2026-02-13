"""
Storage layer for AI Newsroom.

Provides database persistence and caching functionality.
"""

from .database import (
    DatabaseManager,
    get_database,
    Topic,
    Research,
    Draft,
    Feedback,
    Publication,
    Base
)

from .cache import (
    CacheManager,
    get_cache,
    LRUCache,
    cache_result
)

__all__ = [
    # Database
    'DatabaseManager',
    'get_database',
    'Topic',
    'Research',
    'Draft',
    'Feedback',
    'Publication',
    'Base',
    # Cache
    'CacheManager',
    'get_cache',
    'LRUCache',
    'cache_result',
]
