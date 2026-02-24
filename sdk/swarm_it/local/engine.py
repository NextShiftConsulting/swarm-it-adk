"""
RSCT Local Certification Engine

Provides offline certification aligned with YRSNCertificate.
The RSCTCertificate is a projection that round-trips with the full backend.

Hierarchy:
    RSCTCertificate (SDK)
        ↓ to_yrsn_dict()
    YRSNCertificate (Backend)
        ↓ to_sdk_dict()
    RSCTCertificate (SDK)
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class GateDecision(Enum):
    """RSCT gate decisions aligned with yrsn gatekeeper."""

    # Primary decisions
    EXECUTE = "EXECUTE"
    REJECT = "REJECT"
    BLOCK = "BLOCK"
    RE_ENCODE = "RE_ENCODE"
    REPAIR = "REPAIR"
    HALT = "HALT"
    TIMEOUT = "TIMEOUT"
    ESCALATE = "ESCALATE"

    # Legacy compatibility
    PASS_FAST = "PASS_FAST"
    PASS_GUARDED = "PASS_GUARDED"

    @property
    def allowed(self) -> bool:
        """Returns True if execution should proceed."""
        return self in (
            GateDecision.EXECUTE,
            GateDecision.PASS_FAST,
            GateDecision.PASS_GUARDED,
            GateDecision.REPAIR,  # Proceed with repair
        )

    @property
    def requires_action(self) -> bool:
        """Returns True if remediation is needed."""
        return self in (
            GateDecision.RE_ENCODE,
            GateDecision.REPAIR,
            GateDecision.ESCALATE,
        )


@dataclass
class RSCTCertificate:
    """
    SDK Certificate aligned with YRSNCertificate.

    Core fields are always present. Extended fields are populated
    when received from a full YRSN backend, None otherwise.

    Hierarchy:
        - Core simplex (R, S, N) + kappa_gate + sigma: REQUIRED
        - Extended signals (alpha, omega, tau, kappa decomposition): OPTIONAL
        - Stability metrics (admissibility, quality_envelope, lyapunov): OPTIONAL
        - Classification (rsct_mode, degradation_type, error_codes): COMPUTED
        - Raw dict: PRESERVES full backend data for audit
    """

    # === REQUIRED: Identification ===
    id: str
    timestamp: str

    # === REQUIRED: Core Simplex (R + S + N = 1) ===
    R: float  # Relevance [0, 1]
    S: float  # Support/Superfluous [0, 1]
    N: float  # Noise [0, 1]

    # === REQUIRED: Compatibility ===
    kappa_gate: float  # Enforced compatibility: min(kappa_H, kappa_L, ...)
    sigma: float  # Turbulence [0, 1]

    # === REQUIRED: Gate Result ===
    decision: GateDecision
    gate_reached: int  # 1-5 for gates, 0 for pre-gate
    reason: str

    # === OPTIONAL: Extended 6D Signal ===
    alpha: Optional[float] = None  # Purity: R/(R+N)
    omega: Optional[float] = None  # OOD score [0, 1]
    tau: Optional[float] = None  # Temperature

    # === OPTIONAL: Kappa Decomposition ===
    kappa_H: Optional[float] = None  # High-level (text/symbolic)
    kappa_L: Optional[float] = None  # Low-level (vision/signal)
    kappa_A: Optional[float] = None  # Abstraction layer
    kappa_interface: Optional[float] = None  # Cross-modal interface

    # === OPTIONAL: Three Stability Metrics ===
    admissibility: Optional[float] = None  # Feasibility score
    quality_envelope: Optional[float] = None  # Quality bound
    lyapunov: Optional[float] = None  # Stability exponent

    # === CLASSIFICATION (computed or from backend) ===
    rsct_mode: Optional[str] = None  # "1.1", "3.1", etc.
    degradation_type: Optional[str] = None  # "HALLUCINATION", etc.
    error_codes: List[str] = field(default_factory=list)  # ["V1.1.1", "V5.II.1"]

    # === AUDIT ===
    policy: str = "default"
    raw: Dict[str, Any] = field(default_factory=dict)

    # === COMPUTED PROPERTIES ===

    @property
    def allowed(self) -> bool:
        """Is execution allowed?"""
        return self.decision.allowed

    @property
    def margin(self) -> float:
        """Safety margin: distance from rejection thresholds."""
        return min(self.R, self.kappa_gate, 1.0 - self.N)

    @property
    def simplex_valid(self) -> bool:
        """Check R + S + N ≈ 1."""
        return abs(self.R + self.S + self.N - 1.0) < 0.01

    @property
    def has_extended_signals(self) -> bool:
        """Check if 6D signal is available."""
        return self.alpha is not None and self.omega is not None

    @property
    def has_kappa_decomposition(self) -> bool:
        """Check if kappa is decomposed."""
        return self.kappa_H is not None

    @property
    def has_stability_metrics(self) -> bool:
        """Check if stability metrics are available."""
        return self.admissibility is not None

    def get_rsct_mode(self) -> str:
        """Get RSCT mode, computing locally if not provided."""
        if self.rsct_mode:
            return self.rsct_mode
        return self._classify_local()

    def _classify_local(self) -> str:
        """
        Lightweight local RSCT mode classification.

        This is an APPROXIMATION. Full classification requires
        the rotor and additional signals not available locally.
        """
        # Group 1: Encoding
        if self.N >= 0.5:
            return "1.1"  # Noise Saturation
        if self.S > 0.6 and self.R < 0.2:
            return "1.2"  # Superfluous Drowning

        # Group 2: Dynamics
        if self.sigma > 0.7:
            return "2.1"  # Trajectory Divergence

        # Group 3: Semantic
        if self.kappa_gate > 0.7 and self.R < 0.4:
            return "3.1"  # Fluent Hallucination
        if self.alpha is not None and self.alpha < 0.3:
            return "3.2"  # Phasor Conflict

        # Group 4: Execution
        if self.has_kappa_decomposition:
            min_kappa = min(
                k for k in [self.kappa_H, self.kappa_L, self.kappa_A]
                if k is not None
            )
            if min_kappa < 0.3:
                return "4.1"  # Weakest-Link Cascade
            if self.kappa_interface is not None and self.kappa_interface < 0.3:
                return "4.2"  # Cross-Modal Desync

        return "0.0"  # No collapse detected

    # === SERIALIZATION ===

    def to_dict(self) -> Dict[str, Any]:
        """Export for JSON serialization."""
        result = {
            "certificate_id": self.id,
            "timestamp": self.timestamp,

            # Core simplex
            "R": self.R,
            "S": self.S,
            "N": self.N,
            "kappa_gate": self.kappa_gate,
            "sigma": self.sigma,

            # Gate
            "gate_decision": self.decision.value,
            "gate_reached": self.gate_reached,
            "reason": self.reason,

            # Computed
            "allowed": self.allowed,
            "margin": self.margin,
            "rsct_mode": self.get_rsct_mode(),
            "policy": self.policy,
        }

        # Extended signals (if available)
        if self.has_extended_signals:
            result["extended"] = {
                "alpha": self.alpha,
                "omega": self.omega,
                "tau": self.tau,
            }

        # Kappa decomposition (if available)
        if self.has_kappa_decomposition:
            result["kappa_decomposition"] = {
                "kappa_H": self.kappa_H,
                "kappa_L": self.kappa_L,
                "kappa_A": self.kappa_A,
                "kappa_interface": self.kappa_interface,
            }

        # Stability metrics (if available)
        if self.has_stability_metrics:
            result["stability"] = {
                "admissibility": self.admissibility,
                "quality_envelope": self.quality_envelope,
                "lyapunov": self.lyapunov,
            }

        # Classification
        if self.degradation_type or self.error_codes:
            result["classification"] = {
                "degradation_type": self.degradation_type,
                "error_codes": self.error_codes,
            }

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RSCTCertificate":
        """
        Parse response into RSCTCertificate.

        Handles both full YRSNCertificate and minimal responses.
        """
        # Handle S vs S_sup naming
        s_value = data.get("S", data.get("S_sup", 0.0))

        # Parse decision
        decision_str = data.get("gate_decision", "EXECUTE")
        try:
            decision = GateDecision(decision_str)
        except ValueError:
            if decision_str.startswith("PASS"):
                decision = GateDecision.EXECUTE
            elif decision_str.startswith("REJECT"):
                decision = GateDecision.REJECT
            else:
                decision = GateDecision.BLOCK

        # Extract nested fields
        extended = data.get("extended", {})
        kappa_decomp = data.get("kappa_decomposition", {})
        stability = data.get("stability", {})
        classification = data.get("classification", {})

        return cls(
            id=data.get("certificate_id", data.get("id", "")),
            timestamp=data.get("timestamp", ""),

            # Core
            R=data.get("R", 0.0),
            S=s_value,
            N=data.get("N", 0.0),
            kappa_gate=data.get("kappa_gate", data.get("kappa", 0.0)),
            sigma=data.get("sigma", 0.0),

            # Extended (optional, check both flat and nested)
            alpha=data.get("alpha", extended.get("alpha")),
            omega=data.get("omega", extended.get("omega")),
            tau=data.get("tau", extended.get("tau")),

            # Kappa decomposition (optional)
            kappa_H=data.get("kappa_H", kappa_decomp.get("kappa_H")),
            kappa_L=data.get("kappa_L", kappa_decomp.get("kappa_L")),
            kappa_A=data.get("kappa_A", kappa_decomp.get("kappa_A")),
            kappa_interface=data.get("kappa_interface", kappa_decomp.get("kappa_interface")),

            # Stability (optional)
            admissibility=data.get("admissibility", stability.get("admissibility")),
            quality_envelope=data.get("quality_envelope", stability.get("quality_envelope")),
            lyapunov=data.get("lyapunov", stability.get("lyapunov")),

            # Classification
            rsct_mode=data.get("rsct_mode", classification.get("rsct_mode")),
            degradation_type=data.get("degradation_type", classification.get("degradation_type")),
            error_codes=data.get("error_codes", classification.get("error_codes", [])),

            # Gate
            decision=decision,
            gate_reached=data.get("gate_reached", 0),
            reason=data.get("gate_reason", data.get("reason", "")),

            # Audit
            policy=data.get("policy", "default"),
            raw=data,
        )


class LocalEngine:
    """
    Local RSCT certification engine.

    Provides offline certification using hash-based simplex projection.
    NOT production-grade. Use for:
    - Development/testing
    - Graceful degradation when API unavailable
    - Edge deployment proofs-of-concept
    """

    def __init__(
        self,
        policy: str = "default",
        n_threshold: float = 0.5,
        kappa_threshold: float = 0.4,
        sigma_default: float = 0.3,
    ):
        """
        Initialize local engine.

        Args:
            policy: Default policy name
            n_threshold: Noise threshold for rejection
            kappa_threshold: Kappa threshold for blocking
            sigma_default: Default turbulence value
        """
        self.policy = policy
        self.n_threshold = n_threshold
        self.kappa_threshold = kappa_threshold
        self.sigma_default = sigma_default

    def certify(
        self,
        context: str,
        policy: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RSCTCertificate:
        """
        Certify a context locally using hash-based projection.

        Args:
            context: Text to certify
            policy: Override policy
            metadata: Optional metadata (ignored in local mode)

        Returns:
            RSCTCertificate with hash-based R/S/N
        """
        # Hash-based pseudo-RSN (deterministic but not RSCT-compliant)
        h = hashlib.sha256(context.encode()).hexdigest()
        raw_r = int(h[0:8], 16) / 0xFFFFFFFF
        raw_s = int(h[8:16], 16) / 0xFFFFFFFF
        raw_n = int(h[16:24], 16) / 0xFFFFFFFF

        # Normalize to simplex
        total = raw_r + raw_s + raw_n
        R = raw_r / total
        S = raw_s / total
        N = raw_n / total

        # Compute derived metrics
        alpha = R / (R + N) if (R + N) > 0 else 0.0
        kappa = 0.5 + 0.3 * R  # Simplified kappa estimate
        sigma = self.sigma_default

        # Gate decision
        if N >= self.n_threshold:
            decision = GateDecision.REJECT
            reason = f"High noise: N={N:.3f} >= {self.n_threshold}"
            gate = 1
        elif kappa < self.kappa_threshold:
            decision = GateDecision.BLOCK
            reason = f"Low compatibility: kappa={kappa:.3f} < {self.kappa_threshold}"
            gate = 3
        else:
            decision = GateDecision.EXECUTE
            reason = "Local mode: passed basic checks"
            gate = 5

        return RSCTCertificate(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            R=R,
            S=S,
            N=N,
            kappa_gate=kappa,
            sigma=sigma,
            alpha=alpha,
            decision=decision,
            gate_reached=gate,
            reason=reason,
            policy=policy or self.policy,
            raw={"_local_mode": True, "_engine": "hash_simplex"},
        )


def certify_local(
    context: str,
    policy: str = "default",
) -> RSCTCertificate:
    """
    Convenience function for one-shot local certification.

    Args:
        context: Text to certify
        policy: Policy name

    Returns:
        RSCTCertificate
    """
    engine = LocalEngine(policy=policy)
    return engine.certify(context)
