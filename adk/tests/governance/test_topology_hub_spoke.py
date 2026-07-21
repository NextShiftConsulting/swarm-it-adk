"""Tests for HUB_SPOKE topology acceptance policy (V-013 T6).

Each spoke handoff is routed through the real receive/output boundaries
and evaluated INDEPENDENTLY (its own ChainKappaTracker). The hub
aggregates: any failing spoke must REFUSE the whole hub result (a
failing spoke must never be silently passed through), and gating_hop
must identify the failing spoke's index.
"""

import dataclasses
import hashlib
from typing import Optional

import pytest

from swarm_it.governance import HandoffEnvelope, get_trace, reset_trace
from swarm_it.governance.topology_policy import HopInput, accept_hub_spoke
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


def _cert_resolver(_ref):
    return FakeCert(id="cert-predecessor", verdict="EXECUTE", kappa_compat=0.9)


def _certifier_from_kappas(kappas):
    def certifier(state):
        i = state["spoke"]
        return FakeCert(id=f"cert-derived-{i}", verdict="EXECUTE", kappa_compat=kappas[i])

    return certifier


def _fake_certifier_always_execute(_state):
    return FakeCert(id="cert-derived", verdict="EXECUTE", kappa_compat=0.9)


def _make_spokes(kappas, representation_ids=None):
    hops = []
    for i, k in enumerate(kappas):
        rep = representation_ids[i] if representation_ids else "rep-1"
        hops.append(
            HopInput(
                envelope=_make_envelope(
                    handoff_id=f"spoke-{i}", receiver_id=f"agent-spoke-{i}", representation_id=rep
                ),
                produced_payload=GOOD_PAYLOAD,
                successor_representation_id=rep,
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

    decision = accept_hub_spoke(
        spokes, certifier=_certifier_from_kappas([0.8, 0.2, 0.9]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "REFUSE"
    assert decision.gating_hop == 1


def test_hub_spoke_all_healthy_executes():
    spokes = _make_spokes([0.8, 0.7, 0.9])

    decision = accept_hub_spoke(
        spokes, certifier=_certifier_from_kappas([0.8, 0.7, 0.9]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "EXECUTE"
    assert decision.gating_hop is None


def test_hub_spoke_each_evaluated_independently():
    """Two spokes on DIFFERENT representation_ids, each independently
    healthy, must both EXECUTE. A SHARED tracker across spokes would
    instead treat spoke 1's differing representation as a chain-kappa
    clash against spoke 0's baseline and wrongly REFUSE
    (SPOKE_CHAIN_KAPPA_INCOMPARABLE) -- so this test FAILS against a
    shared-tracker implementation, unlike a test that only checks the
    first failing spoke's index (which passes either way)."""
    spokes = _make_spokes([0.9, 0.85], representation_ids=["rep-A", "rep-B"])

    decision = accept_hub_spoke(
        spokes, certifier=_certifier_from_kappas([0.9, 0.85]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "EXECUTE"
    assert decision.gating_hop is None


def test_hub_spoke_emits_trace_record():
    spokes = _make_spokes([0.8, 0.7])

    accept_hub_spoke(
        spokes, certifier=_certifier_from_kappas([0.8, 0.7]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    trace = get_trace()
    assert len(trace) >= 1
    assert trace[-1].event == "topology_decision"
