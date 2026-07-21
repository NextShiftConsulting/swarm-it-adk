"""Tests for the accept() topology dispatcher (V-013 T6).

accept() must route each SwarmPattern to its own per-topology handler
(never a shared default), and fail closed with reason="UNSUPPORTED_TOPOLOGY"
for any pattern outside the T6 scope (PIPELINE/HUB_SPOKE/MESH).
"""

import dataclasses
import hashlib
from typing import Optional

import pytest

from swarm_it.governance import HandoffEnvelope, reset_trace
from swarm_it.governance.topology_policy import HopInput, accept
from swarm_it.topology.patterns import SwarmPattern


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


@dataclasses.dataclass
class FakeCert:
    id: str
    verdict: str
    kappa_compat: Optional[float] = None
    expires_at: Optional[float] = None


def _make_envelope(pattern: SwarmPattern, **overrides) -> HandoffEnvelope:
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
        topology_pattern=pattern.value,
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
    return FakeCert(id="cert-derived", verdict="EXECUTE", kappa_compat=0.9)


def _one_hop(pattern: SwarmPattern) -> list:
    return [
        HopInput(
            envelope=_make_envelope(pattern),
            produced_payload=GOOD_PAYLOAD,
            successor_representation_id="rep-1",
            successor_state={"i": 0},
            hop_kappa=0.9,
        )
    ]


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_trace()
    yield
    reset_trace()


@pytest.mark.parametrize(
    "pattern,expected_reason",
    [
        (SwarmPattern.PIPELINE, "CHAIN_HEALTHY"),
        (SwarmPattern.HUB_SPOKE, "ALL_SPOKES_HEALTHY"),
        (SwarmPattern.MESH, "MESH_HEALTHY"),
    ],
)
def test_accept_dispatches_to_each_topology(pattern, expected_reason):
    hops = _one_hop(pattern)

    decision = accept(
        pattern, hops, certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "EXECUTE"
    assert decision.reason == expected_reason


def test_accept_ring_refuses_unsupported():
    hops = _one_hop(SwarmPattern.RING)

    decision = accept(
        SwarmPattern.RING, hops, certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "REFUSE"
    assert decision.reason == "UNSUPPORTED_TOPOLOGY"


def test_accept_hierarchical_refuses_unsupported():
    hops = _one_hop(SwarmPattern.HIERARCHICAL)

    decision = accept(
        SwarmPattern.HIERARCHICAL,
        hops,
        certifier=_fake_certifier_always_execute,
        cert_resolver=_cert_resolver,
        min_chain_kappa=0.5,
    )

    assert decision.verdict == "REFUSE"
    assert decision.reason == "UNSUPPORTED_TOPOLOGY"
