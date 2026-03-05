"""
Circuit Breakers - Week 2-3 Reliability Critical

Implements circuit breaker pattern to prevent:
- Cascading failures
- Resource exhaustion
- Downstream service overload
- Long timeout chains

Based on ResilienceArchitect recommendation (Severity: High):
"Without circuit breakers, a single downstream failure takes down the
entire certification pipeline. This is the difference between a 5-minute
outage and a 5-hour outage."

Implements:
- Multi-state circuit breaker (closed, open, half-open)
- Configurable failure thresholds
- Automatic recovery attempts
- Fallback mechanisms
- Metrics tracking
"""

from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time
from functools import wraps


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Blocking requests (too many failures)
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    # Failure threshold
    failure_threshold: int = 5  # Open after N failures
    success_threshold: int = 2  # Close after N successes in half-open
    timeout_duration: float = 60.0  # Seconds to wait before half-open

    # Error detection
    failure_exception: tuple = (Exception,)  # Exceptions that count as failures
    timeout_exception: tuple = (TimeoutError,)  # Timeout exceptions

    # Monitoring
    window_size: int = 10  # Track last N requests
    minimum_throughput: int = 5  # Min requests before considering failure rate

    # Recovery
    enable_fallback: bool = True
    max_recovery_attempts: int = 3


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.utcnow)
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failure_count / self.total_calls


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, circuit_name: str, retry_after: float):
        self.circuit_name = circuit_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{circuit_name}' is OPEN. "
            f"Retry after {retry_after:.1f} seconds."
        )


class CircuitBreaker:
    """
    Circuit breaker implementation.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit tripped, requests fail immediately
    - HALF_OPEN: Testing recovery, limited requests allowed

    Transitions:
    - CLOSED → OPEN: After failure_threshold failures
    - OPEN → HALF_OPEN: After timeout_duration seconds
    - HALF_OPEN → CLOSED: After success_threshold successes
    - HALF_OPEN → OPEN: On any failure

    Usage:
        breaker = CircuitBreaker(
            name="openai_api",
            failure_threshold=5,
            timeout_duration=60.0
        )

        try:
            with breaker:
                result = call_openai_api()
        except CircuitBreakerError:
            # Circuit is open, use fallback
            result = use_cached_result()
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name (for logging/metrics)
            config: Circuit breaker configuration
            fallback: Optional fallback function when circuit is open
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback
        self.metrics = CircuitBreakerMetrics()

        # Recovery tracking
        self._recovery_attempts = 0
        self._open_since: Optional[datetime] = None

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self.metrics.state

    def __enter__(self):
        """Context manager entry."""
        self._check_state()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is None:
            # Success
            self._on_success()
            return False
        elif isinstance(exc_val, self.config.failure_exception):
            # Counted failure
            self._on_failure()
            return False  # Re-raise exception
        else:
            # Other exception (not counted as failure)
            return False

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        with self:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if self.config.enable_fallback and self.fallback:
                    return self.fallback(*args, **kwargs)
                raise

    def _check_state(self):
        """Check and update circuit state."""
        if self.metrics.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self._open_since:
                elapsed = (datetime.utcnow() - self._open_since).total_seconds()
                if elapsed >= self.config.timeout_duration:
                    # Try half-open
                    self._transition_to_half_open()
                else:
                    # Still open
                    retry_after = self.config.timeout_duration - elapsed
                    raise CircuitBreakerError(self.name, retry_after)
            else:
                raise CircuitBreakerError(self.name, self.config.timeout_duration)

        elif self.metrics.state == CircuitState.HALF_OPEN:
            # Allow limited requests through
            pass

    def _on_success(self):
        """Handle successful call."""
        self.metrics.success_count += 1
        self.metrics.total_calls += 1
        self.metrics.consecutive_successes += 1
        self.metrics.consecutive_failures = 0

        if self.metrics.state == CircuitState.HALF_OPEN:
            # Check if we can close circuit
            if self.metrics.consecutive_successes >= self.config.success_threshold:
                self._transition_to_closed()

    def _on_failure(self):
        """Handle failed call."""
        self.metrics.failure_count += 1
        self.metrics.total_calls += 1
        self.metrics.consecutive_failures += 1
        self.metrics.consecutive_successes = 0
        self.metrics.last_failure_time = datetime.utcnow()

        if self.metrics.state == CircuitState.CLOSED:
            # Check if we should open circuit
            if self.metrics.consecutive_failures >= self.config.failure_threshold:
                self._transition_to_open()

        elif self.metrics.state == CircuitState.HALF_OPEN:
            # Any failure in half-open immediately reopens circuit
            self._transition_to_open()

    def _transition_to_open(self):
        """Transition to OPEN state."""
        self.metrics.state = CircuitState.OPEN
        self.metrics.last_state_change = datetime.utcnow()
        self._open_since = datetime.utcnow()
        self._recovery_attempts = 0

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self.metrics.state = CircuitState.HALF_OPEN
        self.metrics.last_state_change = datetime.utcnow()
        self.metrics.consecutive_successes = 0
        self.metrics.consecutive_failures = 0
        self._recovery_attempts += 1

    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.metrics.state = CircuitState.CLOSED
        self.metrics.last_state_change = datetime.utcnow()
        self.metrics.consecutive_failures = 0
        self._open_since = None
        self._recovery_attempts = 0

    def reset(self):
        """Reset circuit breaker to initial state."""
        self.metrics = CircuitBreakerMetrics()
        self._open_since = None
        self._recovery_attempts = 0

    def force_open(self):
        """Manually open circuit breaker."""
        self._transition_to_open()

    def force_close(self):
        """Manually close circuit breaker."""
        self._transition_to_closed()

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self.metrics.state.value,
            "failure_count": self.metrics.failure_count,
            "success_count": self.metrics.success_count,
            "total_calls": self.metrics.total_calls,
            "failure_rate": self.metrics.failure_rate,
            "consecutive_failures": self.metrics.consecutive_failures,
            "consecutive_successes": self.metrics.consecutive_successes,
            "recovery_attempts": self._recovery_attempts,
            "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
            "last_state_change": self.metrics.last_state_change.isoformat()
        }


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout_duration: float = 60.0,
    fallback: Optional[Callable] = None
):
    """
    Decorator for circuit breaker pattern.

    Usage:
        @circuit_breaker("openai_api", failure_threshold=5)
        def call_openai():
            return openai.Completion.create(...)

        # With fallback
        def use_cache():
            return cached_result

        @circuit_breaker("openai_api", fallback=use_cache)
        def call_openai():
            return openai.Completion.create(...)
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        timeout_duration=timeout_duration
    )

    breaker = CircuitBreaker(name, config, fallback)

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        wrapper.circuit_breaker = breaker  # Expose breaker for testing
        return wrapper
    return decorator


# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create circuit breaker by name.

    Args:
        name: Circuit breaker name
        config: Configuration (only used if creating new breaker)

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def list_circuit_breakers() -> Dict[str, Dict[str, Any]]:
    """
    List all circuit breakers and their metrics.

    Returns:
        Dictionary of {name: metrics}
    """
    return {
        name: breaker.get_metrics()
        for name, breaker in _circuit_breakers.items()
    }


def reset_all_circuit_breakers():
    """Reset all circuit breakers to initial state."""
    for breaker in _circuit_breakers.values():
        breaker.reset()


# Common circuit breaker configurations

OPENAI_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=2,
    timeout_duration=60.0,
    minimum_throughput=10
)

DOWNSTREAM_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    success_threshold=2,
    timeout_duration=30.0,
    minimum_throughput=5
)

DATABASE_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=10,
    success_threshold=3,
    timeout_duration=120.0,
    minimum_throughput=20
)
