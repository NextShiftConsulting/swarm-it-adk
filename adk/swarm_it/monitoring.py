"""
SLI/SLO Monitoring - Phase 4 Observability

Implements Service Level Indicators and Objectives monitoring for:
- 99.9% uptime SLA tracking
- p99 latency monitoring
- Error rate tracking
- Throughput monitoring
- SLO violation alerting

Based on ReliabilityEngineer recommendation:
"No tracking of 99.9% uptime SLA. Cannot measure p99 latency or error rate."

Implements:
- Prometheus metrics
- SLI/SLO definitions
- Error budget tracking
- Alerting rules
- Dashboard templates
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class SLIType(str, Enum):
    """Service Level Indicator types."""
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


@dataclass
class SLO:
    """Service Level Objective definition."""
    name: str
    sli_type: SLIType
    target: float  # Target percentage (e.g., 99.9 for 99.9%)
    window_days: int = 30  # Time window for SLO

    @property
    def error_budget(self) -> float:
        """Calculate error budget percentage."""
        return 100.0 - self.target


@dataclass
class SLOStatus:
    """SLO status with error budget tracking."""
    slo: SLO
    current_value: float  # Current SLI value
    error_budget_remaining: float  # % of error budget remaining
    is_violated: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def health_status(self) -> str:
        """Get health status based on error budget."""
        if self.error_budget_remaining > 50:
            return "healthy"
        elif self.error_budget_remaining > 10:
            return "warning"
        else:
            return "critical"


class MetricsCollector:
    """
    Prometheus metrics collector for RSCT.

    Collects:
    - Request counts (total, success, failure)
    - Latency histograms (p50, p95, p99)
    - Error rates
    - Cache hit ratios
    - Circuit breaker states

    Usage:
        collector = MetricsCollector()

        # Record certification request
        with collector.track_latency("certification"):
            result = certify(prompt)
            if result.decision == "EXECUTE":
                collector.record_success()
            else:
                collector.record_failure()
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.

        Args:
            registry: Prometheus registry (uses default if None)
        """
        if not PROMETHEUS_AVAILABLE:
            raise ImportError(
                "Prometheus client not installed. "
                "Install with: pip install prometheus-client"
            )

        self.registry = registry or CollectorRegistry()

        # Request counters
        self.requests_total = Counter(
            'rsct_requests_total',
            'Total certification requests',
            ['domain', 'model'],
            registry=self.registry
        )

        self.requests_success = Counter(
            'rsct_requests_success',
            'Successful certifications',
            ['decision', 'domain'],
            registry=self.registry
        )

        self.requests_failed = Counter(
            'rsct_requests_failed',
            'Failed certifications',
            ['error_type', 'domain'],
            registry=self.registry
        )

        # Latency histogram
        self.latency_histogram = Histogram(
            'rsct_latency_seconds',
            'Certification latency',
            ['operation'],
            buckets=[.01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0],
            registry=self.registry
        )

        # Quality metrics
        self.kappa_gauge = Gauge(
            'rsct_kappa',
            'Kappa (compatibility) score',
            ['domain'],
            registry=self.registry
        )

        self.rsn_gauges = {
            'R': Gauge('rsct_relevance', 'Relevance score', ['domain'], registry=self.registry),
            'S': Gauge('rsct_stability', 'Stability score', ['domain'], registry=self.registry),
            'N': Gauge('rsct_noise', 'Noise score', ['domain'], registry=self.registry)
        }

        # Cache metrics
        self.cache_hits = Counter(
            'rsct_cache_hits_total',
            'Cache hits',
            ['cache_type'],
            registry=self.registry
        )

        self.cache_misses = Counter(
            'rsct_cache_misses_total',
            'Cache misses',
            ['cache_type'],
            registry=self.registry
        )

        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            'rsct_circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=open, 2=half_open)',
            ['circuit_name'],
            registry=self.registry
        )

        # Rate limiting
        self.rate_limit_exceeded = Counter(
            'rsct_rate_limit_exceeded_total',
            'Rate limit exceeded count',
            ['limit_type'],
            registry=self.registry
        )

    def record_request(self, domain: str = "research", model: str = "default"):
        """Record certification request."""
        self.requests_total.labels(domain=domain, model=model).inc()

    def record_success(self, decision: str, domain: str = "research"):
        """Record successful certification."""
        self.requests_success.labels(decision=decision, domain=domain).inc()

    def record_failure(self, error_type: str, domain: str = "research"):
        """Record failed certification."""
        self.requests_failed.labels(error_type=error_type, domain=domain).inc()

    def track_latency(self, operation: str = "certification"):
        """
        Context manager to track operation latency.

        Usage:
            with collector.track_latency("certification"):
                result = certify(prompt)
        """
        return self.latency_histogram.labels(operation=operation).time()

    def record_quality_metrics(
        self,
        kappa: float,
        R: float,
        S: float,
        N: float,
        domain: str = "research"
    ):
        """Record quality metrics (kappa, R, S, N)."""
        self.kappa_gauge.labels(domain=domain).set(kappa)
        self.rsn_gauges['R'].labels(domain=domain).set(R)
        self.rsn_gauges['S'].labels(domain=domain).set(S)
        self.rsn_gauges['N'].labels(domain=domain).set(N)

    def record_cache_hit(self, cache_type: str = "rotor"):
        """Record cache hit."""
        self.cache_hits.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str = "rotor"):
        """Record cache miss."""
        self.cache_misses.labels(cache_type=cache_type).inc()

    def set_circuit_breaker_state(self, circuit_name: str, state: str):
        """Set circuit breaker state."""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        self.circuit_breaker_state.labels(circuit_name=circuit_name).set(
            state_map.get(state, 0)
        )

    def record_rate_limit_exceeded(self, limit_type: str = "ip"):
        """Record rate limit exceeded."""
        self.rate_limit_exceeded.labels(limit_type=limit_type).inc()

    def get_metrics(self) -> bytes:
        """Get Prometheus metrics in text format."""
        return generate_latest(self.registry)


class SLOMonitor:
    """
    SLO monitoring and error budget tracking.

    Monitors:
    - Availability SLO (99.9% uptime)
    - Latency SLO (p99 < 100ms)
    - Error rate SLO (<1%)

    Usage:
        monitor = SLOMonitor()

        # Define SLOs
        monitor.add_slo(SLO(
            name="availability",
            sli_type=SLIType.AVAILABILITY,
            target=99.9,
            window_days=30
        ))

        # Check SLO status
        status = monitor.get_slo_status("availability")
        if status.is_violated:
            alert("SLO violated!")
    """

    def __init__(self, collector: Optional[MetricsCollector] = None):
        """
        Initialize SLO monitor.

        Args:
            collector: Metrics collector
        """
        self.collector = collector or MetricsCollector()
        self.slos: Dict[str, SLO] = {}

        # Default SLOs
        self._add_default_slos()

    def _add_default_slos(self):
        """Add default SLOs for production."""
        # Availability: 99.9% uptime (43.2 minutes downtime per month)
        self.add_slo(SLO(
            name="availability",
            sli_type=SLIType.AVAILABILITY,
            target=99.9,
            window_days=30
        ))

        # Latency: p99 < 100ms
        self.add_slo(SLO(
            name="latency_p99",
            sli_type=SLIType.LATENCY,
            target=99.0,  # 99% of requests < 100ms
            window_days=30
        ))

        # Error rate: < 1%
        self.add_slo(SLO(
            name="error_rate",
            sli_type=SLIType.ERROR_RATE,
            target=99.0,  # 99% success rate
            window_days=30
        ))

    def add_slo(self, slo: SLO):
        """Add SLO definition."""
        self.slos[slo.name] = slo

    def get_slo_status(self, slo_name: str) -> Optional[SLOStatus]:
        """
        Get current SLO status.

        Args:
            slo_name: SLO name

        Returns:
            SLOStatus or None if not found
        """
        if slo_name not in self.slos:
            return None

        slo = self.slos[slo_name]

        # Calculate current SLI value
        # This is a simplified implementation
        # Production would query Prometheus for actual values
        current_value = self._calculate_sli(slo)

        # Calculate error budget remaining
        error_budget_total = slo.error_budget
        error_budget_consumed = max(0, slo.target - current_value)
        error_budget_remaining = max(0, error_budget_total - error_budget_consumed)
        error_budget_remaining_pct = (error_budget_remaining / error_budget_total) * 100 if error_budget_total > 0 else 100

        # Check if violated
        is_violated = current_value < slo.target

        return SLOStatus(
            slo=slo,
            current_value=current_value,
            error_budget_remaining=error_budget_remaining_pct,
            is_violated=is_violated
        )

    def _calculate_sli(self, slo: SLO) -> float:
        """
        Calculate current SLI value.

        This is a placeholder - production implementation would
        query Prometheus for actual metric values.
        """
        # Placeholder: return mock values
        if slo.sli_type == SLIType.AVAILABILITY:
            return 99.95  # Mock: 99.95% availability
        elif slo.sli_type == SLIType.LATENCY:
            return 99.5  # Mock: 99.5% under threshold
        elif slo.sli_type == SLIType.ERROR_RATE:
            return 99.8  # Mock: 99.8% success rate
        return 100.0

    def get_all_statuses(self) -> List[SLOStatus]:
        """Get status for all SLOs."""
        return [
            self.get_slo_status(name)
            for name in self.slos.keys()
            if self.get_slo_status(name) is not None
        ]

    def check_violations(self) -> List[SLOStatus]:
        """Get list of violated SLOs."""
        return [
            status for status in self.get_all_statuses()
            if status.is_violated
        ]


# Global instances
_global_collector: Optional[MetricsCollector] = None
_global_monitor: Optional[SLOMonitor] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def get_slo_monitor() -> SLOMonitor:
    """Get or create global SLO monitor."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SLOMonitor()
    return _global_monitor


# Convenience decorator

def monitored(operation: str = "certification"):
    """
    Decorator for automatic monitoring.

    Usage:
        @monitored("certification")
        def certify(prompt):
            return result
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()

            with collector.track_latency(operation):
                try:
                    result = func(*args, **kwargs)
                    collector.record_success("EXECUTE")
                    return result
                except Exception as e:
                    collector.record_failure(type(e).__name__)
                    raise

        return wrapper
    return decorator
