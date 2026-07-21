"""Tests for the receive-boundary ENFORCEMENT path (V-013 T4).

After the inert shape+hash checks pass, receiving a handoff must derive a
NEW certificate over the successor's state (never recompute or mutate the
predecessor's certificate/verdict — ADR-062 Claim 9), and gate authority
stays with the injected `certifier` port (ADR-004/064) — this module
contains no gate math of its own. Everything here is fail-closed.
"""

import copy
import dataclasses
import hashlib
from typing import Optional

import pytest

from swarm_it.governance import HandoffEnvelope
from swarm_it.governance import get_trace, reset_trace, validate_on_receive


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


@dataclasses.dataclass
class FakeCert:
    """Minimal cert-like double: .id, .verdict, .kappa_compat.

    Stands in for a real controlplane-issued certificate (e.g.
    RSCTCertificate) without pulling in any gate math.
    """

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


def test_receive_derives_new_cert_never_mutates_predecessor():
    """Enforcement derives a NEW cert over successor state; the predecessor
    object must be byte-identical (same id, same verdict) before and after."""
    env = _make_envelope()
    predecessor = FakeCert(id="cert-A", verdict="EXECUTE", kappa_compat=0.6)
    predecessor_snapshot = copy.deepcopy(predecessor)

    def cert_resolver(ref):
        assert ref == env.input_certificate_ref
        return predecessor

    def certifier(successor_state):
        return FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=0.7)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=cert_resolver,
        certifier=certifier,
        successor_state={"intermediate": "state"},
        now_epoch=1_000.0,
    )

    assert verdict.ok is True
    assert verdict.new_certificate_ref == "cert-B"
    assert verdict.new_certificate_ref != predecessor.id
    assert predecessor == predecessor_snapshot


def test_unresolvable_cert_ref_fails_closed():
    env = _make_envelope()

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: None,
        certifier=lambda state: FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=0.7),
    )

    assert verdict.ok is False
    assert verdict.reason == "UNRESOLVED_CERT"
    assert verdict.new_certificate_ref is None

    trace = get_trace()
    assert trace[-1].reason == "UNRESOLVED_CERT"
    assert trace[-1].handoff_id == env.handoff_id


def test_representation_mismatch_fails_closed():
    env = _make_envelope(representation_id="rep-1")
    predecessor = FakeCert(id="cert-A", verdict="EXECUTE", kappa_compat=0.6)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id="rep-2",
        cert_resolver=lambda ref: predecessor,
        certifier=lambda state: FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=0.7),
    )

    assert verdict.ok is False
    assert verdict.reason == "INCOMPATIBLE_REPRESENTATION"
    assert verdict.new_certificate_ref is None


def test_recert_refused_fails_closed():
    env = _make_envelope()
    predecessor = FakeCert(id="cert-A", verdict="EXECUTE", kappa_compat=0.6)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=lambda state: FakeCert(id="cert-B", verdict="REPAIR", kappa_compat=0.1),
    )

    assert verdict.ok is False
    assert verdict.reason == "RECERT_REFUSED"
    assert verdict.new_certificate_ref is None


def test_no_inherited_trust():
    """A passing predecessor must NOT authorize the successor: the
    successor is certified fresh regardless of the predecessor's verdict."""
    env = _make_envelope()
    predecessor = FakeCert(id="cert-A", verdict="EXECUTE", kappa_compat=0.9)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=lambda state: FakeCert(id="cert-B", verdict="BLOCK", kappa_compat=0.05),
    )

    assert verdict.ok is False
    assert verdict.reason == "RECERT_REFUSED"


def test_inert_mode_unchanged():
    """Without cert_resolver/certifier, behavior must be exactly the Task 2
    inert shape+hash path."""
    env = _make_envelope()

    verdict = validate_on_receive(env, GOOD_PAYLOAD)

    assert verdict.ok is True
    assert verdict.reason == "SHAPE_OK"
    assert verdict.handoff_id == env.handoff_id
    assert verdict.new_certificate_ref is None


def test_shape_failure_short_circuits_before_enforcement():
    """A hash mismatch must fail before cert_resolver/certifier are ever
    invoked — the inert checks run first."""
    env = _make_envelope()
    called = {"resolver": False, "certifier": False}

    def cert_resolver(ref):
        called["resolver"] = True
        return FakeCert(id="cert-A", verdict="EXECUTE", kappa_compat=0.6)

    def certifier(state):
        called["certifier"] = True
        return FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=0.7)

    verdict = validate_on_receive(
        env,
        b"TAMPERED",
        successor_representation_id=env.representation_id,
        cert_resolver=cert_resolver,
        certifier=certifier,
    )

    assert verdict.ok is False
    assert verdict.reason == "PAYLOAD_HASH_MISMATCH"
    assert called["resolver"] is False
    assert called["certifier"] is False


def test_stale_cert_fails_closed():
    env = _make_envelope()
    predecessor = FakeCert(id="cert-A", verdict="EXECUTE", kappa_compat=0.6, expires_at=500.0)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=lambda state: FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=0.7),
        now_epoch=600.0,
    )

    assert verdict.ok is False
    assert verdict.reason == "STALE_CERT"


def test_chain_kappa_below_threshold_fails_closed():
    env = _make_envelope(prior_chain_kappa_min=0.9, prior_hops=1)
    predecessor = FakeCert(id="cert-A", verdict="EXECUTE", kappa_compat=0.9)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=lambda state: FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=0.2),
        min_chain_kappa=0.5,
    )

    assert verdict.ok is False
    assert verdict.reason == "CHAIN_KAPPA_BELOW_THRESHOLD"


def test_missing_hop_kappa_marks_chain_incomparable_fails_closed():
    env = _make_envelope()
    predecessor = FakeCert(id="cert-A", verdict="EXECUTE", kappa_compat=0.6)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=lambda state: FakeCert(id="cert-B", verdict="EXECUTE", kappa_compat=None),
    )

    assert verdict.ok is False
    assert verdict.reason == "CHAIN_KAPPA_INCOMPARABLE"


def test_no_prohibited_tokens_in_source():
    from pathlib import Path

    from swarm_it.governance import receive_boundary

    source = Path(receive_boundary.__file__).read_text(encoding="utf-8")
    assert "sigma" not in source.lower()
    assert "kappa_gate" not in source.lower()
    assert "time.time(" not in source
    assert "datetime.now(" not in source
