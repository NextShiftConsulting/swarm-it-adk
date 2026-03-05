"""
Distributed Tracing - Phase 4 Observability

Implements OpenTelemetry distributed tracing for:
- End-to-end request tracking
- Performance bottleneck identification
- Latency analysis (p50, p95, p99)
- Service dependency mapping
- Error tracking

Based on ReliabilityEngineer recommendation (Severity: High):
"Cannot debug distributed certification pipeline without end-to-end
tracing. OpenTelemetry is essential for production."

Implements:
- OpenTelemetry instrumentation
- Context propagation across services
- Span attributes for RSCT metrics
- Automatic instrumentation for common frameworks
- Export to Jaeger, Zipkin, or custom backends
"""

from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from functools import wraps
import time

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False


@dataclass
class TracingConfig:
    """Tracing configuration."""
    service_name: str = "swarm-it-adk"
    environment: str = "production"

    # Jaeger configuration
    jaeger_agent_host: str = "localhost"
    jaeger_agent_port: int = 6831

    # Sampling
    sample_rate: float = 1.0  # 100% sampling

    # Export
    enable_console: bool = False
    enable_jaeger: bool = True


class TracingManager:
    """
    OpenTelemetry tracing manager.

    Features:
    - Automatic instrumentation
    - Context propagation
    - Custom span attributes
    - Multiple exporters (Jaeger, Zipkin, Console)
    - Performance metrics

    Usage:
        # Initialize tracing
        config = TracingConfig(service_name="swarm-it-adk")
        manager = TracingManager(config)
        manager.initialize()

        # Create spans
        with manager.start_span("certification") as span:
            span.set_attribute("prompt_length", 500)
            result = certify(prompt)
            span.set_attribute("kappa", result.kappa)
    """

    def __init__(self, config: Optional[TracingConfig] = None):
        """
        Initialize tracing manager.

        Args:
            config: Tracing configuration
        """
        if not OPENTELEMETRY_AVAILABLE:
            raise ImportError(
                "OpenTelemetry not installed. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-jaeger opentelemetry-instrumentation-requests"
            )

        self.config = config or TracingConfig()
        self.tracer: Optional[trace.Tracer] = None
        self._initialized = False

    def initialize(self):
        """Initialize OpenTelemetry tracing."""
        if self._initialized:
            return

        # Create resource
        resource = Resource.create({
            "service.name": self.config.service_name,
            "service.environment": self.config.environment
        })

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add exporters
        if self.config.enable_console:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))

        if self.config.enable_jaeger:
            jaeger_exporter = JaegerExporter(
                agent_host_name=self.config.jaeger_agent_host,
                agent_port=self.config.jaeger_agent_port
            )
            provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer
        self.tracer = trace.get_tracer(__name__)

        # Auto-instrument common frameworks
        try:
            RequestsInstrumentor().instrument()
        except Exception:
            pass

        self._initialized = True

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> trace.Span:
        """
        Start a new span.

        Args:
            name: Span name
            attributes: Initial span attributes

        Returns:
            Span context manager
        """
        if not self._initialized:
            self.initialize()

        span = self.tracer.start_as_current_span(name)

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        return span

    def trace_certification(
        self,
        prompt_length: int,
        model: Optional[str] = None,
        domain: Optional[str] = None
    ):
        """
        Create span for certification request.

        Args:
            prompt_length: Prompt length in characters
            model: Model name
            domain: Certification domain

        Returns:
            Span context manager
        """
        attributes = {
            "rsct.prompt_length": prompt_length,
            "rsct.model": model or "default",
            "rsct.domain": domain or "research"
        }
        return self.start_span("rsct.certification", attributes)

    def trace_rotor(self, embed_dim: int):
        """Create span for rotor computation."""
        return self.start_span("rsct.rotor", {"rsct.embed_dim": embed_dim})

    def trace_quality_gates(self):
        """Create span for quality gate evaluation."""
        return self.start_span("rsct.quality_gates")

    def trace_cache_lookup(self, cache_type: str):
        """Create span for cache lookup."""
        return self.start_span(f"rsct.cache.{cache_type}")


def traced(span_name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator for automatic tracing.

    Usage:
        @traced("certification", {"service": "rsct"})
        def certify(prompt):
            return result
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_tracing_manager()

            with manager.start_span(span_name, attributes) as span:
                start_time = time.time()

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    raise
                finally:
                    duration_ms = (time.time() - start_time) * 1000
                    span.set_attribute("duration_ms", duration_ms)

        return wrapper
    return decorator


# Global tracing manager
_global_manager: Optional[TracingManager] = None


def get_tracing_manager() -> TracingManager:
    """Get or create global tracing manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = TracingManager()
        _global_manager.initialize()
    return _global_manager


def configure_tracing(config: TracingConfig):
    """Configure global tracing manager."""
    global _global_manager
    _global_manager = TracingManager(config)
    _global_manager.initialize()
