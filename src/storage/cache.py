"""
Caching layer for performance optimization.

Implements in-memory caching with LRU eviction and TTL support.
Optional Redis backend support for production environments.
"""

import logging
import time
import hashlib
import json
from typing import Any, Optional, Callable, Dict, Tuple
from functools import wraps
from collections import OrderedDict
from threading import RLock
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a single cache entry with TTL support."""
    
    def __init__(self, value: Any, ttl: Optional[int] = None):
        """
        Initialize cache entry.
        
        Args:
            value: The cached value
            ttl: Time-to-live in seconds (None = no expiration)
        """
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.hits = 0
    
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl
    
    def get_age(self) -> float:
        """Get age of this entry in seconds."""
        return time.time() - self.created_at


class LRUCache:
    """
    Thread-safe LRU cache with TTL support.
    
    Features:
    - LRU (Least Recently Used) eviction
    - TTL (Time To Live) expiration
    - Size-based limits
    - Thread-safe operations
    - Cache statistics
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds (None = no expiration)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0
        
        logger.info(f"LRU Cache initialized: max_size={max_size}, default_ttl={default_ttl}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry.is_expired():
                self._expirations += 1
                self._misses += 1
                del self._cache[key]
                logger.debug(f"Cache expired: {key}")
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._hits += 1
            
            logger.debug(f"Cache hit: {key} (age={entry.get_age():.1f}s, hits={entry.hits})")
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (overrides default_ttl)
        """
        with self._lock:
            # Use provided TTL or default
            if ttl is None:
                ttl = self.default_ttl
            
            # Remove if already exists
            if key in self._cache:
                del self._cache[key]
            
            # Evict oldest if at capacity
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._evictions += 1
                logger.debug(f"Cache evicted (LRU): {oldest_key}")
            
            # Add new entry
            self._cache[key] = CacheEntry(value, ttl)
            logger.debug(f"Cache set: {key} (ttl={ttl})")
    
    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache deleted: {key}")
                return True
            return False
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")
    
    def invalidate_pattern(self, pattern: str):
        """
        Invalidate all keys matching a pattern.
        
        Args:
            pattern: String pattern to match (simple substring match)
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            logger.info(f"Cache invalidated: {len(keys_to_delete)} entries matching '{pattern}'")
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
                self._expirations += 1
            
            if expired_keys:
                logger.info(f"Cache cleanup: {len(expired_keys)} expired entries removed")
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'evictions': self._evictions,
                'expirations': self._expirations,
                'total_requests': total_requests
            }
    
    def __len__(self) -> int:
        """Get current cache size."""
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache (doesn't check expiration)."""
        return key in self._cache


class CacheManager:
    """
    High-level cache manager with structured key generation.
    
    Provides convenient methods for caching different types of data
    with appropriate TTLs and key structures.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        Initialize cache manager.
        
        Args:
            max_size: Maximum cache size
            default_ttl: Default TTL in seconds (1 hour)
        """
        self.cache = LRUCache(max_size=max_size, default_ttl=default_ttl)
        self.ttl_config = {
            'llm': 86400,      # 24 hours for LLM responses
            'api': 3600,       # 1 hour for API responses
            'research': 7200,  # 2 hours for research notes
            'rankings': 1800,  # 30 minutes for topic rankings
        }
        logger.info("Cache manager initialized")
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate cache key from prefix and arguments.
        
        Args:
            prefix: Key prefix (e.g., 'llm', 'api')
            *args: Positional arguments to hash
            **kwargs: Keyword arguments to hash
            
        Returns:
            Cache key string
        """
        # Combine all arguments
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        
        # Create hash of arguments
        key_json = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_json.encode()).hexdigest()[:16]
        
        return f"{prefix}:{key_hash}"
    
    # LLM Response Caching
    
    def cache_llm_response(self, model: str, prompt: str, response: str):
        """Cache LLM response."""
        key = self._make_key('llm', model=model, prompt=prompt)
        self.cache.set(key, response, ttl=self.ttl_config['llm'])
    
    def get_llm_response(self, model: str, prompt: str) -> Optional[str]:
        """Get cached LLM response."""
        key = self._make_key('llm', model=model, prompt=prompt)
        return self.cache.get(key)
    
    # API Response Caching
    
    def cache_api_response(self, service: str, endpoint: str, params: Dict, response: Any):
        """Cache API response."""
        key = self._make_key('api', service=service, endpoint=endpoint, params=params)
        self.cache.set(key, response, ttl=self.ttl_config['api'])
    
    def get_api_response(self, service: str, endpoint: str, params: Dict) -> Optional[Any]:
        """Get cached API response."""
        key = self._make_key('api', service=service, endpoint=endpoint, params=params)
        return self.cache.get(key)
    
    # Research Notes Caching
    
    def cache_research(self, topic_id: int, research_data: Any):
        """Cache research notes."""
        key = f"research:{topic_id}"
        self.cache.set(key, research_data, ttl=self.ttl_config['research'])
    
    def get_research(self, topic_id: int) -> Optional[Any]:
        """Get cached research notes."""
        key = f"research:{topic_id}"
        return self.cache.get(key)
    
    # Topic Rankings Caching
    
    def cache_rankings(self, rankings: Any):
        """Cache topic rankings."""
        key = f"rankings:{int(time.time() / 1800)}"  # 30-minute buckets
        self.cache.set(key, rankings, ttl=self.ttl_config['rankings'])
    
    def get_rankings(self) -> Optional[Any]:
        """Get cached topic rankings."""
        key = f"rankings:{int(time.time() / 1800)}"
        return self.cache.get(key)
    
    # Utility Methods
    
    def invalidate_topic(self, topic_id: int):
        """Invalidate all cache entries for a topic."""
        self.cache.invalidate_pattern(f":{topic_id}")
    
    def invalidate_service(self, service: str):
        """Invalidate all cache entries for an API service."""
        self.cache.invalidate_pattern(f"api:{service}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    def cleanup(self):
        """Clean up expired entries."""
        return self.cache.cleanup_expired()


# Decorator for caching function results

def cache_result(ttl: Optional[int] = None, key_prefix: str = 'func'):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
        
    Usage:
        @cache_result(ttl=3600, key_prefix='expensive_calc')
        def expensive_calculation(x, y):
            return x ** y
    """
    def decorator(func: Callable) -> Callable:
        cache = LRUCache(max_size=100, default_ttl=ttl)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = {
                'func': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            key_json = json.dumps(key_data, sort_keys=True, default=str)
            key_hash = hashlib.md5(key_json.encode()).hexdigest()[:16]
            cache_key = f"{key_prefix}:{key_hash}"
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Function cache hit: {func.__name__}")
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            logger.debug(f"Function cache miss: {func.__name__}")
            
            return result
        
        # Add cache management methods
        wrapper.cache_clear = cache.clear
        wrapper.cache_stats = cache.get_stats
        
        return wrapper
    
    return decorator


# Global cache instance (lazy initialization)
_cache_instance: Optional[CacheManager] = None


def get_cache(max_size: int = 1000, default_ttl: int = 3600) -> CacheManager:
    """
    Get or create global cache instance.
    
    Args:
        max_size: Maximum cache size (only used on first call)
        default_ttl: Default TTL in seconds (only used on first call)
    
    Returns:
        CacheManager instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager(max_size=max_size, default_ttl=default_ttl)
    return _cache_instance
