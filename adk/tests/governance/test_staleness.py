"""Tests for STALE_CERT activation via NormalizedCertificate (V-013 I3).

_check_stale reads `getattr(predecessor, "expires_at", None)`. Neither real
controlplane cert type (RSCTCertificate, SwarmCertificate) currently
exposes `expires_at`, so the check is a None-safe no-op against them today
(see receive_boundary._check_stale). certifier_adapter.NormalizedCertificate
DOES carry `expires_at` — these tests prove the mechanism actually fires
(and correctly does NOT fire) once a real normalized cert supplies one.
"""

import dataclasses
import hashlib
from typing import Optional

import pytest

from swarm_it.governance import HandoffEnvelope, get_trace, reset_trace, validate_on_receive
from swarm_it.governance.certifier_adapter import NormalizedCertificate

GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


@dataclasses.dataclass
class FakeCert:
    """Minimal cert-like double for the freshly-derived successor cert."""

    id: str
    verdict: str
    kappa_compat: Optional[float] = None
    expires_at: Optional[float] = None


def _make_envelope(**overrides) -> HandoffEnvelope:
    fields = dict(
        task_id="task-001",
        handoff_id="handoff-001",
        sender_id="agent-a",
        receiver_id="agent-b",
        input_certificate_ref="cert-A",
        artifact_hashes=("hash1", "hash2"),
        payload_hash=GOOD_HASH,
        representation_id="rep-1",
        environment_id="env-1",
        prior_chain_kappa_min=None,
        prior_chain_dispersion=None,
        prior_hops=0,
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


def test_stale_normalized_cert_fails_closed():
    """A NormalizedCertificate predecessor with expires_at in the past
    (relative to the injected now_epoch) must fail closed with STALE_CERT
    — proving the mechanism is live, not just inert-safe, against a real
    normalized certificate shape."""
    env = _make_envelope()
    predecessor = NormalizedCertificate(id="cert-A", kappa_compat=0.6, allowed=True, expires_at=100.0)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=lambda state: FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=0.7),
        now_epoch=200.0,
        min_chain_kappa=0.5,
    )

    assert verdict.ok is False
    assert verdict.reason == "STALE_CERT"
    assert verdict.new_certificate_ref is None

    trace = get_trace()
    assert trace[-1].reason == "STALE_CERT"
    assert trace[-1].handoff_id == env.handoff_id


def test_non_stale_normalized_cert_passes_stale_check():
    """A NormalizedCertificate predecessor whose expiry is still in the
    future must proceed past the stale check (reason must not be
    STALE_CERT) — the mechanism must not false-positive on a live cert."""
    env = _make_envelope()
    predecessor = NormalizedCertificate(id="cert-A", kappa_compat=0.6, allowed=True, expires_at=300.0)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=lambda state: FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=0.7),
        now_epoch=200.0,
        min_chain_kappa=0.5,
    )

    assert verdict.reason != "STALE_CERT"
    assert verdict.ok is True
    assert verdict.reason == "RECERTIFIED"

