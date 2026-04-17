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
    CertificateEstimate,
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
        )

    @property
    def requires_action(self) -> bool:
        """Returns True if remediation is needed."""
        return self in (
            GateDecision.RE_ENCODE,
            GateDecision.REPAIR,
            GateDecision.ESCALATE,
        )

    def to_enforcement_decision(self) -> Optional[EnforcementDecision]:
        """Map to controlplane EnforcementDecision (None if ADK-only)."""
        mapping = {
            GateDecision.EXECUTE: EnforcementDecision.EXECUTE,
            GateDecision.REJECT: EnforcementDecision.REJECT,
            GateDecision.BLOCK: EnforcementDecision.BLOCK,
            GateDecision.RE_ENCODE: EnforcementDecision.RE_ENCODE,
            GateDecision.REPAIR: EnforcementDecision.REPAIR,
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


def to_certificate_estimate(
    R: float,
    S: float,
    N: float,
    kappa_gate: float,
    sigma: float,
    alpha: float | None = None,
    kappa_H: float | None = None,
    kappa_L: float | None = None,
    kappa_interface: float | None = None,
    coherence: float | None = None,
) -> CertificateEstimate:
    """Build a CertificateEstimate from ADK certificate fields.

    Bridges the gap between ADK's RSCTCertificate (rich, mutable) and
    controlplane's CertificateEstimate (minimal, for gating).
    """
    if alpha is None:
        alpha = R / (R + N) if (R + N) > 0 else 0.0

    evidence: dict = {"N": N, "R": R, "S_sup": S}
    if coherence is not None:
        evidence["coherence"] = coherence

    return CertificateEstimate(
        alpha=alpha,
        kappa_gate=kappa_gate,
        sigma=sigma,
        source_mode="direct",
        evidence=evidence,
        kappa_H=kappa_H,
        kappa_L=kappa_L,
        kappa_interface=kappa_interface,
    )
