"""
Health Checks - Phase 4 Reliability Enhancement

Kubernetes-compatible health checks for:
- Liveness probes (is service alive?)
- Readiness probes (is service ready to accept traffic?)
- Dependency health (Redis, rotor, external APIs)

Expected improvements:
- Better orchestration
- Faster recovery from failures
- Service visibility
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
import time


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of health check."""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus
    checks: List[HealthCheckResult]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def is_ready(self) -> bool:
        """Check if system is ready to serve traffic."""
        return self.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

    @property
    def is_alive(self) -> bool:
        """Check if system is alive."""
        return self.status != HealthStatus.UNHEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "is_ready": self.is_ready,
            "is_alive": self.is_alive,
            "timestamp": self.timestamp,
            "checks": [asdict(check) for check in self.checks]
        }


class HealthChecker:
    """
    Health check coordinator.

    Manages health checks for all system components.

    Usage:
        checker = HealthChecker()

        # Register checks
        checker.register("redis", redis_health_check)
        checker.register("rotor", rotor_health_check)

        # Run all checks
        health = checker.check_all()

        # Kubernetes endpoints
        if health.is_alive:
            return 200  # Liveness
        if health.is_ready:
            return 200  # Readiness
    """

    def __init__(self):
        """Initialize health checker."""
        self._checks: Dict[str, Callable[[], HealthCheckResult]] = {}

    def register(self, name: str, check_func: Callable[[], HealthCheckResult]):
        """
        Register health check function.

        Args:
            name: Unique check name
            check_func: Function that returns HealthCheckResult
        """
        self._checks[name] = check_func

    def unregister(self, name: str):
        """Unregister health check."""
        if name in self._checks:
            del self._checks[name]

    def check(self, name: str) -> HealthCheckResult:
        """
        Run single health check.

        Args:
            name: Check name

        Returns:
            Health check result
        """
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check '{name}' not found"
            )

        try:
            start = time.time()
            result = self._checks[name]()
            if result.latency_ms is None:
                result.latency_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}"
            )

    def check_all(self) -> SystemHealth:
        """
        Run all health checks.

        Returns:
            Overall system health
        """
        results = []

        for name in self._checks:
            result = self.check(name)
            results.append(result)

        # Determine overall status
        if not results:
            overall_status = HealthStatus.HEALTHY
        elif any(r.status == HealthStatus.UNHEALTHY for r in results):
            overall_status = HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        return SystemHealth(
            status=overall_status,
            checks=results
        )


# Standard health checks

def redis_health_check(cache_client) -> HealthCheckResult:
    """
    Check Redis cache health.

    Args:
        cache_client: CacheClient instance

    Returns:
        Health check result
    """
    try:
        start = time.time()

        if cache_client.redis_available and cache_client.client:
            # Test ping
            cache_client.client.ping()

            # Get info
            info = cache_client.client.info()
            used_memory = info.get('used_memory_human', 'unknown')

            latency_ms = (time.time() - start) * 1000

            return HealthCheckResult(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis cache operational",
                latency_ms=latency_ms,
                details={
                    "used_memory": used_memory,
                    "connected_clients": info.get('connected_clients', 0)
                }
            )
        elif cache_client.enable_fallback:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.DEGRADED,
                message="Using in-memory fallback cache",
                details={
                    "fallback_size": len(cache_client._fallback_cache)
                }
            )
        else:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message="Redis unavailable and no fallback"
            )

    except Exception as e:
        return HealthCheckResult(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=f"Redis check failed: {str(e)}"
        )


def rotor_health_check(rotor) -> HealthCheckResult:
    """
    Check rotor model health.

    Args:
        rotor: Rotor instance

    Returns:
        Health check result
    """
    try:
        start = time.time()

        # Test inference with dummy input
        import torch
        dummy_input = torch.randn(1, 64)  # Batch of 1, embed_dim=64

        result = rotor(dummy_input)

        # Verify output
        if 'R' in result and 'S' in result and 'N' in result:
            latency_ms = (time.time() - start) * 1000

            return HealthCheckResult(
                name="rotor",
                status=HealthStatus.HEALTHY,
                message="Rotor model operational",
                latency_ms=latency_ms,
                details={
                    "test_R": float(result['R'][0]),
                    "test_S": float(result['S'][0]),
                    "test_N": float(result['N'][0])
                }
            )
        else:
            return HealthCheckResult(
                name="rotor",
                status=HealthStatus.UNHEALTHY,
                message="Rotor output invalid"
            )

    except Exception as e:
        return HealthCheckResult(
            name="rotor",
            status=HealthStatus.UNHEALTHY,
            message=f"Rotor check failed: {str(e)}"
        )


def api_key_health_check(api_key: Optional[str]) -> HealthCheckResult:
    """
    Check API key availability.

    Args:
        api_key: API key to check

    Returns:
        Health check result
    """
    if api_key and len(api_key) > 0:
        return HealthCheckResult(
            name="api_key",
            status=HealthStatus.HEALTHY,
            message="API key configured"
        )
    else:
        return HealthCheckResult(
            name="api_key",
            status=HealthStatus.DEGRADED,
            message="API key not configured (BYOK mode required)"
        )


def memory_health_check(threshold_percent: float = 90.0) -> HealthCheckResult:
    """
    Check system memory usage.

    Args:
        threshold_percent: Unhealthy threshold (default: 90%)

    Returns:
        Health check result
    """
    try:
        import psutil

        memory = psutil.virtual_memory()
        percent_used = memory.percent

        if percent_used < threshold_percent:
            status = HealthStatus.HEALTHY
            message = f"Memory usage: {percent_used:.1f}%"
        elif percent_used < 95.0:
            status = HealthStatus.DEGRADED
            message = f"High memory usage: {percent_used:.1f}%"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Critical memory usage: {percent_used:.1f}%"

        return HealthCheckResult(
            name="memory",
            status=status,
            message=message,
            details={
                "percent_used": percent_used,
                "available_mb": memory.available // (1024 * 1024),
                "total_mb": memory.total // (1024 * 1024)
            }
        )

    except ImportError:
        return HealthCheckResult(
            name="memory",
            status=HealthStatus.DEGRADED,
            message="psutil not installed, cannot check memory"
        )
    except Exception as e:
        return HealthCheckResult(
            name="memory",
            status=HealthStatus.UNHEALTHY,
            message=f"Memory check failed: {str(e)}"
        )


def disk_health_check(path: str = "/", threshold_percent: float = 90.0) -> HealthCheckResult:
    """
    Check disk usage.

    Args:
        path: Path to check (default: /)
        threshold_percent: Unhealthy threshold (default: 90%)

    Returns:
        Health check result
    """
    try:
        import psutil

        disk = psutil.disk_usage(path)
        percent_used = disk.percent

        if percent_used < threshold_percent:
            status = HealthStatus.HEALTHY
            message = f"Disk usage: {percent_used:.1f}%"
        elif percent_used < 95.0:
            status = HealthStatus.DEGRADED
            message = f"High disk usage: {percent_used:.1f}%"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Critical disk usage: {percent_used:.1f}%"

        return HealthCheckResult(
            name="disk",
            status=status,
            message=message,
            details={
                "percent_used": percent_used,
                "free_gb": disk.free // (1024 ** 3),
                "total_gb": disk.total // (1024 ** 3)
            }
        )

    except ImportError:
        return HealthCheckResult(
            name="disk",
            status=HealthStatus.DEGRADED,
            message="psutil not installed, cannot check disk"
        )
    except Exception as e:
        return HealthCheckResult(
            name="disk",
            status=HealthStatus.UNHEALTHY,
            message=f"Disk check failed: {str(e)}"
        )


# Convenience functions

def create_standard_checker(
    cache_client=None,
    rotor=None,
    api_key: Optional[str] = None
) -> HealthChecker:
    """
    Create health checker with standard checks.

    Args:
        cache_client: CacheClient instance
        rotor: Rotor instance
        api_key: API key

    Returns:
        Configured HealthChecker
    """
    checker = HealthChecker()

    # Redis check
    if cache_client:
        checker.register("redis", lambda: redis_health_check(cache_client))

    # Rotor check
    if rotor:
        checker.register("rotor", lambda: rotor_health_check(rotor))

    # API key check
    checker.register("api_key", lambda: api_key_health_check(api_key))

    # System checks
    checker.register("memory", memory_health_check)
    checker.register("disk", disk_health_check)

    return checker
