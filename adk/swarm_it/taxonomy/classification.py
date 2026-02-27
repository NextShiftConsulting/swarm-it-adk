"""
RSCT Classification Layer

Provides thin classification on top of certificate signals:
- 16-mode RSCT classification
- 8 degradation types
- Error code assignment
- Multimodal diagnostics
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..local.engine import RSCTCertificate


class RSCTMode(Enum):
    """16-mode RSCT collapse taxonomy."""

    # Group 1: Encoding
    NOISE_SATURATION = "1.1"
    SUPERFLUOUS_DROWNING = "1.2"
    DIMENSIONAL_FRACTURE = "1.3"
    FORMAT_MISMATCH = "1.4"

    # Group 2: Dynamics
    TRAJECTORY_DIVERGENCE = "2.1"
    GRADIENT_STARVATION = "2.2"
    OOBLECK_JAMMING = "2.3"
    SUBSTRATE_DEGRADATION = "2.4"

    # Group 3: Semantic
    FLUENT_HALLUCINATION = "3.1"
    PHASOR_CONFLICT = "3.2"
    REWARD_HACKING = "3.3"
    OOD_FABRICATION = "3.4"

    # Group 4: Execution
    WEAKEST_LINK_CASCADE = "4.1"
    CROSS_MODAL_DESYNC = "4.2"
    STALLED_NAVIGATION = "4.3"
    GATEKEEPER_BYPASS = "4.4"

    # No collapse
    NOMINAL = "0.0"


class DegradationType(Enum):
    """Core degradation types aligned with yrsn."""

    NOMINAL = "NOMINAL"
    RSN_COLLAPSE = "RSN_COLLAPSE"
    HALLUCINATION = "HALLUCINATION"
    POISONING = "POISONING"
    DISTRACTION = "DISTRACTION"
    INSTABILITY = "INSTABILITY"
    LOW_RELEVANCE = "LOW_RELEVANCE"
    TRAJECTORY_DIVERGENCE = "TRAJECTORY_DIVERGENCE"
    OOD_FABRICATION = "OOD_FABRICATION"


class Severity(Enum):
    """Four-tier severity aligned with constraint taxonomy."""

    TRACE = "TRACE"  # Emergent tier
    MINOR = "MINOR"  # Emergent/Learned
    WARNING = "WARNING"  # Learned
    CRITICAL = "CRITICAL"  # Consolidated
    FATAL = "FATAL"  # Actual


@dataclass
class ClassificationResult:
    """Result of certificate classification."""

    rsct_mode: RSCTMode
    degradation_type: DegradationType
    severity: Severity
    error_codes: List[str]
    confidence: float
    diagnostics: Dict[str, Any]


# Mode descriptions for user-facing output
MODE_DESCRIPTIONS = {
    RSCTMode.NOISE_SATURATION: "N ≥ 0.5, encoding is garbage",
    RSCTMode.SUPERFLUOUS_DROWNING: "S ≫ R, signal lost in fluff",
    RSCTMode.DIMENSIONAL_FRACTURE: "Embedding space too small for rotor",
    RSCTMode.FORMAT_MISMATCH: "Output doesn't match expected schema",
    RSCTMode.TRAJECTORY_DIVERGENCE: "σ > 0.7, solver is unstable",
    RSCTMode.GRADIENT_STARVATION: "Learning has stalled",
    RSCTMode.OOBLECK_JAMMING: "Turbulence spike (σ_max > 2×σ_mean)",
    RSCTMode.SUBSTRATE_DEGRADATION: "Hardware is physically damaged",
    RSCTMode.FLUENT_HALLUCINATION: "High κ, low R — confident but wrong",
    RSCTMode.PHASOR_CONFLICT: "c < 0.4, agents disagree",
    RSCTMode.REWARD_HACKING: "Optimizing proxy, not objective",
    RSCTMode.OOD_FABRICATION: "Out-of-distribution extrapolation",
    RSCTMode.WEAKEST_LINK_CASCADE: "min(κ_i) pulls down whole system",
    RSCTMode.CROSS_MODAL_DESYNC: "κ_interface < 0.3, modalities misaligned",
    RSCTMode.STALLED_NAVIGATION: "Reasoning loop detected",
    RSCTMode.GATEKEEPER_BYPASS: "Adversarial manipulation of certificates",
    RSCTMode.NOMINAL: "No collapse detected",
}


def classify_certificate(cert: "RSCTCertificate") -> ClassificationResult:
    """
    Classify a certificate into RSCT mode, degradation type, and severity.

    Args:
        cert: RSCTCertificate to classify

    Returns:
        ClassificationResult with mode, type, severity, and error codes
    """
    mode = _classify_mode(cert)
    degradation = _classify_degradation(cert, mode)
    severity = _classify_severity(cert, mode)
    error_codes = _generate_error_codes(cert, mode)
    diagnostics = _generate_diagnostics(cert, mode)

    return ClassificationResult(
        rsct_mode=mode,
        degradation_type=degradation,
        severity=severity,
        error_codes=error_codes,
        confidence=_compute_confidence(cert, mode),
        diagnostics=diagnostics,
    )


def _classify_mode(cert: "RSCTCertificate") -> RSCTMode:
    """Classify certificate into RSCT mode."""

    # Use backend classification if available
    if cert.rsct_mode:
        try:
            return RSCTMode(cert.rsct_mode)
        except ValueError:
            pass  # Fall through to local classification

    # Group 1: Encoding
    if cert.N >= 0.5:
        return RSCTMode.NOISE_SATURATION
    if cert.S > 0.6 and cert.R < 0.2:
        return RSCTMode.SUPERFLUOUS_DROWNING

    # Group 2: Dynamics
    if cert.sigma > 0.7:
        return RSCTMode.TRAJECTORY_DIVERGENCE

    # Group 3: Semantic
    if cert.kappa_gate > 0.7 and cert.R < 0.4:
        return RSCTMode.FLUENT_HALLUCINATION
    if cert.alpha is not None and cert.alpha < 0.3:
        return RSCTMode.PHASOR_CONFLICT
    if cert.omega is not None and cert.omega < 0.3:
        return RSCTMode.OOD_FABRICATION

    # Group 4: Execution (requires kappa decomposition)
    if cert.has_kappa_decomposition:
        kappas = [k for k in [cert.kappa_H, cert.kappa_L, cert.kappa_A] if k is not None]
        if kappas and min(kappas) < 0.3:
            return RSCTMode.WEAKEST_LINK_CASCADE
        if cert.kappa_interface is not None and cert.kappa_interface < 0.3:
            return RSCTMode.CROSS_MODAL_DESYNC

    return RSCTMode.NOMINAL


def _classify_degradation(cert: "RSCTCertificate", mode: RSCTMode) -> DegradationType:
    """Map RSCT mode to degradation type."""

    mode_to_degradation = {
        RSCTMode.NOISE_SATURATION: DegradationType.RSN_COLLAPSE,
        RSCTMode.SUPERFLUOUS_DROWNING: DegradationType.DISTRACTION,
        RSCTMode.TRAJECTORY_DIVERGENCE: DegradationType.TRAJECTORY_DIVERGENCE,
        RSCTMode.FLUENT_HALLUCINATION: DegradationType.HALLUCINATION,
        RSCTMode.PHASOR_CONFLICT: DegradationType.INSTABILITY,
        RSCTMode.OOD_FABRICATION: DegradationType.OOD_FABRICATION,
        RSCTMode.WEAKEST_LINK_CASCADE: DegradationType.INSTABILITY,
        RSCTMode.CROSS_MODAL_DESYNC: DegradationType.INSTABILITY,
    }

    return mode_to_degradation.get(mode, DegradationType.NOMINAL)


def _classify_severity(cert: "RSCTCertificate", mode: RSCTMode) -> Severity:
    """Classify severity based on mode and metrics."""

    # Fatal conditions
    if mode in (RSCTMode.NOISE_SATURATION, RSCTMode.SUBSTRATE_DEGRADATION):
        return Severity.FATAL

    # Critical conditions
    if mode in (RSCTMode.GATEKEEPER_BYPASS, RSCTMode.TRAJECTORY_DIVERGENCE):
        return Severity.CRITICAL

    if not cert.decision.allowed:
        return Severity.CRITICAL

    # Warning conditions
    if mode in (RSCTMode.FLUENT_HALLUCINATION, RSCTMode.PHASOR_CONFLICT):
        return Severity.WARNING

    if cert.N > 0.3:
        return Severity.WARNING

    # Minor conditions
    if mode != RSCTMode.NOMINAL:
        return Severity.MINOR

    return Severity.TRACE


def _generate_error_codes(cert: "RSCTCertificate", mode: RSCTMode) -> List[str]:
    """Generate error codes based on certificate and mode."""
    codes = []

    # Pre-execution codes (V1-V4)
    if cert.N >= 0.5:
        codes.append("V1.1.1")  # Noise Saturation
    elif cert.N >= 0.3:
        codes.append("V1.1.1-WARN")

    if cert.S > 0.6 and cert.R < 0.2:
        codes.append("V1.1.2")  # Superfluous Drowning

    if cert.sigma > 0.7:
        codes.append("V2.2.1")  # Trajectory Divergence

    if cert.kappa_gate > 0.7 and cert.R < 0.4:
        codes.append("V3.3.1")  # Fluent Hallucination

    if not cert.simplex_valid:
        codes.append("V0.0.1")  # Simplex Violation

    # Mode-specific codes
    mode_codes = {
        RSCTMode.PHASOR_CONFLICT: "V3.3.2",
        RSCTMode.REWARD_HACKING: "V3.3.3",
        RSCTMode.OOD_FABRICATION: "V3.3.4",
        RSCTMode.WEAKEST_LINK_CASCADE: "V4.4.1",
        RSCTMode.CROSS_MODAL_DESYNC: "V4.4.2",
        RSCTMode.STALLED_NAVIGATION: "V4.4.3",
        RSCTMode.GATEKEEPER_BYPASS: "V4.4.4",
    }

    if mode in mode_codes:
        codes.append(mode_codes[mode])

    return codes


def _generate_diagnostics(cert: "RSCTCertificate", mode: RSCTMode) -> Dict[str, Any]:
    """Generate diagnostic information."""
    diagnostics = {
        "mode_description": MODE_DESCRIPTIONS.get(mode, "Unknown"),
        "simplex_valid": cert.simplex_valid,
        "margin": cert.margin,
    }

    # Add trigger analysis
    if mode == RSCTMode.NOISE_SATURATION:
        diagnostics["trigger"] = f"N={cert.N:.3f} >= 0.5"
    elif mode == RSCTMode.FLUENT_HALLUCINATION:
        diagnostics["trigger"] = f"kappa={cert.kappa_gate:.3f} > 0.7, R={cert.R:.3f} < 0.4"
    elif mode == RSCTMode.TRAJECTORY_DIVERGENCE:
        diagnostics["trigger"] = f"sigma={cert.sigma:.3f} > 0.7"

    return diagnostics


def _compute_confidence(cert: "RSCTCertificate", mode: RSCTMode) -> float:
    """Compute classification confidence."""
    if mode == RSCTMode.NOMINAL:
        return 1.0 - cert.N  # Higher confidence when less noise

    # Mode-specific confidence
    if mode == RSCTMode.NOISE_SATURATION:
        return min(1.0, cert.N / 0.5)  # How far above threshold

    if mode == RSCTMode.FLUENT_HALLUCINATION:
        return (cert.kappa_gate - 0.7) * (0.4 - cert.R) * 4  # Product of exceedances

    return 0.7  # Default moderate confidence


def add_error_codes(cert: "RSCTCertificate") -> "RSCTCertificate":
    """
    Add error codes to a certificate in place.

    Args:
        cert: Certificate to update

    Returns:
        Same certificate with error_codes populated
    """
    result = classify_certificate(cert)
    cert.error_codes = result.error_codes
    cert.rsct_mode = result.rsct_mode.value
    cert.degradation_type = result.degradation_type.value
    return cert


def diagnose_multimodal(cert: "RSCTCertificate") -> Dict[str, Any]:
    """
    Diagnose multimodal issues based on kappa decomposition.

    Requires kappa_H, kappa_L, kappa_A, and kappa_interface to be present.

    Args:
        cert: Certificate with kappa decomposition

    Returns:
        Diagnostic dict with per-modality health and recommendations
    """
    if not cert.has_kappa_decomposition:
        return {
            "available": False,
            "reason": "Kappa decomposition not available",
        }

    kappas = {
        "high_level": cert.kappa_H,
        "low_level": cert.kappa_L,
        "abstraction": cert.kappa_A,
        "interface": cert.kappa_interface,
    }

    # Find weakest modality
    valid_kappas = {k: v for k, v in kappas.items() if v is not None}
    if not valid_kappas:
        return {"available": False, "reason": "No valid kappa values"}

    weakest = min(valid_kappas, key=valid_kappas.get)
    weakest_value = valid_kappas[weakest]

    # Compute health scores
    health = {}
    for name, value in valid_kappas.items():
        if value >= 0.7:
            health[name] = "healthy"
        elif value >= 0.4:
            health[name] = "degraded"
        else:
            health[name] = "critical"

    # Generate recommendations
    recommendations = []
    if weakest_value < 0.4:
        if weakest == "high_level":
            recommendations.append("Re-encode input with clearer semantic structure")
        elif weakest == "low_level":
            recommendations.append("Check signal quality or sensor calibration")
        elif weakest == "abstraction":
            recommendations.append("Simplify abstraction hierarchy")
        elif weakest == "interface":
            recommendations.append("Check cross-modal alignment or use unified encoder")

    # Check for desync
    if len(valid_kappas) >= 2:
        values = list(valid_kappas.values())
        spread = max(values) - min(values)
        if spread > 0.4:
            recommendations.append(f"High kappa spread ({spread:.2f}): modalities out of sync")

    return {
        "available": True,
        "kappas": valid_kappas,
        "health": health,
        "weakest": weakest,
        "weakest_value": weakest_value,
        "recommendations": recommendations,
        "is_desynced": any(h == "critical" for h in health.values()),
    }
