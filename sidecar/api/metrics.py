"""
Prometheus Metrics for Swarm-It Sidecar

Exposes /metrics endpoint for Prometheus scraping.
"""

import time
from functools import wraps
from typing import Callable, Any

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


if PROMETHEUS_AVAILABLE:
    # === Counters ===

    CERTIFICATIONS_TOTAL = Counter(
        'swarm_it_certifications_total',
        'Total number of certification requests',
        ['decision']
    )

    VALIDATIONS_TOTAL = Counter(
        'swarm_it_validations_total',
        'Total number of validation submissions',
        ['type', 'failed']
    )

    AUDIT_REQUESTS_TOTAL = Counter(
        'swarm_it_audit_requests_total',
        'Total number of audit requests',
        ['format']
    )

    ERRORS_TOTAL = Counter(
        'swarm_it_errors_total',
        'Total number of errors',
        ['endpoint', 'error_type']
    )

    # === Histograms ===

    CERTIFICATION_LATENCY = Histogram(
        'swarm_it_certification_latency_seconds',
        'Certification request latency',
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
    )

    VALIDATION_LATENCY = Histogram(
        'swarm_it_validation_latency_seconds',
        'Validation request latency',
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
    )

    KAPPA_GATE_DISTRIBUTION = Histogram(
        'swarm_it_kappa_gate',
        'Distribution of kappa_gate values',
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    )

    NOISE_DISTRIBUTION = Histogram(
        'swarm_it_noise',
        'Distribution of N (noise) values',
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    )

    # === Gauges ===

    CERTIFICATES_STORED = Gauge(
        'swarm_it_certificates_stored',
        'Number of certificates currently stored'
    )

    CURRENT_THRESHOLDS = Gauge(
        'swarm_it_threshold',
        'Current threshold values',
        ['threshold_name']
    )

    FAILURE_RATE = Gauge(
        'swarm_it_failure_rate',
        'Current failure rate by validation type',
        ['type']
    )

    # === Info ===

    BUILD_INFO = Info(
        'swarm_it',
        'Swarm-It sidecar build information'
    )

    def init_metrics(version: str = "0.1.0"):
        """Initialize static metrics."""
        BUILD_INFO.info({
            'version': version,
            'service': 'swarm-it-sidecar',
        })

    def record_certification(cert: dict):
        """Record certification metrics."""
        decision = cert.get('decision', 'UNKNOWN')
        CERTIFICATIONS_TOTAL.labels(decision=decision).inc()
        KAPPA_GATE_DISTRIBUTION.observe(cert.get('kappa_gate', 0))
        NOISE_DISTRIBUTION.observe(cert.get('N', 0))

    def record_validation(validation_type: str, failed: bool):
        """Record validation metrics."""
        VALIDATIONS_TOTAL.labels(type=validation_type, failed=str(failed)).inc()

    def record_audit(format: str):
        """Record audit request."""
        AUDIT_REQUESTS_TOTAL.labels(format=format).inc()

    def record_error(endpoint: str, error_type: str):
        """Record error."""
        ERRORS_TOTAL.labels(endpoint=endpoint, error_type=error_type).inc()

    def update_store_gauge(count: int):
        """Update certificates stored gauge."""
        CERTIFICATES_STORED.set(count)

    def update_thresholds(thresholds: dict):
        """Update threshold gauges."""
        for name, value in thresholds.items():
            CURRENT_THRESHOLDS.labels(threshold_name=name).set(value)

    def update_failure_rates(rates: dict):
        """Update failure rate gauges."""
        for vtype, rate in rates.items():
            FAILURE_RATE.labels(type=vtype).set(rate)

    def timed(histogram):
        """Decorator to time a function with a histogram."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    histogram.observe(time.perf_counter() - start)

            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    histogram.observe(time.perf_counter() - start)

            if asyncio_iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        return decorator

    def get_metrics() -> bytes:
        """Generate Prometheus metrics output."""
        return generate_latest()

    def get_metrics_content_type() -> str:
        """Get content type for metrics response."""
        return CONTENT_TYPE_LATEST

    # Helper for checking if function is async
    import asyncio
    def asyncio_iscoroutinefunction(func):
        return asyncio.iscoroutinefunction(func)

else:
    # Stubs when prometheus_client not installed

    def init_metrics(version: str = "0.1.0"):
        pass

    def record_certification(cert: dict):
        pass

    def record_validation(validation_type: str, failed: bool):
        pass

    def record_audit(format: str):
        pass

    def record_error(endpoint: str, error_type: str):
        pass

    def update_store_gauge(count: int):
        pass

    def update_thresholds(thresholds: dict):
        pass

    def update_failure_rates(rates: dict):
        pass

    def timed(histogram):
        def decorator(func):
            return func
        return decorator

    def get_metrics() -> bytes:
        return b"# Prometheus metrics not available. Install prometheus_client."

    def get_metrics_content_type() -> str:
        return "text/plain"

    CERTIFICATION_LATENCY = None
    VALIDATION_LATENCY = None
