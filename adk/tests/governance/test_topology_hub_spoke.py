"""Tests for HUB_SPOKE topology acceptance policy (V-013 T6).

Each spoke handoff is evaluated INDEPENDENTLY (its own ChainKappaTracker).
The hub aggregates: any failing spoke must REFUSE the whole hub result
(a failing spoke must never be silently passed through), and gating_hop
must identify the failing spoke's index.
"""

import hashlib

import pytest

from swarm_it.governance import HandoffEnvelope, get_trace, reset_trace
from swarm_it.governance.topology_policy import HopInput, accept_hub_spoke
from swarm_it.topology.patterns import SwarmPattern


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


def _make_envelope(**overrides) -> HandoffEnvelope:
    fields = dict(
        task_id="task-001",
        handoff_id="handoff-001",
        sender_id="agent-hub",
        receiver_id="agent-spoke-0",
        input_certificate_ref="cert-abc123",
        artifact_hashes=("hash1",),
        payload_hash=GOOD_HASH,
        representation_id="rep-1",
        environment_id="env-1",
        prior_chain_kappa_min=None,
        prior_chain_dispersion=None,
        prior_hops=0,
        requested_capability="analyze",
        topology_pattern=SwarmPattern.HUB_SPOKE.value,
        policy_version="v1",
        created_at="2026-07-20T00:00:00Z",
        replay_seed=42,
        trace_parent=None,
    )
    fields.update(overrides)
    return HandoffEnvelope(**fields)


def _fake_certifier_always_execute(_state):
    class _Cert:
        id = "cert-derived"
        verdict = "EXECUTE"

    return _Cert()


def _make_spokes(kappas):
    hops = []
    for i, k in enumerate(kappas):
        hops.append(
            HopInput(
                envelope=_make_envelope(handoff_id=f"spoke-{i}", receiver_id=f"agent-spoke-{i}"),
                produced_payload=GOOD_PAYLOAD,
                successor_representation_id="rep-1",
                successor_state={"spoke": i},
                hop_kappa=k,
            )
        )
    return hops


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_trace()
    yield
    reset_trace()


def test_hub_spoke_one_failing_spoke_refuses():
    spokes = _make_spokes([0.8, 0.2, 0.9])

    decision = accept_hub_spoke(spokes, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    assert decision.verdict == "REFUSE"
    assert decision.gating_hop == 1


def test_hub_spoke_all_healthy_executes():
    spokes = _make_spokes([0.8, 0.7, 0.9])

    decision = accept_hub_spoke(spokes, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    assert decision.verdict == "EXECUTE"
    assert decision.gating_hop is None


def test_hub_spoke_each_evaluated_independently():
    """A weak spoke must not drag down a later, independently-healthy
    spoke's own evaluation — each spoke gets its own tracker, so this is
    only observable via the REFUSE happening at the correct spoke index."""
    spokes = _make_spokes([0.2, 0.9, 0.9])

    decision = accept_hub_spoke(spokes, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    assert decision.verdict == "REFUSE"
    assert decision.gating_hop == 0


def test_hub_spoke_emits_trace_record():
    spokes = _make_spokes([0.8, 0.7])

    accept_hub_spoke(spokes, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    trace = get_trace()
    assert len(trace) >= 1
    assert trace[-1].event == "topology_decision"
