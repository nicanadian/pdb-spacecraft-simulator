"""Disk-based caching for simulation artifacts."""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SimCache:
    """
    Disk-based cache for simulation artifacts.

    Caches geometry primitives like eclipse intervals, access windows,
    and rate-vs-elevation lookups.
    """

    def __init__(self, cache_dir: str = ".sim_cache", enabled: bool = True):
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache files
            enabled: Whether caching is enabled
        """
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled

        if enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self.enabled:
            return None

        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    data = pickle.load(f)
                logger.debug(f"Cache hit: {key}")
                return data
            except Exception as e:
                logger.warning(f"Cache read error: {e}")
                return None

        return None

    def set(self, key: str, value: Any) -> None:
        """
        Set cached value.

        Args:
            key: Cache key
            value: Value to cache
        """
        if not self.enabled:
            return

        cache_file = self.cache_dir / f"{key}.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(value, f)
            logger.debug(f"Cache set: {key}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    def invalidate(self, key: str) -> bool:
        """
        Invalidate cached value.

        Args:
            key: Cache key

        Returns:
            True if key was invalidated
        """
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            cache_file.unlink()
            return True
        return False

    def clear(self) -> int:
        """
        Clear all cached values.

        Returns:
            Number of items cleared
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
            count += 1
        return count

    def cached(self, func):
        """
        Decorator for caching function results.

        Usage:
            @cache.cached
            def expensive_function(x, y):
                ...
        """
        def wrapper(*args, **kwargs):
            key = self._generate_key(func.__name__, *args, **kwargs)
            result = self.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            self.set(key, result)
            return result
        return wrapper


# Global cache instance
_cache: Optional[SimCache] = None


def get_cache(cache_dir: str = ".sim_cache", enabled: bool = True) -> SimCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = SimCache(cache_dir=cache_dir, enabled=enabled)
    return _cache


def cache_key(
    spacecraft_id: str,
    epoch_start: datetime,
    epoch_end: datetime,
    config_hash: str,
) -> str:
    """
    Generate a cache key for geometry primitives.

    Args:
        spacecraft_id: Spacecraft identifier
        epoch_start: Start of epoch range
        epoch_end: End of epoch range
        config_hash: Configuration hash

    Returns:
        Cache key string
    """
    data = {
        "spacecraft_id": spacecraft_id,
        "epoch_start": epoch_start.isoformat(),
        "epoch_end": epoch_end.isoformat(),
        "config_hash": config_hash,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:32]
