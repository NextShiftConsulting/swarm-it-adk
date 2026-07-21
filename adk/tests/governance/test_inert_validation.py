"""Tests for the inert receive-boundary validation layer.

This layer validates SHAPE and HASH only. It never resolves a certificate
and never derives a gate outcome — it only decides whether an incoming
HandoffEnvelope + payload are well-formed enough to be handed to the
(later) certificate-resolution step. Fail-closed: anything missing or
mismatched returns ok=False.
"""

import hashlib

import pytest

from swarm_it.governance import HandoffEnvelope
from swarm_it.governance import (
    CycleGuard,
    ReceiveVerdict,
    TraceRecord,
    emit,
    get_trace,
    reset_trace,
    validate_on_receive,
)


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


def _make_envelope(**overrides) -> HandoffEnvelope:
    fields = dict(
        task_id="task-001",
        handoff_id="handoff-001",
        sender_id="agent-a",
        receiver_id="agent-b",
        input_certificate_ref="cert-abc123",
        artifact_hashes=("hash1", "hash2"),
        payload_hash=GOOD_HASH,
        representation_id="rep-1",
        environment_id="env-1",
        prior_chain_kappa_min=0.72,
        prior_chain_dispersion=0.05,
        prior_hops=2,
        requested_capability="analyze",
        topology_pattern="pipeline",
        policy_version="v1",
        created_at="2026-07-20T00:00:00Z",
        replay_seed=42,
        trace_parent="trace-xyz",
    )
    fields.update(overrides)
    return HandoffEnvelope(**fields)


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_trace()
    yield
    reset_trace()


def test_hash_mismatch_fails_closed_and_traces():
    env = _make_envelope()

    verdict = validate_on_receive(env, b"TAMPERED")

    assert verdict.ok is False
    assert verdict.reason == "PAYLOAD_HASH_MISMATCH"
    assert verdict.handoff_id == env.handoff_id

    trace = get_trace()
    assert trace[-1].reason == "PAYLOAD_HASH_MISMATCH"
    assert trace[-1].handoff_id == env.handoff_id


def test_hash_match_shape_ok():
    env = _make_envelope()

    verdict = validate_on_receive(env, GOOD_PAYLOAD)

    assert verdict.ok is True
    assert verdict.reason == "SHAPE_OK"
    assert verdict.handoff_id == env.handoff_id


def test_missing_cert_ref_fails_closed():
    env = _make_envelope(input_certificate_ref="")

    verdict = validate_on_receive(env, GOOD_PAYLOAD)

    assert verdict.ok is False
    assert verdict.reason == "MISSING_CERT_REF"


def test_cycle_guard_xor():
    with CycleGuard.enter("handoff"):
        with pytest.raises(RuntimeError):
            with CycleGuard.enter("repair"):
                pass

        # Re-entering the SAME mode nested inside itself must not raise.
        with CycleGuard.enter("handoff"):
            pass


def test_trace_is_append_only():
    record_a = TraceRecord(event="a", reason="first", handoff_id="h1", detail={}, trace_parent=None)
    record_b = TraceRecord(event="b", reason="second", handoff_id="h2", detail={}, trace_parent=None)

    emit(record_a)
    emit(record_b)

    trace = get_trace()

    assert isinstance(trace, tuple)
    assert trace == (record_a, record_b)
