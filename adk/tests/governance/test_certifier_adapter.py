"""Tests for the certifier adapter (V-013 I1).

The governance boundaries duck-type a derived certificate's
`.kappa_compat` / `.allowed` / `.id` / `.expires_at`, but the two REAL
certificate types produced by this repo do not present that shape
uniformly:

- RSCTCertificate (swarm_it.local.engine) exposes `.kappa_compat` directly.
- SwarmCertificate (swarm_it.topology.certifier) exposes the same
  enforced-proxy value under `.kappa_compat_chain_min` instead, so a raw
  SwarmCertificate fed straight into the boundaries reads
  kappa_compat=None -> every hop is marked incomparable -> everything
  REFUSEs, even when the swarm certificate is a clean EXECUTE.

certifier_adapter.normalize_certificate() closes that gap by mapping
either real type onto one NormalizedCertificate shape. These tests
construct the REAL dataclasses (not test doubles) to bind the adapter to
the actual attribute names, so a regression in either class's field names
is caught here.
"""

import hashlib

import pytest

from swarm_it._compat import GateDecision
from swarm_it.governance import HandoffEnvelope, get_trace, reset_trace, validate_on_receive
from swarm_it.governance.certifier_adapter import (
    NormalizedCertificate,
    make_certifier,
    normalize_certificate,
)
from swarm_it.local.engine import RSCTCertificate
from swarm_it.topology.certifier import SwarmCertificate

GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


def _make_rsct_certificate(**overrides) -> RSCTCertificate:
    fields = dict(
        id="cert-rsct-1",
        timestamp="2026-07-20T00:00:00Z",
        R=0.7,
        S_sup=0.2,
        N=0.1,
        kappa_compat=0.65,
        sigma=0.3,
        decision=GateDecision.EXECUTE,
        gate_reached=5,
        reason="EXECUTE at ALL_PASSED",
    )
    fields.update(overrides)
    return RSCTCertificate(**fields)


def _make_swarm_certificate(**overrides) -> SwarmCertificate:
    fields = dict(
        id="cert-swarm-1",
        timestamp="2026-07-20T00:00:00Z",
        swarm_id="swarm-1",
        R=0.6,
        S_sup=0.2,
        N=0.2,
        consensus=0.9,
        kappa_compat_chain_min=0.42,
        kappa_interface_min=0.5,
        sigma_max=0.3,
        decision=GateDecision.EXECUTE,
        gate_reached=5,
        reason="Swarm: EXECUTE at ALL_PASSED",
    )
    fields.update(overrides)
    return SwarmCertificate(**fields)


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


def test_normalize_rsct_certificate():
    """RSCTCertificate already exposes kappa_compat directly — the
    adapter must pass it through unchanged, along with id and allowed."""
    cert = _make_rsct_certificate(kappa_compat=0.65, decision=GateDecision.EXECUTE)

    normalized = normalize_certificate(cert)

    assert isinstance(normalized, NormalizedCertificate)
    assert normalized.id == "cert-rsct-1"
    assert normalized.kappa_compat == 0.65
    assert normalized.allowed is True
    assert normalized.expires_at is None


def test_normalize_swarm_certificate_maps_chain_min():
    """SwarmCertificate has NO .kappa_compat attribute — the enforced
    proxy lives under .kappa_compat_chain_min. This is the exact I1 bug:
    without the fallback mapping, normalize would read kappa_compat=None."""
    cert = _make_swarm_certificate(kappa_compat_chain_min=0.42, decision=GateDecision.EXECUTE)

    assert not hasattr(cert, "kappa_compat")  # confirms the real mismatch

    normalized = normalize_certificate(cert)

    assert normalized.id == "cert-swarm-1"
    assert normalized.kappa_compat == 0.42
    assert normalized.allowed is True


def test_normalize_swarm_certificate_refused():
    cert = _make_swarm_certificate(
        kappa_compat_chain_min=0.1, decision=GateDecision.BLOCK, reason="Swarm: BLOCK"
    )

    normalized = normalize_certificate(cert)

    assert normalized.allowed is False


def test_make_certifier_returns_normalized():
    def certify_fn(state):
        return _make_rsct_certificate(id="cert-x", kappa_compat=0.55)

    wrapped = make_certifier(certify_fn)
    result = wrapped({"some": "state"})

    assert isinstance(result, NormalizedCertificate)
    assert result.id == "cert-x"
    assert result.kappa_compat == 0.55
    assert result.allowed is True


def test_normalized_cert_drives_receive_boundary():
    """End-to-end: a real SwarmCertificate, wrapped through make_certifier,
    must flow through validate_on_receive as a comparable kappa hop instead
    of being marked incomparable (the pre-adapter I1 failure mode)."""
    env = _make_envelope()
    predecessor = normalize_certificate(_make_rsct_certificate(kappa_compat=0.6))

    def certify_high(state):
        return _make_swarm_certificate(kappa_compat_chain_min=0.8, decision=GateDecision.EXECUTE)

    certifier = make_certifier(certify_high)

    verdict = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=certifier,
        successor_state={"intermediate": "state"},
        min_chain_kappa=0.5,
    )

    assert verdict.ok is True
    assert verdict.reason == "RECERTIFIED"
    assert verdict.derived_kappa_compat == 0.8

    def certify_low(state):
        return _make_swarm_certificate(kappa_compat_chain_min=0.1, decision=GateDecision.EXECUTE)

    verdict_low = validate_on_receive(
        env,
        GOOD_PAYLOAD,
        successor_representation_id=env.representation_id,
        cert_resolver=lambda ref: predecessor,
        certifier=make_certifier(certify_low),
        successor_state={"intermediate": "state"},
        min_chain_kappa=0.5,
    )

    assert verdict_low.ok is False
    assert verdict_low.reason == "CHAIN_KAPPA_BELOW_THRESHOLD"


def test_no_prohibited_tokens_in_source():
    from pathlib import Path

    from swarm_it.governance import certifier_adapter

    source = Path(certifier_adapter.__file__).read_text(encoding="utf-8")
    assert "sigma" not in source.lower()
    assert "kappa_gate" not in source.lower()
    assert "time.time(" not in source
    assert "datetime.now(" not in source
