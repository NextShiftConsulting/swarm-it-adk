"""Tests for PIPELINE topology acceptance policy (V-013 T6).

Pipeline hops are threaded through a single ChainKappaTracker, in order:
the weakest hop gates the whole chain, and gating_hop identifies the FIRST
hop whose observation drove the running min below the threshold.
"""

import hashlib

import pytest

from swarm_it.governance import HandoffEnvelope, get_trace, reset_trace
from swarm_it.governance.topology_policy import HopInput, TopologyDecision, accept_pipeline
from swarm_it.topology.patterns import SwarmPattern


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


def _make_envelope(**overrides) -> HandoffEnvelope:
    fields = dict(
        task_id="task-001",
        handoff_id="handoff-001",
        sender_id="agent-a",
        receiver_id="agent-b",
        input_certificate_ref="cert-abc123",
        artifact_hashes=("hash1",),
        payload_hash=GOOD_HASH,
        representation_id="rep-1",
        environment_id="env-1",
        prior_chain_kappa_min=None,
        prior_chain_dispersion=None,
        prior_hops=0,
        requested_capability="analyze",
        topology_pattern=SwarmPattern.PIPELINE.value,
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


def _make_hops(kappas):
    hops = []
    for i, k in enumerate(kappas):
        hops.append(
            HopInput(
                envelope=_make_envelope(handoff_id=f"h{i}"),
                produced_payload=GOOD_PAYLOAD,
                successor_representation_id="rep-1",
                successor_state={"i": i},
                hop_kappa=k,
            )
        )
    return hops


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_trace()
    yield
    reset_trace()


def test_pipeline_weakest_hop_gates_chain():
    hops = _make_hops([0.8, 0.4, 0.9])

    decision = accept_pipeline(hops, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    assert isinstance(decision, TopologyDecision)
    assert decision.verdict == "REFUSE"
    assert decision.gating_hop == 1


def test_pipeline_all_healthy_executes():
    hops = _make_hops([0.8, 0.7, 0.9])

    decision = accept_pipeline(hops, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    assert decision.verdict == "EXECUTE"
    assert decision.gating_hop is None


def test_pipeline_emits_trace_record():
    hops = _make_hops([0.8, 0.7])

    accept_pipeline(hops, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    trace = get_trace()
    assert len(trace) >= 1
    assert trace[-1].event == "topology_decision"
