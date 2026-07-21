"""Tests for HandoffEnvelope — the evidence contract carried across MAS handoffs.

An envelope must carry evidence (a certificate reference to be resolved
against the controlplane elsewhere) and must never carry a gate outcome
or threshold itself.
"""

import dataclasses

import pytest

from swarm_it.governance import HandoffEnvelope


def _make_envelope() -> HandoffEnvelope:
    return HandoffEnvelope(
        task_id="task-001",
        handoff_id="handoff-001",
        sender_id="agent-a",
        receiver_id="agent-b",
        input_certificate_ref="cert-abc123",
        artifact_hashes=("hash1", "hash2"),
        payload_hash="payloadhash",
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


def test_envelope_carries_evidence_not_authority():
    """The envelope must carry evidence, never a gate outcome or threshold."""
    env = _make_envelope()

    assert isinstance(env.input_certificate_ref, str)
    assert env.input_certificate_ref != ""

    forbidden_attrs = {"verdict", "decision", "kappa_threshold", "allowed", "gate"}
    assert forbidden_attrs.isdisjoint(vars(env).keys())

    with pytest.raises(dataclasses.FrozenInstanceError):
        env.receiver_id = "x"


def test_a2a_round_trip():
    """to_a2a_extension / from_a2a_extension must round-trip exactly."""
    env = _make_envelope()

    data = env.to_a2a_extension()
    restored = HandoffEnvelope.from_a2a_extension(data)

    assert restored == env
    assert isinstance(restored.artifact_hashes, tuple)


def test_no_sigma_lexeme_in_source():
    """The chain-dispersion field must use prior_chain_dispersion, never sigma."""
    from pathlib import Path
    from swarm_it import governance

    source_path = Path(governance.__file__).parent / "envelope.py"
    source = source_path.read_text(encoding="utf-8")

    assert "sigma" not in source.lower()
