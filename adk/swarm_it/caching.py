"""
Multi-Layer Caching - Phase 2 Performance Optimization

Implements Redis-based caching for:
- L1: Rotor computation outputs (90% hit ratio target)
- L2: Model registry metadata (95% hit ratio target)

Expected improvements:
- 5x latency reduction (200ms → 40ms)
- 10x throughput increase (100 → 1000 certs/sec)
"""

from typing import Dict, Any, Optional, List, Callable
import json
import hashlib
from functools import wraps
from dataclasses import dataclass, asdict
import time

try:
    import redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass
class CacheConfig:
    """Cache configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: float = 5.0

    # TTLs (in seconds)
    rotor_ttl: int = 3600  # 1 hour
    model_ttl: int = 86400  # 24 hours

    # Eviction
    max_memory: str = "100mb"
    eviction_policy: str = "allkeys-lru"


class CacheMetrics:
    """Track cache performance metrics."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.latency_sum = 0.0
        self.latency_count = 0

    def record_hit(self, latency_ms: float):
        """Record cache hit."""
        self.hits += 1
        self.latency_sum += latency_ms
        self.latency_count += 1

    def record_miss(self):
        """Record cache miss."""
        self.misses += 1

    def record_error(self):
        """Record cache error."""
        self.errors += 1

    @property
    def hit_ratio(self) -> float:
        """Calculate hit ratio."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.latency_count == 0:
            return 0.0
        return self.latency_sum / self.latency_count

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "hit_ratio": self.hit_ratio,
            "avg_latency_ms": self.avg_latency_ms
        }


class CacheClient:
    """
    Multi-layer cache client with Redis backend.

    Features:
    - L1: Rotor computation cache (LRU eviction, 1h TTL)
    - L2: Model registry cache (TTL eviction, 24h TTL)
    - Automatic fallback if Redis unavailable
    - Performance metrics tracking

    Usage:
        config = CacheConfig(host="localhost", port=6379)
        cache = CacheClient(config)

        # Cache rotor result
        cache.set_rotor("key", {"R": 0.5, "S": 0.4, "N": 0.1})

        # Get rotor result
        result = cache.get_rotor("key")
    """

    def __init__(self, config: Optional[CacheConfig] = None, enable_fallback: bool = True):
        """
        Initialize cache client.

        Args:
            config: Cache configuration
            enable_fallback: Enable in-memory fallback if Redis unavailable
        """
        self.config = config or CacheConfig()
        self.enable_fallback = enable_fallback
        self.metrics = CacheMetrics()

        # In-memory fallback cache
        self._fallback_cache: Dict[str, Any] = {}

        # Try to connect to Redis
        self.client: Optional[redis.Redis] = None
        self.redis_available = False

        if REDIS_AVAILABLE:
            try:
                self.client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    socket_timeout=self.config.socket_timeout,
                    decode_responses=True
                )
                # Test connection
                self.client.ping()
                self.redis_available = True

                # Configure eviction policy
                self.client.config_set("maxmemory", self.config.max_memory)
                self.client.config_set("maxmemory-policy", self.config.eviction_policy)

            except Exception:
                self.redis_available = False
                if not self.enable_fallback:
                    raise

    def _make_key(self, prefix: str, identifier: str) -> str:
        """Generate cache key with prefix."""
        return f"{prefix}:{identifier}"

    def _hash_embedding(self, embedding: List[float]) -> str:
        """Hash embedding to create cache key."""
        # Convert to tuple for hashing
        embedding_bytes = json.dumps(embedding, sort_keys=True).encode()
        return hashlib.sha256(embedding_bytes).hexdigest()[:16]

    def set_rotor(self, embedding: List[float], result: Dict[str, float]) -> bool:
        """
        Cache rotor computation result.

        Args:
            embedding: Input embedding vector
            result: Rotor output {R, S, N, kappa, ...}

        Returns:
            True if cached successfully
        """
        key = self._make_key("rotor", self._hash_embedding(embedding))
        value = json.dumps(result)

        try:
            if self.redis_available and self.client:
                self.client.setex(key, self.config.rotor_ttl, value)
                return True
            elif self.enable_fallback:
                # In-memory fallback
                self._fallback_cache[key] = (value, time.time() + self.config.rotor_ttl)
                return True
            return False
        except RedisError:
            self.metrics.record_error()
            if self.enable_fallback:
                self._fallback_cache[key] = (value, time.time() + self.config.rotor_ttl)
                return True
            return False

    def get_rotor(self, embedding: List[float]) -> Optional[Dict[str, float]]:
        """
        Get cached rotor computation result.

        Args:
            embedding: Input embedding vector

        Returns:
            Cached result or None if not found
        """
        key = self._make_key("rotor", self._hash_embedding(embedding))
        start = time.time()

        try:
            if self.redis_available and self.client:
                value = self.client.get(key)
                if value:
                    latency_ms = (time.time() - start) * 1000
                    self.metrics.record_hit(latency_ms)
                    return json.loads(value)
                else:
                    self.metrics.record_miss()
                    return None
            elif self.enable_fallback:
                # In-memory fallback
                if key in self._fallback_cache:
                    value, expiry = self._fallback_cache[key]
                    if time.time() < expiry:
                        latency_ms = (time.time() - start) * 1000
                        self.metrics.record_hit(latency_ms)
                        return json.loads(value)
                    else:
                        # Expired
                        del self._fallback_cache[key]
                        self.metrics.record_miss()
                        return None
                self.metrics.record_miss()
                return None
            return None
        except RedisError:
            self.metrics.record_error()
            return None

    def set_model(self, model_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Cache model registry metadata.

        Args:
            model_id: Model identifier
            metadata: Model metadata

        Returns:
            True if cached successfully
        """
        key = self._make_key("model", model_id)
        value = json.dumps(metadata)

        try:
            if self.redis_available and self.client:
                self.client.setex(key, self.config.model_ttl, value)
                return True
            elif self.enable_fallback:
                self._fallback_cache[key] = (value, time.time() + self.config.model_ttl)
                return True
            return False
        except RedisError:
            self.metrics.record_error()
            if self.enable_fallback:
                self._fallback_cache[key] = (value, time.time() + self.config.model_ttl)
                return True
            return False

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached model registry metadata.

        Args:
            model_id: Model identifier

        Returns:
            Cached metadata or None if not found
        """
        key = self._make_key("model", model_id)
        start = time.time()

        try:
            if self.redis_available and self.client:
                value = self.client.get(key)
                if value:
                    latency_ms = (time.time() - start) * 1000
                    self.metrics.record_hit(latency_ms)
                    return json.loads(value)
                else:
                    self.metrics.record_miss()
                    return None
            elif self.enable_fallback:
                if key in self._fallback_cache:
                    value, expiry = self._fallback_cache[key]
                    if time.time() < expiry:
                        latency_ms = (time.time() - start) * 1000
                        self.metrics.record_hit(latency_ms)
                        return json.loads(value)
                    else:
                        del self._fallback_cache[key]
                        self.metrics.record_miss()
                        return None
                self.metrics.record_miss()
                return None
            return None
        except RedisError:
            self.metrics.record_error()
            return None

    def invalidate_rotor(self, embedding: List[float]) -> bool:
        """Invalidate cached rotor result."""
        key = self._make_key("rotor", self._hash_embedding(embedding))
        try:
            if self.redis_available and self.client:
                self.client.delete(key)
            if self.enable_fallback and key in self._fallback_cache:
                del self._fallback_cache[key]
            return True
        except RedisError:
            return False

    def invalidate_model(self, model_id: str) -> bool:
        """Invalidate cached model metadata."""
        key = self._make_key("model", model_id)
        try:
            if self.redis_available and self.client:
                self.client.delete(key)
            if self.enable_fallback and key in self._fallback_cache:
                del self._fallback_cache[key]
            return True
        except RedisError:
            return False

    def clear_all(self) -> bool:
        """Clear all cache entries."""
        try:
            if self.redis_available and self.client:
                self.client.flushdb()
            if self.enable_fallback:
                self._fallback_cache.clear()
            return True
        except RedisError:
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        return self.metrics.to_dict()


def cached_rotor(cache: CacheClient):
    """
    Decorator to cache rotor computation.

    Usage:
        @cached_rotor(cache_client)
        def compute_rotor(embedding):
            return {"R": 0.5, "S": 0.4, "N": 0.1}
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(embedding: List[float], *args, **kwargs):
            # Try cache first
            cached = cache.get_rotor(embedding)
            if cached is not None:
                return cached

            # Cache miss - compute
            result = func(embedding, *args, **kwargs)

            # Cache result
            cache.set_rotor(embedding, result)

            return result
        return wrapper
    return decorator


# Global cache instance (optional convenience)
_global_cache: Optional[CacheClient] = None


def get_global_cache() -> CacheClient:
    """Get or create global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheClient()
    return _global_cache


def configure_global_cache(config: CacheConfig):
    """Configure global cache instance."""
    global _global_cache
    _global_cache = CacheClient(config)
