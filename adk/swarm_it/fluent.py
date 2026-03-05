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

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass


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

    def certify(self) -> Dict[str, Any]:
        """
        Execute certification.

        Returns:
            Certification result
        """
        if self._prompt is None:
            raise ValueError("Prompt not set. Use with_prompt() first.")

        # Import here to avoid circular dependencies
        from swarm_it_adk import RSCTCertifier

        # Build certifier
        certifier = RSCTCertifier(
            kappa=self._kappa,
            R=self._R,
            S=self._S,
            N=self._N
        )

        # Execute with tracing if enabled
        if self._enable_tracing:
            from swarm_it_adk.tracing import get_tracing_manager
            manager = get_tracing_manager()

            with manager.trace_certification(
                prompt_length=len(self._prompt),
                model=self._model,
                domain=self._domain
            ):
                result = certifier.certify(self._prompt)
        else:
            result = certifier.certify(self._prompt)

        # Record monitoring metrics if enabled
        if self._enable_monitoring:
            from swarm_it_adk.monitoring import get_metrics_collector
            collector = get_metrics_collector()

            collector.record_request(domain=self._domain, model=self._model or "default")

            if hasattr(result, 'decision') and result.decision == "EXECUTE":
                collector.record_success(result.decision, self._domain)
                if hasattr(result, 'kappa'):
                    collector.record_quality_metrics(
                        result.kappa, result.R, result.S, result.N, self._domain
                    )
            else:
                collector.record_failure("gate_failed", self._domain)

        # Audit log if enabled
        if self._enable_audit:
            from swarm_it_adk.audit import get_audit_logger
            logger = get_audit_logger()

            logger.log_certification_success(
                user_id=self._user_id,
                request_id=self._request_id,
                decision=result.decision if hasattr(result, 'decision') else None,
                kappa=result.kappa if hasattr(result, 'kappa') else None,
                R=result.R if hasattr(result, 'R') else None,
                S=result.S if hasattr(result, 'S') else None,
                N=result.N if hasattr(result, 'N') else None
            )

        return result

    def certify_batch(self) -> List[Dict[str, Any]]:
        """
        Execute batch certification.

        Returns:
            List of certification results
        """
        if self._prompts is None:
            raise ValueError("Prompts not set. Use with_prompts() first.")

        if self._enable_async:
            # Use async batch processing
            from swarm_it_adk.async_processing import BatchProcessor, AsyncCertificationClient

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
        else:
            # Synchronous batch processing
            return [
                self.with_prompt(prompt).certify()
                for prompt in self._prompts
            ]


# Convenience function

def certify(prompt: str) -> Dict[str, Any]:
    """
    Quick certification with defaults.

    Usage:
        result = certify("Your text here")
    """
    return FluentCertifier().with_prompt(prompt).certify()


def certify_batch(prompts: List[str]) -> List[Dict[str, Any]]:
    """
    Quick batch certification with defaults.

    Usage:
        results = certify_batch(["Text 1", "Text 2", "Text 3"])
    """
    return FluentCertifier().with_prompts(prompts).certify_batch()
