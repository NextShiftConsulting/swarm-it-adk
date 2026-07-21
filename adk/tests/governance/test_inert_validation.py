"""Tests for the inert receive-boundary validation layer.

This layer validates SHAPE and HASH only. It never resolves a certificate
and never derives a gate outcome — it only decides whether an incoming
HandoffEnvelope + payload are well-formed enough to be handed to the
(later) certificate-resolution step. Fail-closed: anything missing or
mismatched returns ok=False.
"""

import asyncio
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


def test_trace_detail_is_immutable():
    original_detail = {"expected": "sha256:abc", "actual": "sha256:def"}
    record = TraceRecord(
        event="receive_boundary",
        reason="PAYLOAD_HASH_MISMATCH",
        handoff_id="h1",
        detail=original_detail,
        trace_parent=None,
    )

    emit(record)
    stored = get_trace()[-1]

    with pytest.raises(TypeError):
        stored.detail["expected"] = "tampered"

    # Mutating the caller's original dict after construction must not reach
    # into the stored record either — the record owns its own copy.
    original_detail["expected"] = "tampered-at-source"
    assert stored.detail["expected"] == "sha256:abc"


async def test_cycle_guard_xor_across_await():
    """Within a single logical flow, entering the opposite mode must still
    raise on the far side of an `await` suspension."""
    with CycleGuard.enter("handoff"):
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError):
            with CycleGuard.enter("repair"):
                pass


async def test_cycle_guard_isolates_unrelated_concurrent_tasks():
    """The bug threading.local actually has: two independent asyncio Tasks
    running concurrently on the same OS thread share one threading.local,
    so an unrelated "repair" task gets a false-positive RuntimeError just
    because some other task is mid-"handoff". contextvars.ContextVar gives
    each Task its own copy-on-write context, so unrelated tasks must not
    see each other's CycleGuard state at all."""
    repair_raised = False
    handoff_seen_active = asyncio.Event()

    async def run_handoff():
        with CycleGuard.enter("handoff"):
            handoff_seen_active.set()
            await asyncio.sleep(0.02)

    async def run_repair():
        nonlocal repair_raised
        await handoff_seen_active.wait()
        try:
            with CycleGuard.enter("repair"):
                pass
        except RuntimeError:
            repair_raised = True

    await asyncio.gather(run_handoff(), run_repair())

    assert repair_raised is False


def test_missing_cert_ref_and_hash_mismatch_precedence():
    """When both a missing cert ref AND a payload-hash mismatch are present,
    the missing-cert-ref check runs first (validate_on_receive returns before
    ever computing the payload hash), so MISSING_CERT_REF wins."""
    env = _make_envelope(input_certificate_ref="")

    verdict = validate_on_receive(env, b"TAMPERED")

    assert verdict.ok is False
    assert verdict.reason == "MISSING_CERT_REF"


def test_no_prohibited_tokens_in_source():
    from pathlib import Path

    from swarm_it.governance import cycle_guard, receive_boundary, trace

    for module in (trace, cycle_guard, receive_boundary):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "sigma" not in source.lower(), f"'sigma' found in {module.__file__}"
        assert "kappa_gate" not in source.lower(), f"'kappa_gate' found in {module.__file__}"
