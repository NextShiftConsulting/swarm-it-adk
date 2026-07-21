"""Tests for MESH topology acceptance policy (V-013 T6).

Every edge in a mesh evaluation is a governed handoff, routed through the
real receive/output boundaries inside CycleGuard.enter("handoff"). No path
may inherit authorization from an untraversed edge: an edge whose
envelope.trace_parent does not correspond to an already-traversed edge in
THIS mesh evaluation must REFUSE with reason="UNTRAVERSED_PARENT". Each
connected lineage (traced back to its root edge) gets its own
ChainKappaTracker so an unrelated, unhealthy lineage cannot poison a
healthy one.
"""

import dataclasses
import hashlib
from typing import Optional

import pytest

from swarm_it.governance import HandoffEnvelope, get_trace, reset_trace
from swarm_it.governance.topology_policy import HopInput, accept_mesh
from swarm_it.topology.patterns import SwarmPattern


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


@dataclasses.dataclass
class FakeCert:
    """Minimal cert-like double: .id, .verdict, .kappa_compat, .expires_at."""

    id: str
    verdict: str
    kappa_compat: Optional[float] = None
    expires_at: Optional[float] = None


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


def _cert_resolver(_ref):
    return FakeCert(id="cert-predecessor", verdict="EXECUTE", kappa_compat=0.9)


def _fake_certifier_always_execute(_state):
    # A fixed, comparable kappa_compat -- each mesh test in this file
    # constructs hops one at a time, so the receive boundary's own
    # (single-hop, per-call) chain-kappa read never spuriously fails on
    # a missing kappa_compat.
    return FakeCert(id="cert-derived", verdict="EXECUTE", kappa_compat=0.8)


def _hop(handoff_id, trace_parent, kappa=0.8, representation_id="rep-1"):
    return HopInput(
        envelope=_make_envelope(handoff_id=handoff_id, trace_parent=trace_parent, representation_id=representation_id),
        produced_payload=GOOD_PAYLOAD,
        successor_representation_id=representation_id,
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

    decision = accept_mesh(hops, certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5)

    assert decision.verdict == "REFUSE"
    assert decision.reason == "UNTRAVERSED_PARENT"
    assert decision.gating_hop == 1


def test_mesh_properly_parented_executes():
    hops = [
        _hop("edge-A", trace_parent=None),
        _hop("edge-B", trace_parent="edge-A"),
        _hop("edge-C", trace_parent="edge-B"),
    ]

    decision = accept_mesh(hops, certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5)

    assert decision.verdict == "EXECUTE"
    assert decision.gating_hop is None


def test_mesh_emits_trace_record():
    hops = [_hop("edge-A", trace_parent=None)]

    accept_mesh(hops, certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5)

    trace = get_trace()
    assert len(trace) >= 1
    assert trace[-1].event == "topology_decision"


def test_mesh_unrelated_lineages_isolated():
    """Two independent root edges (different representation_ids) must
    each get their OWN chain-kappa tracker: an unrelated lineage's
    representation must never poison another lineage's own tracker.

    good-root starts a healthy lineage (rep-good). bad-root starts an
    UNRELATED lineage (rep-bad) -- under a shared-tracker bug, bad-root
    would immediately fail as CHAIN_KAPPA_INCOMPARABLE merely for
    disagreeing with good-root's representation (gating_hop=1). Under the
    correct per-lineage tracker, bad-root passes cleanly as its own
    lineage's root; only bad-child (a THIRD, incompatible representation
    within the bad lineage itself) trips the incomparable failure
    (gating_hop=2) -- proving the bad lineage's own internal weakness is
    what REFUSEs, not a cross-lineage clash with the healthy root.
    """
    hops = [
        _hop("good-root", trace_parent=None, kappa=0.8, representation_id="rep-good"),
        _hop("bad-root", trace_parent=None, kappa=0.8, representation_id="rep-bad"),
        _hop("bad-child", trace_parent="bad-root", kappa=0.8, representation_id="rep-other"),
    ]

    decision = accept_mesh(hops, certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5)

    assert decision.verdict == "REFUSE"
    assert decision.reason == "CHAIN_KAPPA_INCOMPARABLE"
    assert decision.gating_hop == 2

    # Isolation proof: the healthy lineage, evaluated on its own, still
    # EXECUTEs -- it was never poisoned by the unrelated bad lineage.
    good_only = accept_mesh(hops[:1], certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5)
    assert good_only.verdict == "EXECUTE"
