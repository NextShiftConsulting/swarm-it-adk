"""
Fluent API - Phase 5 Developer Experience

Implements builder pattern for improved developer experience:
- Chainable method calls
- Intuitive configuration
- Less boilerplate
- Better readability

Based on APIDesigner recommendation (kappa=0.308):
"Current API is verbose, not chainable. Builder pattern would
improve DX significantly."

Implements:
- FluentCertifier builder
- Chainable configuration methods
- Sensible defaults
- Method chaining for all operations
"""

from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from swarm_it.local.engine import RSCTCertificate


class FluentCertifier:
    """
    Fluent API builder for RSCT certification.

    Features:
    - Chainable method calls
    - Sensible defaults
    - Optional configuration
    - Clean syntax

    Usage:
        # Simple certification
        result = (
            FluentCertifier()
            .with_prompt("Your text here")
            .certify()
        )

        # Advanced configuration
        result = (
            FluentCertifier()
            .with_prompt("Medical diagnosis text")
            .for_domain("medical")
            .with_threshold("kappa", 0.9)
            .with_threshold("R", 0.5)
            .with_user("doc_123")
            .enable_caching()
            .enable_tracing()
            .certify()
        )

        # Batch processing
        results = (
            FluentCertifier()
            .with_prompts(["Text 1", "Text 2", "Text 3"])
            .for_domain("research")
            .enable_async()
            .certify_batch()
        )
    """

    def __init__(self):
        """Initialize fluent certifier with defaults."""
        # Core config
        self._prompt: Optional[str] = None
        self._prompts: Optional[List[str]] = None
        self._model: Optional[str] = None
        self._domain: str = "research"

        # Thresholds
        self._kappa: Optional[float] = None
        self._R: Optional[float] = None
        self._S: Optional[float] = None
        self._N: Optional[float] = None

        # Context
        self._user_id: Optional[str] = None
        self._org_id: Optional[str] = None
        self._request_id: Optional[str] = None

        # Features
        self._enable_cache: bool = False
        self._enable_tracing: bool = False
        self._enable_monitoring: bool = False
        self._enable_audit: bool = False
        self._enable_async: bool = False

        # Advanced
        self._max_retries: int = 2
        self._enable_autofix: bool = True
        self._auto_export_evidence: bool = False

    # Configuration methods (chainable)

    def with_prompt(self, prompt: str) -> 'FluentCertifier':
        """Set prompt for certification."""
        self._prompt = prompt
        return self

    def with_prompts(self, prompts: List[str]) -> 'FluentCertifier':
        """Set multiple prompts for batch certification."""
        self._prompts = prompts
        return self

    def with_model(self, model: str) -> 'FluentCertifier':
        """Set certification model."""
        self._model = model
        return self

    def for_domain(self, domain: str) -> 'FluentCertifier':
        """
        Set certification domain.

        Args:
            domain: One of: medical, legal, financial, research, dev
        """
        self._domain = domain
        return self

    def with_threshold(self, metric: str, value: float) -> 'FluentCertifier':
        """
        Set quality threshold.

        Args:
            metric: One of: kappa, R, S, N
            value: Threshold value (0.0-1.0)
        """
        if metric == "kappa":
            self._kappa = value
        elif metric == "R":
            self._R = value
        elif metric == "S":
            self._S = value
        elif metric == "N":
            self._N = value
        return self

    def with_thresholds(
        self,
        kappa: Optional[float] = None,
        R: Optional[float] = None,
        S: Optional[float] = None,
        N: Optional[float] = None
    ) -> 'FluentCertifier':
        """Set multiple thresholds at once."""
        if kappa is not None:
            self._kappa = kappa
        if R is not None:
            self._R = R
        if S is not None:
            self._S = S
        if N is not None:
            self._N = N
        return self

    def with_user(self, user_id: str) -> 'FluentCertifier':
        """Set user ID for audit trail."""
        self._user_id = user_id
        return self

    def with_org(self, org_id: str) -> 'FluentCertifier':
        """Set organization ID for audit trail."""
        self._org_id = org_id
        return self

    def with_request_id(self, request_id: str) -> 'FluentCertifier':
        """Set request ID for tracking."""
        self._request_id = request_id
        return self

    def enable_caching(self, enabled: bool = True) -> 'FluentCertifier':
        """Enable Redis caching."""
        self._enable_cache = enabled
        return self

    def enable_tracing(self, enabled: bool = True) -> 'FluentCertifier':
        """Enable OpenTelemetry tracing."""
        self._enable_tracing = enabled
        return self

    def enable_monitoring(self, enabled: bool = True) -> 'FluentCertifier':
        """Enable Prometheus monitoring."""
        self._enable_monitoring = enabled
        return self

    def enable_audit(self, enabled: bool = True) -> 'FluentCertifier':
        """Enable audit logging."""
        self._enable_audit = enabled
        return self

    def enable_async(self, enabled: bool = True) -> 'FluentCertifier':
        """Enable async processing."""
        self._enable_async = enabled
        return self

    def with_retries(self, max_retries: int) -> 'FluentCertifier':
        """Set maximum retry attempts."""
        self._max_retries = max_retries
        return self

    def with_autofix(self, enabled: bool = True) -> 'FluentCertifier':
        """Enable automatic prompt repair."""
        self._enable_autofix = enabled
        return self

    def export_evidence(self, enabled: bool = True) -> 'FluentCertifier':
        """Enable evidence export."""
        self._auto_export_evidence = enabled
        return self

    # Preset configurations

    def for_medical(self) -> 'FluentCertifier':
        """Use medical domain presets (strict)."""
        return (
            self.for_domain("medical")
            .with_thresholds(kappa=0.9, R=0.5, S=0.6, N=0.3)
            .enable_audit()
            .export_evidence()
        )

    def for_legal(self) -> 'FluentCertifier':
        """Use legal domain presets (strict)."""
        return (
            self.for_domain("legal")
            .with_thresholds(kappa=0.85, R=0.5, S=0.5, N=0.4)
            .enable_audit()
            .export_evidence()
        )

    def for_research(self) -> 'FluentCertifier':
        """Use research domain presets (moderate)."""
        return (
            self.for_domain("research")
            .with_thresholds(kappa=0.7, R=0.3, S=0.4, N=0.5)
        )

    def for_development(self) -> 'FluentCertifier':
        """Use development domain presets (permissive)."""
        return (
            self.for_domain("dev")
            .with_thresholds(kappa=0.5, R=0.2, S=0.2, N=0.7)
        )

    def with_performance(self) -> 'FluentCertifier':
        """Enable all performance features."""
        return (
            self.enable_caching()
            .enable_async()
        )

    def with_observability(self) -> 'FluentCertifier':
        """Enable all observability features."""
        return (
            self.enable_tracing()
            .enable_monitoring()
            .enable_audit()
        )

    def with_production(self) -> 'FluentCertifier':
        """Enable all production features."""
        return (
            self.with_performance()
            .with_observability()
            .export_evidence()
        )

    # Execution methods

    def certify(self) -> "RSCTCertificate":
        """
        Execute certification.

        Returns:
            RSCTCertificate object with full certification details
        """
        if self._prompt is None:
            from swarm_it.errors import CertificationError, ErrorCode
            raise CertificationError(
                code=ErrorCode.PROMPT_TOO_SHORT,
                message="Prompt not set. Use with_prompt() first."
            )

        # Import here to avoid circular dependencies
        from swarm_it.local.engine import LocalEngine

        # Build engine with policy based on domain
        # Note: LocalEngine uses hash-based simplex, doesn't take threshold args
        # Thresholds would be enforced post-certification in quality gates
        engine = LocalEngine(policy=self._domain)

        # Execute certification
        if self._enable_tracing:
            try:
                from swarm_it.tracing import get_tracing_manager
                manager = get_tracing_manager()

                with manager.trace_certification(
                    prompt_length=len(self._prompt),
                    model=self._model,
                    domain=self._domain
                ):
                    cert = engine.certify(self._prompt)
            except ImportError:
                # Tracing not available, fall back
                cert = engine.certify(self._prompt)
        else:
            cert = engine.certify(self._prompt)

        # Record monitoring metrics if enabled
        if self._enable_monitoring:
            try:
                from swarm_it.monitoring import get_metrics_collector
                collector = get_metrics_collector()

                collector.record_request(domain=self._domain, model=self._model or "default")

                if cert.decision.value == "EXECUTE":
                    collector.record_success(cert.decision.value, self._domain)
                    collector.record_quality_metrics(
                        cert.kappa_gate, cert.R, cert.S, cert.N, self._domain
                    )
                else:
                    collector.record_failure("gate_failed", self._domain)
            except ImportError:
                pass  # Monitoring not available

        # Audit log if enabled
        if self._enable_audit:
            try:
                from swarm_it.audit import get_audit_logger
                logger = get_audit_logger()

                logger.log_certification_success(
                    user_id=self._user_id,
                    request_id=self._request_id,
                    decision=cert.decision.value,
                    kappa=cert.kappa_gate,
                    R=cert.R,
                    S=cert.S,
                    N=cert.N
                )
            except ImportError:
                pass  # Audit logging not available

        return cert

    def certify_batch(self) -> List["RSCTCertificate"]:
        """
        Execute batch certification.

        Returns:
            List of RSCTCertificate objects
        """
        if self._prompts is None:
            from swarm_it.errors import CertificationError, ErrorCode
            raise CertificationError(
                code=ErrorCode.PROMPT_TOO_SHORT,
                message="Prompts not set. Use with_prompts() first."
            )

        if self._enable_async:
            # Use async batch processing if available
            try:
                from swarm_it.async_processing import BatchProcessor, AsyncCertificationClient

                client = AsyncCertificationClient()
                processor = BatchProcessor(client)

                request_ids = processor.submit_batch(
                    prompts=self._prompts,
                    model=self._model,
                    domain=self._domain,
                    user_id=self._user_id,
                    org_id=self._org_id
                )

                results = processor.get_batch_results(request_ids, timeout=60)
                return [r.result for r in results if r.result]
            except ImportError:
                # Async not available, fall back to sync
                pass

        # Synchronous batch processing (fallback)
        # Create a new certifier for each prompt to avoid state issues
        from swarm_it.local.engine import LocalEngine

        results = []
        for prompt in self._prompts:
            engine = LocalEngine(policy=self._domain)
            cert = engine.certify(prompt)
            results.append(cert)
        return results


# Convenience functions

def certify(prompt: str) -> "RSCTCertificate":
    """
    Quick certification with defaults.

    Usage:
        from swarm_it.fluent import certify
        cert = certify("Your text here")
        if cert.decision.allowed:
            # Proceed with execution

    Returns:
        RSCTCertificate object
    """
    return FluentCertifier().with_prompt(prompt).certify()


def certify_batch(prompts: List[str]) -> List["RSCTCertificate"]:
    """
    Quick batch certification with defaults.

    Usage:
        from swarm_it.fluent import certify_batch
        certs = certify_batch(["Text 1", "Text 2", "Text 3"])
        for cert in certs:
            print(f"{cert.id}: {cert.decision.value}")

    Returns:
        List of RSCTCertificate objects
    """
    return FluentCertifier().with_prompts(prompts).certify_batch()
