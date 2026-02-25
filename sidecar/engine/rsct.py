"""
RSCT Engine - Sidecar pre-screening layer.

First Principles (Tendermint model):
- Sidecar is domain-agnostic (like Tendermint Core)
- Sidecar handles: API, pre-screening, metrics, multi-language access
- yrsn core handles: RSN computation, certificate generation, domain semantics

This module ONLY does:
1. Pattern pre-screening (like Tendermint's CheckTx)
2. Delegation to yrsn adapter
3. Observability hooks

It does NOT compute R, S, N values - that's yrsn's job.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List

from .interface import (
    CertifyRequest,
    CertifyResponse,
    PreScreenResult,
    PreScreenOutput,
    YRSNAdapter,
)
from .patterns import get_detector, PatternMatch
from .yrsn_adapter import get_adapter
from .semantic import get_semantic_analyzer


class RSCTEngine:
    """
    RSCT Sidecar Engine.

    Thin layer that:
    1. Pre-screens for obvious attacks (pattern detection)
    2. Delegates to yrsn for actual RSN computation
    3. Provides observability hooks

    Does NOT implement domain logic - that's yrsn's job.
    """

    # Severity threshold for immediate rejection (don't even call yrsn)
    REJECT_SEVERITY = 0.9

    def __init__(
        self,
        use_mock: bool = False,
        embed_model: str = "text-embedding-3-small",
        rotor_checkpoint: Optional[str] = None,
    ):
        """
        Initialize sidecar engine.

        Args:
            use_mock: Use mock adapter (for testing without yrsn)
            embed_model: OpenAI embedding model for convenience wrapper
            rotor_checkpoint: Path to trained yrsn rotor checkpoint
        """
        # Pattern detector for pre-screening (regex-based)
        self.pattern_detector = get_detector()

        # Semantic analyzer (embedding-based - catches paraphrased attacks)
        self.semantic_analyzer = get_semantic_analyzer()

        # yrsn adapter for actual RSN computation
        self.adapter: YRSNAdapter = get_adapter(
            use_mock=use_mock,
            embed_model=embed_model,
            rotor_checkpoint=rotor_checkpoint,
        )

    def certify(
        self,
        prompt: str,
        embeddings: Optional[List[float]] = None,
        context: Optional[str] = None,
        model_id: Optional[str] = None,
        policy: str = "default",
    ) -> Dict[str, Any]:
        """
        Certify a prompt.

        Flow:
        1. Pre-screen (sidecar) - pattern detection
        2. If severe, reject immediately (don't call yrsn)
        3. Otherwise, delegate to yrsn for RSN computation
        4. Return certificate

        Args:
            prompt: The prompt to certify
            embeddings: Pre-computed embeddings (optional - yrsn will compute if missing)
            context: Additional context
            model_id: Target model identifier
            policy: Policy name

        Returns:
            Certificate dict
        """
        # Step 1: Pre-screen (sidecar's job - like Tendermint CheckTx)
        pre_screen = self._pre_screen(prompt)

        # Step 2: If severe pattern, reject without calling yrsn
        if pre_screen.result == PreScreenResult.REJECT:
            return self._reject_certificate(prompt, pre_screen)

        # Step 3: Build request and delegate to yrsn
        request = CertifyRequest(
            prompt=prompt,
            embeddings=embeddings,
            context=context,
            model_id=model_id,
            policy=policy,
            pre_screen=pre_screen,
        )

        # Step 4: yrsn computes RSN and returns certificate
        response = self.adapter.certify(request)

        # Step 5: Convert to dict for API compatibility
        return self._response_to_dict(response)

    def _pre_screen(self, prompt: str) -> PreScreenOutput:
        """
        Pre-screen prompt for obvious attacks.

        Two layers:
        1. Regex patterns (fast, catches known attacks)
        2. Semantic analysis (slower, catches paraphrased attacks)

        This is the sidecar's value-add - catching attacks
        before they hit yrsn (like Tendermint's CheckTx).
        """
        patterns = []
        max_severity = 0.0

        # Layer 1: Regex pattern detection (fast)
        matches = self.pattern_detector.detect(prompt)
        if matches:
            max_severity = matches[0].score
            patterns = [m.category for m in matches[:5]]

        # Layer 2: Semantic analysis (if available)
        semantic_result = None
        if self.semantic_analyzer.available:
            semantic_result = self.semantic_analyzer.analyze(prompt)
            if semantic_result.get("is_attack"):
                # Semantic analysis detected attack
                attack_sim = semantic_result.get("attack_similarity", 0)
                if attack_sim > max_severity:
                    max_severity = attack_sim
                semantic_cat = semantic_result.get("top_attack_match")
                if semantic_cat and semantic_cat.category not in patterns:
                    patterns.insert(0, f"semantic:{semantic_cat.category}")

        # No issues found
        if max_severity == 0:
            return PreScreenOutput(
                result=PreScreenResult.PASS,
                patterns=[],
                max_severity=0.0,
            )

        # Severe patterns = immediate rejection
        if max_severity >= self.REJECT_SEVERITY:
            severe_categories = {
                'jailbreak', 'xss', 'code_injection',
                'injection', 'fake_system', 'format_injection',
                'spam',  # High-score spam is also rejected
            }
            top_pattern = patterns[0] if patterns else "unknown"
            # Check both regex and semantic categories
            base_category = top_pattern.replace("semantic:", "")
            if base_category in severe_categories:
                return PreScreenOutput(
                    result=PreScreenResult.REJECT,
                    patterns=patterns,
                    max_severity=max_severity,
                    reason=f"Dangerous pattern: {top_pattern}",
                )

        # Semantic attack detection (even if regex didn't catch it)
        if semantic_result and semantic_result.get("is_attack"):
            confidence = semantic_result.get("confidence", 0)
            if confidence > 0.15:  # High confidence semantic attack
                return PreScreenOutput(
                    result=PreScreenResult.REJECT,
                    patterns=patterns,
                    max_severity=max_severity,
                    reason=f"Semantic attack detected (confidence={confidence:.2f})",
                )

        # Otherwise, pass to yrsn with warning
        return PreScreenOutput(
            result=PreScreenResult.WARN,
            patterns=patterns,
            max_severity=max_severity,
        )

    def _reject_certificate(
        self, prompt: str, pre_screen: PreScreenOutput
    ) -> Dict[str, Any]:
        """
        Create rejection certificate (sidecar rejected before yrsn).

        This is a sidecar-level rejection, not yrsn's gate decision.
        """
        import hashlib
        from datetime import datetime

        cert_id = hashlib.sha256(prompt[:100].encode()).hexdigest()[:16]

        return {
            "id": cert_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "R": 0.0,
            "S": 0.0,
            "N": 1.0,
            "kappa_gate": 0.0,
            "sigma": 1.0,
            "decision": "REJECT",
            "gate_reached": 0,  # Pre-gate (sidecar rejection)
            "reason": pre_screen.reason or "Pre-screen rejection",
            "allowed": False,
            "pattern_flags": pre_screen.patterns,
            "pre_screen_rejection": True,  # Flag that sidecar rejected
            "is_multimodal": False,
            "kappa_H": None,
            "kappa_L": None,
            "kappa_interface": None,
            "weak_modality": None,
        }

    def _response_to_dict(self, response: CertifyResponse) -> Dict[str, Any]:
        """Convert CertifyResponse to dict for API compatibility."""
        return {
            "id": response.id,
            "timestamp": response.timestamp,
            "R": response.R,
            "S": response.S,
            "N": response.N,
            "kappa_gate": response.kappa_gate,
            "sigma": response.sigma,
            "decision": response.decision,
            "gate_reached": response.gate_reached,
            "reason": response.reason,
            "allowed": response.allowed,
            "kappa_H": response.kappa_H,
            "kappa_L": response.kappa_L,
            "kappa_interface": response.kappa_interface,
            "weak_modality": response.weak_modality,
            "is_multimodal": response.is_multimodal,
            "pattern_flags": response.pattern_flags or [],
            "pre_screen_rejection": False,
        }

    def health(self) -> Dict[str, Any]:
        """Get engine health status."""
        return {
            "sidecar": "healthy",
            "pattern_detector": "ready",
            "semantic_analyzer": "ready" if self.semantic_analyzer.available else "unavailable (no API key)",
            "yrsn_adapter": self.adapter.health(),
        }

    # =========================================================================
    # DEPRECATED - These methods exist for backward compatibility
    # Remove after migration to clean architecture
    # =========================================================================

    def get_thresholds(self) -> Dict[str, float]:
        """DEPRECATED: Thresholds are now in yrsn adapter."""
        return {
            "kappa_threshold": 0.7,
            "N_threshold": 0.5,
            "sigma_threshold": 0.7,
            "R_min": 0.3,
            "S_min": 0.4,
        }

    def set_threshold(self, key: str, value: float) -> None:
        """DEPRECATED: Thresholds are now in yrsn adapter."""
        pass

    def record_validation(self, *args, **kwargs):
        """DEPRECATED: Validation recording moved to yrsn."""
        pass

    def get_failure_rates(self) -> Dict[str, float]:
        """DEPRECATED: Failure rates are now in yrsn."""
        return {}

    def format_sr117(self, cert: Dict[str, Any]) -> Dict[str, Any]:
        """Format certificate for SR 11-7 compliance."""
        return {
            "record_type": "MODEL_VALIDATION",
            "certificate_id": cert.get("id"),
            "timestamp": cert.get("timestamp"),
            "quantitative_metrics": {
                "R": cert.get("R"),
                "S": cert.get("S"),
                "N": cert.get("N"),
                "kappa_gate": cert.get("kappa_gate"),
                "sigma": cert.get("sigma"),
            },
            "gate_outcome": cert.get("decision"),
            "gate_reached": cert.get("gate_reached"),
            "pattern_flags": cert.get("pattern_flags", []),
            "pre_screen_rejection": cert.get("pre_screen_rejection", False),
            "risk_indicators": {
                "noise_level": "HIGH" if cert.get("N", 0) > 0.4 else "NORMAL",
                "stability": "UNSTABLE" if cert.get("sigma", 0) > 0.7 else "STABLE",
                "patterns_detected": len(cert.get("pattern_flags", [])) > 0,
            },
        }
