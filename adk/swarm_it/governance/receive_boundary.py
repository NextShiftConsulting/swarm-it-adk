"""Receive-boundary validation for HandoffEnvelope: shape+hash, then
fail-closed re-derivation enforcement.

Two layers, always in this order:

1. INERT shape+hash checks (unchanged from Task 2): malformed or tampered
   handoffs are rejected before anything else runs.
2. ENFORCEMENT (this task): once shape+hash pass, receiving a handoff
   DERIVES A NEW certificate over the SUCCESSOR's state. This module never
   re-evaluates, recomputes, or mutates the predecessor's certificate or
   verdict (ADR-062 Claim 9) — the predecessor object passed in is read
   only. Gate authority stays with the controlplane (ADR-004/064): this
   module contains no R/S/N math and no threshold decision of its own; it
   only requests certification through the injected `certifier` port and
   reads the verdict that comes back. A passing predecessor never
   authorizes the successor — every hop is certified fresh.

Enforcement only runs when `cert_resolver` and `certifier` are supplied;
callers that omit them get exactly the Task 2 inert behavior.
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Optional

from swarm_it.governance.chain_kappa import ChainKappaTracker
from swarm_it.governance.envelope import HandoffEnvelope
from swarm_it.governance.trace import TraceRecord, emit

# Envelope producers must prefix payload_hash with this literal so receivers
# can identify the digest algorithm; validate_on_receive fails closed on any
# other prefix (or a missing one) because the hashes simply won't match.
HASH_PREFIX = "sha256:"


@dataclass(frozen=True)
class ReceiveVerdict:
    """Outcome of receive-boundary validation, inert or enforcement."""

    ok: bool
    reason: str
    handoff_id: Optional[str]
    new_certificate_ref: Optional[str] = None


def _hash_payload(payload: bytes) -> str:
    return HASH_PREFIX + hashlib.sha256(payload).hexdigest()


def _fail(envelope: HandoffEnvelope, reason: str, detail: Optional[dict] = None) -> ReceiveVerdict:
    verdict = ReceiveVerdict(ok=False, reason=reason, handoff_id=envelope.handoff_id)
    emit(
        TraceRecord(
            event="receive_boundary",
            reason=reason,
            handoff_id=envelope.handoff_id,
            detail=detail or {},
            trace_parent=envelope.trace_parent,
        )
    )
    return verdict


def _validate_shape(envelope: HandoffEnvelope, received_payload: bytes) -> ReceiveVerdict:
    """Shape+hash only. Never resolves input_certificate_ref, never derives
    or requests a gate outcome."""
    if not envelope.input_certificate_ref:
        return _fail(envelope, "MISSING_CERT_REF")

    actual_hash = _hash_payload(received_payload)
    if actual_hash != envelope.payload_hash:
        return _fail(
            envelope,
            "PAYLOAD_HASH_MISMATCH",
            {"expected": envelope.payload_hash, "actual": actual_hash},
        )

    verdict = ReceiveVerdict(ok=True, reason="SHAPE_OK", handoff_id=envelope.handoff_id)
    emit(
        TraceRecord(
            event="receive_boundary",
            reason=verdict.reason,
            handoff_id=envelope.handoff_id,
            detail={},
            trace_parent=envelope.trace_parent,
        )
    )
    return verdict


def _check_representation(
    envelope: HandoffEnvelope, successor_representation_id: Optional[str]
) -> Optional[ReceiveVerdict]:
    if successor_representation_id is None:
        return None
    if successor_representation_id != envelope.representation_id:
        return _fail(
            envelope,
            "INCOMPATIBLE_REPRESENTATION",
            {
                "envelope_representation_id": envelope.representation_id,
                "successor_representation_id": successor_representation_id,
            },
        )
    return None


def _check_stale(
    envelope: HandoffEnvelope, predecessor: Any, now_epoch: Optional[float]
) -> Optional[ReceiveVerdict]:
    # Staleness is only assessed when both the predecessor exposes an
    # expiry and the caller injects "now" — this module never reads the
    # wall clock itself (no time/datetime calls).
    expires_at = getattr(predecessor, "expires_at", None)
    if expires_at is None or now_epoch is None:
        return None
    if now_epoch >= expires_at:
        return _fail(envelope, "STALE_CERT", {"expires_at": expires_at, "now_epoch": now_epoch})
    return None


def _derived_verdict_ok(derived: Any) -> bool:
    # Duck-typed: real controlplane certs expose .allowed; simple test
    # doubles may only expose .verdict == "EXECUTE". Neither present means
    # the outcome can't be confirmed, so it fails closed.
    if hasattr(derived, "allowed"):
        return bool(derived.allowed)
    if hasattr(derived, "verdict"):
        return derived.verdict == "EXECUTE"
    return False


def _check_recert(envelope: HandoffEnvelope, derived: Any) -> Optional[ReceiveVerdict]:
    if not _derived_verdict_ok(derived):
        return _fail(envelope, "RECERT_REFUSED", {"derived_certificate_id": getattr(derived, "id", None)})
    return None


def _check_chain_kappa(
    envelope: HandoffEnvelope, derived: Any, min_chain_kappa: Optional[float]
) -> Optional[ReceiveVerdict]:
    tracker = ChainKappaTracker.from_envelope(envelope)
    hop_kappa = getattr(derived, "kappa_compat", None)
    state = tracker.observe(envelope, hop_kappa)

    if state.incomparable:
        return _fail(envelope, "CHAIN_KAPPA_INCOMPARABLE", {"chain_kappa_min": state.chain_kappa_min})
    if min_chain_kappa is not None and (state.chain_kappa_min is None or state.chain_kappa_min < min_chain_kappa):
        return _fail(
            envelope,
            "CHAIN_KAPPA_BELOW_THRESHOLD",
            {"chain_kappa_min": state.chain_kappa_min, "min_chain_kappa": min_chain_kappa},
        )
    return None


def validate_on_receive(
    envelope: HandoffEnvelope,
    received_payload: bytes,
    *,
    successor_representation_id: Optional[str] = None,
    cert_resolver: Optional[Callable[[str], Optional[Any]]] = None,
    certifier: Optional[Callable[[Any], Any]] = None,
    successor_state: Optional[Any] = None,
    now_epoch: Optional[float] = None,
    min_chain_kappa: Optional[float] = None,
) -> ReceiveVerdict:
    """Validate an incoming envelope, then (if enforcement ports are
    supplied) re-derive a fresh certificate over the successor's state.

    Inert mode (cert_resolver and certifier both None): shape+hash only,
    identical to Task 2.

    Enforcement mode (both supplied): after shape+hash pass, resolves the
    predecessor certificate, checks representation compatibility and
    staleness, then calls certifier(successor_state) to derive a NEW
    certificate — never re-evaluating or mutating the predecessor. A
    refusing (non-EXECUTE) derived verdict fails closed regardless of the
    predecessor's own verdict: no inherited trust. Chain-kappa is updated
    from the derived certificate's kappa_compat; an incomparable chain, or
    one below `min_chain_kappa` (when given), also fails closed.
    """
    shape_verdict = _validate_shape(envelope, received_payload)
    if not shape_verdict.ok:
        return shape_verdict

    if cert_resolver is None and certifier is None:
        return shape_verdict

    predecessor = cert_resolver(envelope.input_certificate_ref)
    if predecessor is None:
        return _fail(envelope, "UNRESOLVED_CERT", {"input_certificate_ref": envelope.input_certificate_ref})

    representation_failure = _check_representation(envelope, successor_representation_id)
    if representation_failure is not None:
        return representation_failure

    stale_failure = _check_stale(envelope, predecessor, now_epoch)
    if stale_failure is not None:
        return stale_failure

    derived = certifier(successor_state)

    recert_failure = _check_recert(envelope, derived)
    if recert_failure is not None:
        return recert_failure

    chain_failure = _check_chain_kappa(envelope, derived, min_chain_kappa)
    if chain_failure is not None:
        return chain_failure

    verdict = ReceiveVerdict(
        ok=True,
        reason="RECERTIFIED",
        handoff_id=envelope.handoff_id,
        new_certificate_ref=derived.id,
    )
    emit(
        TraceRecord(
            event="receive_boundary",
            reason=verdict.reason,
            handoff_id=envelope.handoff_id,
            detail={"new_certificate_ref": derived.id},
            trace_parent=envelope.trace_parent,
        )
    )
    return verdict
