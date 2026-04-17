"""Simple caching utilities with TTL support."""
import time
from typing import Any, Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry with TTL."""
    
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.timestamp = time.time()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() - self.timestamp > self.ttl


class TTLCache:
    """Simple in-memory cache with time-to-live support."""
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self._cache:
            self.misses += 1
            return None
        
        entry = self._cache[key]
        
        if entry.is_expired():
            del self._cache[key]
            self.misses += 1
            return None
        
        self.hits += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default_ttl if not provided)
        """
        ttl = ttl or self.default_ttl
        self._cache[key] = CacheEntry(value, ttl)
        logger.debug(f"Cached '{key}' with TTL {ttl}s")
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False if key not found
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.debug("Cache cleared")
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "total_requests": total,
        }


class CacheKey:
    """Builder for cache keys."""
    
    @staticmethod
    def corpus_exists(corpus_name: str) -> str:
        return f"corpus_exists:{corpus_name}"
    
    @staticmethod
    def corpus_info(corpus_name: str) -> str:
        return f"corpus_info:{corpus_name}"
    
    @staticmethod
    def user_session(user_id: int) -> str:
        return f"user_session:{user_id}"
    
    @staticmethod
    def policy_check(user_id: int, action: str) -> str:
        return f"policy:{user_id}:{action}"
    
    @staticmethod
    def document_metadata(doc_id: str) -> str:
        return f"doc_metadata:{doc_id}"


# Global semantic cache instance for common operations
semantic_cache = TTLCache(default_ttl=300)



# Global cache instances
_cache_instance: Optional[TTLCache] = None


def get_cache(ttl: int = 300) -> TTLCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = TTLCache(default_ttl=ttl)
    return _cache_instance


def cached(ttl: int = 300):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time-to-live in seconds
    
    Example:
        @cached(ttl=600)
        def get_user_data(user_id: int):
            # Expensive operation
            return user_db.get(user_id)
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            cache = get_cache()
            
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value
            
            # Call original function
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator
