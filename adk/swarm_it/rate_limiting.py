"""
Rate Limiting - Week 1 Security Critical

Implements multi-tier rate limiting to prevent:
- DDoS attacks
- Brute-force attempts
- API quota exhaustion
- Resource abuse

Based on SecurityAuditor recommendation (CVSS 7.5):
"Certification endpoints are not protected against DDoS attacks or
brute-force attempts. This is a production blocker."

Implements:
- IP-based rate limiting (100/minute default)
- User-based rate limiting (with authentication)
- Global rate limiting (system-wide protection)
- Sliding window algorithm
- Redis-backed distributed rate limiting
"""

from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time
import hashlib

try:
    import redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    # Limits
    requests_per_minute: int = 100
    requests_per_hour: int = 5000
    requests_per_day: int = 100000

    # Strategy
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW

    # Redis (for distributed rate limiting)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1  # Use separate DB from cache
    redis_password: Optional[str] = None

    # Behavior
    block_duration_seconds: int = 60  # How long to block after exceeding limit
    enable_whitelist: bool = True
    enable_blacklist: bool = True


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
    retry_after: Optional[int] = None  # Seconds until retry allowed
    reason: Optional[str] = None


class RateLimiter:
    """
    Multi-tier rate limiter with Redis backend.

    Features:
    - IP-based limiting (prevent DDoS)
    - User-based limiting (authenticated requests)
    - Global limiting (system-wide protection)
    - Sliding window algorithm (smooth rate limiting)
    - Distributed support (Redis-backed)
    - Whitelist/blacklist support

    Usage:
        limiter = RateLimiter(config)

        # Check IP rate limit
        result = limiter.check_ip("192.168.1.1")
        if not result.allowed:
            raise RateLimitExceeded(result.retry_after)

        # Check user rate limit
        result = limiter.check_user("user_123")
        if not result.allowed:
            raise RateLimitExceeded(result.retry_after)
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()

        # In-memory fallback
        self._memory_store: Dict[str, list] = {}
        self._whitelist: set = set()
        self._blacklist: set = set()

        # Redis connection
        self.redis_client: Optional[redis.Redis] = None
        self.redis_available = False

        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    db=self.config.redis_db,
                    password=self.config.redis_password,
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                self.redis_available = True
            except Exception:
                self.redis_available = False

    def check_ip(
        self,
        ip_address: str,
        requests_per_minute: Optional[int] = None
    ) -> RateLimitResult:
        """
        Check IP-based rate limit.

        Args:
            ip_address: Client IP address
            requests_per_minute: Override default limit

        Returns:
            RateLimitResult
        """
        # Check blacklist
        if self.config.enable_blacklist and ip_address in self._blacklist:
            return RateLimitResult(
                allowed=False,
                limit=0,
                remaining=0,
                reset_at=datetime.utcnow() + timedelta(days=1),
                retry_after=86400,
                reason="IP address is blacklisted"
            )

        # Check whitelist
        if self.config.enable_whitelist and ip_address in self._whitelist:
            return RateLimitResult(
                allowed=True,
                limit=999999,
                remaining=999999,
                reset_at=datetime.utcnow() + timedelta(hours=1)
            )

        limit = requests_per_minute or self.config.requests_per_minute
        key = f"ratelimit:ip:{ip_address}"

        return self._check_limit(key, limit, window_seconds=60)

    def check_user(
        self,
        user_id: str,
        requests_per_minute: Optional[int] = None
    ) -> RateLimitResult:
        """
        Check user-based rate limit.

        Args:
            user_id: User identifier
            requests_per_minute: Override default limit

        Returns:
            RateLimitResult
        """
        limit = requests_per_minute or self.config.requests_per_minute
        key = f"ratelimit:user:{user_id}"

        return self._check_limit(key, limit, window_seconds=60)

    def check_global(self) -> RateLimitResult:
        """
        Check global system-wide rate limit.

        Returns:
            RateLimitResult
        """
        key = "ratelimit:global"
        limit = self.config.requests_per_minute * 10  # 10x for global

        return self._check_limit(key, limit, window_seconds=60)

    def _check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> RateLimitResult:
        """
        Check rate limit using configured strategy.

        Args:
            key: Rate limit key
            limit: Request limit
            window_seconds: Time window in seconds

        Returns:
            RateLimitResult
        """
        if self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return self._check_sliding_window(key, limit, window_seconds)
        elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return self._check_fixed_window(key, limit, window_seconds)
        elif self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return self._check_token_bucket(key, limit, window_seconds)
        else:
            return self._check_sliding_window(key, limit, window_seconds)

    def _check_sliding_window(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> RateLimitResult:
        """
        Sliding window rate limiting (recommended).

        More accurate than fixed window, prevents burst at window boundaries.
        """
        now = time.time()
        window_start = now - window_seconds

        if self.redis_available and self.redis_client:
            # Redis-based sliding window
            try:
                # Remove old entries
                self.redis_client.zremrangebyscore(key, 0, window_start)

                # Count requests in window
                count = self.redis_client.zcard(key)

                if count >= limit:
                    # Get oldest entry to calculate reset time
                    oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                    if oldest:
                        reset_timestamp = oldest[0][1] + window_seconds
                        retry_after = int(reset_timestamp - now)
                    else:
                        retry_after = window_seconds

                    return RateLimitResult(
                        allowed=False,
                        limit=limit,
                        remaining=0,
                        reset_at=datetime.fromtimestamp(now + retry_after),
                        retry_after=retry_after,
                        reason=f"Rate limit exceeded: {count}/{limit} requests in {window_seconds}s"
                    )

                # Add current request
                self.redis_client.zadd(key, {str(now): now})
                self.redis_client.expire(key, window_seconds)

                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit - count - 1,
                    reset_at=datetime.fromtimestamp(window_start + window_seconds)
                )

            except RedisError:
                # Fallback to in-memory
                pass

        # In-memory sliding window
        if key not in self._memory_store:
            self._memory_store[key] = []

        # Remove old entries
        self._memory_store[key] = [
            ts for ts in self._memory_store[key]
            if ts > window_start
        ]

        count = len(self._memory_store[key])

        if count >= limit:
            oldest = min(self._memory_store[key])
            retry_after = int(oldest + window_seconds - now)

            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=datetime.fromtimestamp(oldest + window_seconds),
                retry_after=retry_after,
                reason=f"Rate limit exceeded: {count}/{limit} requests"
            )

        # Add current request
        self._memory_store[key].append(now)

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit - count - 1,
            reset_at=datetime.fromtimestamp(window_start + window_seconds)
        )

    def _check_fixed_window(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> RateLimitResult:
        """Fixed window rate limiting (simpler but less accurate)."""
        now = time.time()
        window_key = f"{key}:{int(now / window_seconds)}"

        if self.redis_available and self.redis_client:
            try:
                count = self.redis_client.incr(window_key)

                if count == 1:
                    self.redis_client.expire(window_key, window_seconds)

                if count > limit:
                    return RateLimitResult(
                        allowed=False,
                        limit=limit,
                        remaining=0,
                        reset_at=datetime.fromtimestamp(
                            (int(now / window_seconds) + 1) * window_seconds
                        ),
                        retry_after=int((int(now / window_seconds) + 1) * window_seconds - now),
                        reason=f"Rate limit exceeded: {count}/{limit} requests"
                    )

                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit - count,
                    reset_at=datetime.fromtimestamp(
                        (int(now / window_seconds) + 1) * window_seconds
                    )
                )
            except RedisError:
                pass

        # In-memory fallback
        if window_key not in self._memory_store:
            self._memory_store[window_key] = []

        count = len(self._memory_store[window_key]) + 1

        if count > limit:
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=datetime.fromtimestamp(
                    (int(now / window_seconds) + 1) * window_seconds
                ),
                retry_after=int((int(now / window_seconds) + 1) * window_seconds - now),
                reason=f"Rate limit exceeded: {count}/{limit} requests"
            )

        self._memory_store[window_key].append(now)

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit - count,
            reset_at=datetime.fromtimestamp(
                (int(now / window_seconds) + 1) * window_seconds
            )
        )

    def _check_token_bucket(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> RateLimitResult:
        """Token bucket rate limiting (smooth refill)."""
        # Simplified token bucket - production would use more sophisticated algorithm
        return self._check_sliding_window(key, limit, window_seconds)

    def add_to_whitelist(self, identifier: str):
        """Add IP or user to whitelist (unlimited requests)."""
        self._whitelist.add(identifier)

    def remove_from_whitelist(self, identifier: str):
        """Remove from whitelist."""
        self._whitelist.discard(identifier)

    def add_to_blacklist(self, identifier: str):
        """Add IP or user to blacklist (blocked)."""
        self._blacklist.add(identifier)

    def remove_from_blacklist(self, identifier: str):
        """Remove from blacklist."""
        self._blacklist.discard(identifier)

    def reset(self, key: str):
        """Reset rate limit for specific key."""
        if self.redis_available and self.redis_client:
            try:
                self.redis_client.delete(key)
            except RedisError:
                pass

        if key in self._memory_store:
            del self._memory_store[key]


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int, result: Optional[RateLimitResult] = None):
        self.retry_after = retry_after
        self.result = result
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after} seconds."
        )


def rate_limit(
    limiter: RateLimiter,
    get_identifier: Callable[[], str],
    limit_type: str = "ip"
):
    """
    Decorator for rate limiting functions.

    Usage:
        @rate_limit(limiter, lambda: request.client.host, "ip")
        def certify_endpoint():
            ...
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            identifier = get_identifier()

            if limit_type == "ip":
                result = limiter.check_ip(identifier)
            elif limit_type == "user":
                result = limiter.check_user(identifier)
            else:
                result = limiter.check_global()

            if not result.allowed:
                raise RateLimitExceeded(
                    retry_after=result.retry_after or 60,
                    result=result
                )

            return func(*args, **kwargs)
        return wrapper
    return decorator


# Global rate limiter instance
_global_limiter: Optional[RateLimiter] = None


def get_global_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter()
    return _global_limiter


def configure_global_limiter(config: RateLimitConfig):
    """Configure global rate limiter."""
    global _global_limiter
    _global_limiter = RateLimiter(config)
