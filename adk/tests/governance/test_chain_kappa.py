"""Tests for ChainKappaTracker — weakest-link proxy tracking across hops.

Chain-kappa here aggregates the R*(1-N) proxy (the same enforced kappa
each Agent exposes via kappa_compat), NOT a true kappa. These tests only
check the aggregation contract (weakest-link min, no silent upgrade,
dispersion, fail-safe on missing/incomparable values) — they make no
claim about proxy fidelity (that is ADR-078, open).
"""

import hashlib

import pytest

from swarm_it.governance import HandoffEnvelope
from swarm_it.governance import ChainKappaState, ChainKappaTracker
from swarm_it.governance import get_trace, reset_trace


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()


def _make_envelope(**overrides) -> HandoffEnvelope:
    fields = dict(
        task_id="task-001",
        handoff_id="handoff-001",
        sender_id="agent-a",
        receiver_id="agent-b",
        input_certificate_ref="cert-abc123",
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


def test_weakest_link_min_monotone_and_no_silent_upgrade():
    """Running min must equal the minimum observed so far, and a later,
    higher-kappa hop must never raise it back up."""
    tracker = ChainKappaTracker()

    s1 = tracker.observe(_make_envelope(handoff_id="h1"), 0.8)
    s2 = tracker.observe(_make_envelope(handoff_id="h2"), 0.5)
    s3 = tracker.observe(_make_envelope(handoff_id="h3"), 0.9)

    assert s1.chain_kappa_min == pytest.approx(0.8)
    assert s2.chain_kappa_min == pytest.approx(0.5)
    assert s3.chain_kappa_min == pytest.approx(0.5)

    assert s3.hops == 3

    # dispersion must exist, and "sigma" must never be an attribute name.
    assert hasattr(s3, "chain_kappa_dispersion")
    assert not hasattr(s3, "sigma")
    assert not any("sigma" in name for name in vars(s3).keys())


def test_single_hop_dispersion_zero():
    tracker = ChainKappaTracker()

    state = tracker.observe(_make_envelope(handoff_id="h1"), 0.7)

    assert state.hops == 1
    assert state.chain_kappa_dispersion == pytest.approx(0.0)


def test_missing_value_marks_incomparable():
    tracker = ChainKappaTracker()

    s1 = tracker.observe(_make_envelope(handoff_id="h1"), 0.8)
    assert s1.incomparable is False

    s2 = tracker.observe(_make_envelope(handoff_id="h2"), None)

    assert s2.incomparable is True
    # No imputed value: the running min must be unaffected by the missing hop.
    assert s2.chain_kappa_min == pytest.approx(0.8)

    # Once incomparable, it stays True for the chain even on a later good hop.
    s3 = tracker.observe(_make_envelope(handoff_id="h3"), 0.6)
    assert s3.incomparable is True


def test_missing_value_with_no_prior_comparable_hop_stays_none():
    tracker = ChainKappaTracker()

    state = tracker.observe(_make_envelope(handoff_id="h1"), None)

    assert state.incomparable is True
    assert state.chain_kappa_min is None


def test_representation_mismatch_marks_incomparable():
    tracker = ChainKappaTracker()

    s1 = tracker.observe(_make_envelope(handoff_id="h1", representation_id="rep-1"), 0.8)
    assert s1.incomparable is False

    s2 = tracker.observe(_make_envelope(handoff_id="h2", representation_id="rep-2"), 0.9)

    assert s2.incomparable is True
    # A mismatched-representation value is not comparable, so it must not
    # silently raise (or otherwise move) the running min.
    assert s2.chain_kappa_min == pytest.approx(0.8)


def test_is_proxy_always_true():
    tracker = ChainKappaTracker()

    state = tracker.observe(_make_envelope(handoff_id="h1"), 0.5)

    assert state.is_proxy is True


def test_observe_emits_trace_record():
    tracker = ChainKappaTracker()

    tracker.observe(_make_envelope(handoff_id="h1"), 0.8)
    tracker.observe(_make_envelope(handoff_id="h2"), 0.5)

    trace = get_trace()

    assert len(trace) == 2
    assert trace[0].event == "chain_kappa_observe"
    assert trace[0].handoff_id == "h1"
    assert trace[1].handoff_id == "h2"


def test_no_sigma_lexeme_in_source():
    from pathlib import Path
    from swarm_it import governance

    source_path = Path(governance.__file__).parent / "chain_kappa.py"
    source = source_path.read_text(encoding="utf-8")

    assert "sigma" not in source.lower()


def test_no_kappa_gate_identifier_in_source():
    from pathlib import Path
    from swarm_it import governance

    source_path = Path(governance.__file__).parent / "chain_kappa.py"
    source = source_path.read_text(encoding="utf-8")

    assert "kappa_gate" not in source.lower()


def test_chain_kappa_state_is_frozen():
    import dataclasses

    state = ChainKappaState(
        chain_kappa_min=0.5,
        chain_kappa_dispersion=0.1,
        hops=1,
        incomparable=False,
        is_proxy=True,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        state.hops = 2
