"""
Compatibility shim — maps between ADK's GateDecision and controlplane types.

ADK extends the core enforcement decisions with runtime-specific states
(HALT, TIMEOUT, ESCALATE) that are not part of the controlplane contract.
This shim provides the mapping layer.

PASS_FAST and PASS_GUARDED are legacy — mapped to EXECUTE.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from yrsn_controlplane import (
    CPGatekeeperInput,
    EnforcementDecision,
    GatekeeperResult,
)


class GateDecision(str, Enum):
    """ADK gate decisions — superset of controlplane EnforcementDecision.

    Core decisions (delegated to controlplane):
        EXECUTE, REJECT, BLOCK, RE_ENCODE, REPAIR

    Extended decisions (ADK runtime only):
        HALT:     Agent terminated by supervisor
        TIMEOUT:  Gate evaluation exceeded deadline
        ESCALATE: Requires human review

    Legacy (deprecated, mapped to EXECUTE):
        PASS_FAST, PASS_GUARDED
    """

    # Core — 1:1 with EnforcementDecision
    EXECUTE = "EXECUTE"
    REJECT = "REJECT"
    BLOCK = "BLOCK"
    RE_ENCODE = "RE_ENCODE"
    REPAIR = "REPAIR"

    # Routing decisions (from controlplane)
    WARN = "WARN"
    FALLBACK = "FALLBACK"

    # ADK runtime extensions
    HALT = "HALT"
    TIMEOUT = "TIMEOUT"
    ESCALATE = "ESCALATE"

    # Legacy (deprecated)
    PASS_FAST = "PASS_FAST"
    PASS_GUARDED = "PASS_GUARDED"

    @property
    def allowed(self) -> bool:
        """Returns True if execution should proceed."""
        return self in (
            GateDecision.EXECUTE,
            GateDecision.PASS_FAST,
            GateDecision.PASS_GUARDED,
            GateDecision.REPAIR,
            GateDecision.WARN,
            GateDecision.FALLBACK,
        )

    @property
    def requires_action(self) -> bool:
        """Returns True if remediation is needed."""
        return self in (
            GateDecision.RE_ENCODE,
            GateDecision.REPAIR,
            GateDecision.ESCALATE,
            GateDecision.WARN,
            GateDecision.FALLBACK,
        )

    def to_enforcement_decision(self) -> Optional[EnforcementDecision]:
        """Map to controlplane EnforcementDecision (None if ADK-only)."""
        mapping = {
            GateDecision.EXECUTE: EnforcementDecision.EXECUTE,
            GateDecision.REJECT: EnforcementDecision.REJECT,
            GateDecision.BLOCK: EnforcementDecision.BLOCK,
            GateDecision.RE_ENCODE: EnforcementDecision.RE_ENCODE,
            GateDecision.REPAIR: EnforcementDecision.REPAIR,
            GateDecision.WARN: EnforcementDecision.WARN,
            GateDecision.FALLBACK: EnforcementDecision.FALLBACK,
            GateDecision.PASS_FAST: EnforcementDecision.EXECUTE,
            GateDecision.PASS_GUARDED: EnforcementDecision.EXECUTE,
        }
        return mapping.get(self)


def from_enforcement_decision(decision: EnforcementDecision) -> GateDecision:
    """Convert controlplane EnforcementDecision to ADK GateDecision."""
    return GateDecision(decision.value)


def from_gatekeeper_result(result: GatekeeperResult) -> GateDecision:
    """Extract ADK GateDecision from a controlplane GatekeeperResult."""
    return from_enforcement_decision(result.decision)


def to_measurement_estimate(
    R: float,
    S_sup: float,
    N: float,
    kappa_compat: float,
    sigma: float,
    alpha: float | None = None,
    kappa_H: float | None = None,
    kappa_L: float | None = None,
    kappa_interface: float | None = None,
    coherence: float | None = None,
) -> CPGatekeeperInput:
    """Build a CPGatekeeperInput from ADK certificate fields.

    Bridges the gap between ADK's RSCTCertificate (rich, mutable) and
    controlplane's CPGatekeeperInput (minimal, for gating).

    kappa_compat is the ADK name (ADR-020 D7).
    """
    if alpha is None:
        alpha = R / (R + N) if (R + N) > 0 else 0.0

    # V-011: derive noise_admissibility from raw N. Initially = N,
    # creating the seam for future evolution to f(N, sigma, omega, ...).
    # Raw N stays in evidence as measurement fact.
    noise_admissibility = N

    evidence: dict = {
        "N": N,
        "R": R,
        "S_sup": S_sup,
        "noise_admissibility": noise_admissibility,
        "noise_admissibility_method": "raw_N_v1",
    }
    if coherence is not None:
        evidence["coherence"] = coherence

    return CPGatekeeperInput(
        alpha=alpha,
        kappa_compat=kappa_compat,
        sigma=sigma,
        source_mode="direct",
        evidence=evidence,
        kappa_H=kappa_H,
        kappa_L=kappa_L,
        kappa_interface=kappa_interface,
    )


# Backward-compat alias
to_certificate_estimate = to_measurement_estimate


# ---------------------------------------------------------------------------
# Output-direction normalization (V-013 reconciliation, ADR-079.b Decision 2).
# Folded in from the removed governance/certifier_adapter.py so that _compat is
# the single home for "map between ADK certificate types and a uniform shape."
# Maps either real certificate type onto one NormalizedCertificate:
#   - RSCTCertificate (local.engine) exposes `.kappa_compat` directly.
#   - SwarmCertificate (topology.certifier) exposes the same enforced proxy under
#     `.kappa_compat_chain_min` and has no `.kappa_compat`.
# Contains no gate math and makes no allow/refuse decision of its own; `allowed`
# is read fail-closed via _cert_allowed (the one duck-type site).
# ---------------------------------------------------------------------------

from dataclasses import dataclass as _dataclass  # noqa: E402
from typing import Any as _Any, Callable as _Callable, Optional as _Optional  # noqa: E402


def _cert_allowed(cert: _Any) -> bool:
    """Fail-closed verdict read: `.allowed` if present, else `.verdict == 'EXECUTE'`.

    Unknown shape (neither attribute) -> False (never admit what we cannot read).
    """
    if hasattr(cert, "allowed"):
        return bool(cert.allowed)
    if hasattr(cert, "verdict"):
        return cert.verdict == "EXECUTE"
    return False


@_dataclass(frozen=True)
class NormalizedCertificate:
    """Uniform read shape for a derived certificate.

    kappa_compat: prefer `.kappa_compat`; else fall back to
    `.kappa_compat_chain_min` (SwarmCertificate); None if neither (treat as
    incomparable). expires_at is None-safe (real types carry none today).
    """

    id: _Optional[str]
    kappa_compat: _Optional[float]
    allowed: bool
    expires_at: _Optional[float] = None


def normalize_certificate(cert: _Any) -> "NormalizedCertificate":
    """Map a real (or duck-type-compatible) certificate onto NormalizedCertificate."""
    kappa_compat = getattr(cert, "kappa_compat", None)
    if kappa_compat is None:
        kappa_compat = getattr(cert, "kappa_compat_chain_min", None)
    return NormalizedCertificate(
        id=getattr(cert, "id", None),
        kappa_compat=kappa_compat,
        allowed=_cert_allowed(cert),
        expires_at=getattr(cert, "expires_at", None),
    )


def make_certifier(
    certify_fn: _Callable[[_Any], _Any]
) -> _Callable[[_Any], "NormalizedCertificate"]:
    """Wrap a raw certification function so it returns a NormalizedCertificate.

    `certify_fn` is any callable producing a real certificate (a bound
    `LocalEngine.certify`, `SwarmCertifier.certify`, or a controlplane-backed
    certifier). The returned callable is what a recert boundary consumes as its
    `certifier` port.
    """

    def _certifier(state: _Any) -> "NormalizedCertificate":
        return normalize_certificate(certify_fn(state))

    return _certifier
