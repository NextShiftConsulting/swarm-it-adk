"""Tests for MESH topology acceptance policy (V-013 T6).

Every edge in a mesh evaluation is a governed handoff. No path may inherit
authorization from an untraversed edge: an edge whose envelope.trace_parent
does not correspond to an already-traversed edge in THIS mesh evaluation
must REFUSE with reason="UNTRAVERSED_PARENT".
"""

import hashlib

import pytest

from swarm_it.governance import HandoffEnvelope, get_trace, reset_trace
from swarm_it.governance.topology_policy import HopInput, accept_mesh
from swarm_it.topology.patterns import SwarmPattern


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


def _make_envelope(**overrides) -> HandoffEnvelope:
    fields = dict(
        task_id="task-001",
        handoff_id="edge-001",
        sender_id="agent-0",
        receiver_id="agent-1",
        input_certificate_ref="cert-abc123",
        artifact_hashes=("hash1",),
        payload_hash=GOOD_HASH,
        representation_id="rep-1",
        environment_id="env-1",
        prior_chain_kappa_min=None,
        prior_chain_dispersion=None,
        prior_hops=0,
        requested_capability="analyze",
        topology_pattern=SwarmPattern.MESH.value,
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


def _hop(handoff_id, trace_parent, kappa=0.8):
    return HopInput(
        envelope=_make_envelope(handoff_id=handoff_id, trace_parent=trace_parent),
        produced_payload=GOOD_PAYLOAD,
        successor_representation_id="rep-1",
        successor_state={"edge": handoff_id},
        hop_kappa=kappa,
    )


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_trace()
    yield
    reset_trace()


def test_mesh_untraversed_parent_refuses():
    hops = [
        _hop("edge-A", trace_parent=None),
        # edge-B claims a parent ("edge-ghost") that was never traversed.
        _hop("edge-B", trace_parent="edge-ghost"),
    ]

    decision = accept_mesh(hops, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    assert decision.verdict == "REFUSE"
    assert decision.reason == "UNTRAVERSED_PARENT"
    assert decision.gating_hop == 1


def test_mesh_properly_parented_executes():
    hops = [
        _hop("edge-A", trace_parent=None),
        _hop("edge-B", trace_parent="edge-A"),
        _hop("edge-C", trace_parent="edge-B"),
    ]

    decision = accept_mesh(hops, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    assert decision.verdict == "EXECUTE"
    assert decision.gating_hop is None


def test_mesh_emits_trace_record():
    hops = [_hop("edge-A", trace_parent=None)]

    accept_mesh(hops, certifier=_fake_certifier_always_execute, min_chain_kappa=0.5)

    trace = get_trace()
    assert len(trace) >= 1
    assert trace[-1].event == "topology_decision"
