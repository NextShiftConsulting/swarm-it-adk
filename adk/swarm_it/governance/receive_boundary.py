"""Inert receive-boundary validation for HandoffEnvelope.

This is SHAPE and HASH validation only. It never resolves
input_certificate_ref against the controlplane and never derives or
requests a gate outcome — that resolution happens later, against the
authoritative controlplane, by a separate component. This layer exists
so a malformed or tampered handoff is rejected before it ever reaches
that resolution step. Fail-closed: anything missing or mismatched
returns ok=False.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional

from swarm_it.governance.envelope import HandoffEnvelope
from swarm_it.governance.trace import TraceRecord, emit


@dataclass(frozen=True)
class ReceiveVerdict:
    """Outcome of inert shape+hash validation at a receive boundary."""

    ok: bool
    reason: str
    handoff_id: Optional[str]


def _hash_payload(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_on_receive(envelope: HandoffEnvelope, received_payload: bytes) -> ReceiveVerdict:
    """Validate an incoming envelope's shape and payload hash. Fail-closed.

    Does not resolve input_certificate_ref and does not compute a gate
    outcome — this only rejects malformed or tampered handoffs before
    certificate resolution happens elsewhere.
    """
    if not envelope.input_certificate_ref:
        verdict = ReceiveVerdict(ok=False, reason="MISSING_CERT_REF", handoff_id=envelope.handoff_id)
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

    actual_hash = _hash_payload(received_payload)
    if actual_hash != envelope.payload_hash:
        verdict = ReceiveVerdict(ok=False, reason="PAYLOAD_HASH_MISMATCH", handoff_id=envelope.handoff_id)
        emit(
            TraceRecord(
                event="receive_boundary",
                reason=verdict.reason,
                handoff_id=envelope.handoff_id,
                detail={"expected": envelope.payload_hash, "actual": actual_hash},
                trace_parent=envelope.trace_parent,
            )
        )
        return verdict

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
