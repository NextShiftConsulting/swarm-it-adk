"""
Certificate Bridge

Provides round-trip conversion between SDK RSCTCertificate and yrsn YRSNCertificate.

Hierarchy:
    RSCTCertificate (SDK, lightweight)
        ↓ to_yrsn_dict()
    YRSNCertificate (Backend, full)
        ↓ to_sdk_dict()
    RSCTCertificate (SDK, lightweight)

The bridge ensures:
1. No data loss during round-trip
2. SDK can consume full backend certificates
3. Backend can log SDK-generated certificates
4. Multimodal hierarchy fields transfer correctly
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..local.engine import RSCTCertificate


@dataclass
class CertificateHierarchy:
    """
    Multimodal hierarchy extracted from certificate.

    Matches yrsn's hierarchy structure for compatibility.
    """

    # Per-modality kappa
    kappa_H: Optional[float] = None  # High-level (text/symbolic)
    kappa_L: Optional[float] = None  # Low-level (vision/signal)
    kappa_A: Optional[float] = None  # Abstraction
    kappa_interface: Optional[float] = None  # Cross-modal

    # Per-modality sigma
    sigma_H: Optional[float] = None
    sigma_L: Optional[float] = None

    # Computed
    kappa_gate: Optional[float] = None  # min(kappa_H, kappa_L, ...)
    hierarchy_gap: Optional[float] = None  # |kappa_H - kappa_L|
    dominant_modality: Optional[str] = None  # "H" or "L"

    @property
    def is_multimodal(self) -> bool:
        """Check if hierarchy has multimodal data."""
        return self.kappa_H is not None and self.kappa_L is not None

    def to_dict(self) -> Dict[str, Any]:
        if not self.is_multimodal:
            return {}
        return {
            "kappa_H": self.kappa_H,
            "kappa_L": self.kappa_L,
            "kappa_A": self.kappa_A,
            "kappa_interface": self.kappa_interface,
            "sigma_H": self.sigma_H,
            "sigma_L": self.sigma_L,
            "kappa_gate": self.kappa_gate,
            "hierarchy_gap": self.hierarchy_gap,
            "dominant_modality": self.dominant_modality,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CertificateHierarchy":
        return cls(
            kappa_H=data.get("kappa_H"),
            kappa_L=data.get("kappa_L"),
            kappa_A=data.get("kappa_A"),
            kappa_interface=data.get("kappa_interface"),
            sigma_H=data.get("sigma_H"),
            sigma_L=data.get("sigma_L"),
            kappa_gate=data.get("kappa_gate"),
            hierarchy_gap=data.get("hierarchy_gap"),
            dominant_modality=data.get("dominant_modality"),
        )


def to_yrsn_dict(cert: "RSCTCertificate") -> Dict[str, Any]:
    """
    Convert SDK certificate to yrsn-compatible dict.

    This format can be:
    1. Logged to DynamoDB/S3 via yrsn adapters
    2. Reconstructed into full YRSNCertificate
    3. Used in yrsn analytics pipelines

    Args:
        cert: SDK RSCTCertificate

    Returns:
        Dict compatible with YRSNCertificate.from_dict()
    """
    result = {
        # Identification
        "certificate_id": cert.id,
        "timestamp": cert.timestamp,

        # Core simplex (yrsn uses S_sup, SDK uses S)
        "R": cert.R,
        "S_sup": cert.S,  # yrsn naming
        "N": cert.N,

        # Compatibility
        "kappa_gate": cert.kappa_gate,
        "sigma": cert.sigma,

        # Extended 6D signal
        "alpha": cert.alpha,
        "omega": cert.omega,
        "tau": cert.tau,

        # Kappa decomposition
        "kappa_H": cert.kappa_H,
        "kappa_L": cert.kappa_L,
        "kappa_A": cert.kappa_A,
        "kappa_interface": cert.kappa_interface,

        # Stability
        "admissibility": cert.admissibility,
        "quality_envelope": cert.quality_envelope,
        "lyapunov": cert.lyapunov,

        # Classification
        "rsct_mode": cert.rsct_mode,
        "degradation_type": cert.degradation_type,
        "error_codes": cert.error_codes,

        # Gate
        "gate_decision": cert.decision.value,
        "gate_reached": cert.gate_reached,
        "gate_reason": cert.reason,

        # Metadata
        "policy": cert.policy,
        "source": "swarm_it_sdk",
    }

    # Add hierarchy block if multimodal
    if cert.has_kappa_decomposition:
        # Compute derived hierarchy values
        kappas = [k for k in [cert.kappa_H, cert.kappa_L, cert.kappa_A] if k is not None]
        if kappas:
            result["hierarchy"] = {
                "kappa_H": cert.kappa_H,
                "kappa_L": cert.kappa_L,
                "kappa_A": cert.kappa_A,
                "kappa_interface": cert.kappa_interface,
                "kappa_gate": min(kappas),
                "hierarchy_gap": abs(cert.kappa_H - cert.kappa_L) if cert.kappa_H and cert.kappa_L else None,
                "dominant_modality": "H" if (cert.kappa_H or 0) > (cert.kappa_L or 0) else "L",
            }

    return result


def from_yrsn_dict(data: Dict[str, Any]) -> "RSCTCertificate":
    """
    Convert yrsn YRSNCertificate dict to SDK RSCTCertificate.

    This handles:
    1. Full YRSNCertificate from backend API
    2. Stored certificates from DynamoDB/S3
    3. Certificates with hierarchy blocks

    Args:
        data: Dict from YRSNCertificate.to_dict() or to_sdk_dict()

    Returns:
        SDK RSCTCertificate
    """
    from ..local.engine import RSCTCertificate, GateDecision

    # Handle S vs S_sup naming
    s_value = data.get("S_sup", data.get("S", 0.0))

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

    # Extract hierarchy block if present
    hierarchy = data.get("hierarchy", {})

    return RSCTCertificate(
        id=data.get("certificate_id", data.get("id", "")),
        timestamp=data.get("timestamp", ""),

        # Core
        R=data.get("R", 0.0),
        S=s_value,
        N=data.get("N", 0.0),
        kappa_gate=data.get("kappa_gate", data.get("kappa", 0.0)),
        sigma=data.get("sigma", 0.0),

        # Extended (check both flat and hierarchy)
        alpha=data.get("alpha"),
        omega=data.get("omega"),
        tau=data.get("tau"),

        # Kappa decomposition (prefer hierarchy block)
        kappa_H=hierarchy.get("kappa_H", data.get("kappa_H")),
        kappa_L=hierarchy.get("kappa_L", data.get("kappa_L")),
        kappa_A=hierarchy.get("kappa_A", data.get("kappa_A")),
        kappa_interface=hierarchy.get("kappa_interface", data.get("kappa_interface")),

        # Stability
        admissibility=data.get("admissibility"),
        quality_envelope=data.get("quality_envelope"),
        lyapunov=data.get("lyapunov"),

        # Classification
        rsct_mode=data.get("rsct_mode"),
        degradation_type=data.get("degradation_type"),
        error_codes=data.get("error_codes", []),

        # Gate
        decision=decision,
        gate_reached=data.get("gate_reached", 0),
        reason=data.get("gate_reason", data.get("reason", "")),

        # Audit
        policy=data.get("policy", "default"),
        raw=data,
    )


def extract_hierarchy(cert: "RSCTCertificate") -> CertificateHierarchy:
    """
    Extract hierarchy structure from certificate.

    Args:
        cert: RSCTCertificate

    Returns:
        CertificateHierarchy with multimodal data
    """
    hierarchy = CertificateHierarchy(
        kappa_H=cert.kappa_H,
        kappa_L=cert.kappa_L,
        kappa_A=cert.kappa_A,
        kappa_interface=cert.kappa_interface,
    )

    if hierarchy.is_multimodal:
        kappas = [k for k in [cert.kappa_H, cert.kappa_L, cert.kappa_A] if k is not None]
        hierarchy.kappa_gate = min(kappas) if kappas else None
        if cert.kappa_H is not None and cert.kappa_L is not None:
            hierarchy.hierarchy_gap = abs(cert.kappa_H - cert.kappa_L)
            hierarchy.dominant_modality = "H" if cert.kappa_H > cert.kappa_L else "L"

    return hierarchy


def validate_round_trip(cert: "RSCTCertificate") -> bool:
    """
    Validate that a certificate can round-trip without data loss.

    Args:
        cert: RSCTCertificate to validate

    Returns:
        True if round-trip preserves all fields
    """
    yrsn_dict = to_yrsn_dict(cert)
    restored = from_yrsn_dict(yrsn_dict)

    # Check core fields
    checks = [
        cert.R == restored.R,
        cert.S == restored.S,
        cert.N == restored.N,
        cert.kappa_gate == restored.kappa_gate,
        cert.sigma == restored.sigma,
        cert.decision == restored.decision,
    ]

    # Check optional fields if present
    if cert.alpha is not None:
        checks.append(cert.alpha == restored.alpha)
    if cert.kappa_H is not None:
        checks.append(cert.kappa_H == restored.kappa_H)

    return all(checks)
