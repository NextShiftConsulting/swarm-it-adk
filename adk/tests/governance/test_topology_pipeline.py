"""Tests for PIPELINE topology acceptance policy (V-013 T6).

Pipeline hops are routed through the real receive/output boundaries and
threaded through a single ChainKappaTracker, in order: the weakest hop
gates the whole chain, and gating_hop identifies the FIRST hop whose
observation drove the running min below the threshold (or the first hop
a boundary check refused).
"""

import dataclasses
import hashlib
from typing import Optional

import pytest

from swarm_it.governance import HandoffEnvelope, get_trace, reset_trace
from swarm_it.governance.topology_policy import HopInput, TopologyDecision, accept_pipeline
from swarm_it.topology.patterns import SwarmPattern


GOOD_PAYLOAD = b"GOOD"
GOOD_HASH = "sha256:" + hashlib.sha256(GOOD_PAYLOAD).hexdigest()
TAMPERED_PAYLOAD = b"TAMPERED"


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


def _cert_resolver(_ref):
    # A clean, non-stale predecessor -- enough to satisfy the receive
    # boundary's resolution step in every test in this file.
    return FakeCert(id="cert-predecessor", verdict="EXECUTE", kappa_compat=0.9)


def _certifier_from_kappas(kappas, verdict="EXECUTE"):
    """Certifier whose derived kappa_compat matches the hop's intended
    hop_kappa (state["i"] indexes into `kappas`) -- this keeps the receive
    boundary's OWN chain-kappa read consistent with what each test hop is
    actually exercising."""

    def certifier(state):
        i = state["i"]
        return FakeCert(id=f"cert-derived-{i}", verdict=verdict, kappa_compat=kappas[i])

    return certifier


def _fake_certifier_always_execute(_state):
    return FakeCert(id="cert-derived", verdict="EXECUTE", kappa_compat=0.9)


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

    decision = accept_pipeline(
        hops, certifier=_certifier_from_kappas([0.8, 0.4, 0.9]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert isinstance(decision, TopologyDecision)
    assert decision.verdict == "REFUSE"
    assert decision.gating_hop == 1


def test_pipeline_all_healthy_executes():
    hops = _make_hops([0.8, 0.7, 0.9])

    decision = accept_pipeline(
        hops, certifier=_certifier_from_kappas([0.8, 0.7, 0.9]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "EXECUTE"
    assert decision.gating_hop is None


def test_pipeline_emits_trace_record():
    hops = _make_hops([0.8, 0.7])

    accept_pipeline(
        hops, certifier=_certifier_from_kappas([0.8, 0.7]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    trace = get_trace()
    assert len(trace) >= 1
    assert trace[-1].event == "topology_decision"


def test_pipeline_tampered_payload_refuses():
    """A hop whose produced_payload does not match its envelope's
    payload_hash must be caught (and REFUSEd) at the receive boundary --
    the topology layer can never certify a tampered handoff."""
    good_hop = _make_hops([0.8])[0]
    tampered_hop = HopInput(
        envelope=_make_envelope(handoff_id="h-tampered"),
        produced_payload=TAMPERED_PAYLOAD,
        successor_representation_id="rep-1",
        successor_state={"i": 0},
        hop_kappa=0.8,
    )
    hops = [good_hop, tampered_hop]

    decision = accept_pipeline(
        hops, certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "REFUSE"
    assert decision.reason == "PAYLOAD_HASH_MISMATCH"
    assert decision.gating_hop == 1


def test_topology_aggregates_certified_kappa_not_caller_value():
    """The topology-level ChainKappaTracker must aggregate the
    CERTIFIER-DERIVED kappa_compat read off each hop's receive verdict --
    never the untrusted, caller-supplied HopInput.hop_kappa.

    hop 1's caller claims an unhealthy hop_kappa (0.1) while the injected
    certifier actually derives a healthy kappa_compat (0.6, still >=
    min_chain_kappa=0.5) for that same hop. Every hop's certified value
    individually clears the receive boundary's own per-hop chain-kappa
    check (0.9, 0.6, 0.9 are all >= 0.5), so the receive boundary never
    refuses -- the only place left that could still get this wrong is the
    topology's own running weakest-link tracker.

    Against the pre-fix code (tracker.observe(hop.envelope, hop.hop_kappa)),
    this REFUSEs on hop 1 with chain_kappa_min=0.1 in the detail -- a
    number no certifier ever produced, exactly the "chain_kappa_min that
    nobody certified" integrity gap under review. Fixed, the tracker reads
    the certified 0.6 and the chain EXECUTEs. (The reverse framing --
    caller inflates hop_kappa to mask a low certified value -- does NOT
    distinguish pre- from post-fix here: the receive boundary already
    reconciles and refuses on the true derived value for that hop before
    the topology tracker ever runs, independent of this bug. This
    deflated-caller framing is the one that actually depends on the fix,
    confirmed by running it against the pre-fix tracker.)
    """
    caller_claims = [0.9, 0.1, 0.9]  # hop 1: caller falsely claims unhealthy
    certified = [0.9, 0.6, 0.9]  # hop 1: certifier actually derives healthy

    hops = []
    for i, claim in enumerate(caller_claims):
        hops.append(
            HopInput(
                envelope=_make_envelope(handoff_id=f"h{i}"),
                produced_payload=GOOD_PAYLOAD,
                successor_representation_id="rep-1",
                successor_state={"i": i},
                hop_kappa=claim,
            )
        )

    decision = accept_pipeline(
        hops,
        certifier=_certifier_from_kappas(certified),
        cert_resolver=_cert_resolver,
        min_chain_kappa=0.5,
    )

    assert decision.verdict == "EXECUTE"
    assert decision.gating_hop is None


def test_pipeline_empty_hops_refuses():
    """An empty hop list must REFUSE, not fall through the (never-entered)
    loop into an EXECUTE -- that would be a vacuous authorization where no
    certifier was ever called and no hop was ever validated."""
    decision = accept_pipeline(
        [], certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "REFUSE"
    assert decision.reason == "EMPTY_CHAIN"
    assert decision.gating_hop is None


def test_pipeline_carried_weak_prior_refuses_locally_healthy_hop():
    """V-013 I2: a SINGLE hop whose certifier-derived kappa is locally
    healthy (0.9, >= threshold 0.5) but whose envelope ARRIVES carrying a
    weak prior_chain_kappa_min (0.3, from an earlier chain segment/handoff)
    must REFUSE -- the carried prior caps the chain at 0.3 regardless of
    how healthy this hop's own certified kappa is.

    NOTE: this specific case is already correctly handled even WITHOUT any
    topology-layer wiring, because `_cross_hop_boundaries` forwards
    `hop.envelope` unmodified straight into `validate_on_receive`, whose
    `ChainKappaTracker.from_envelope` already seeds off
    envelope.prior_chain_kappa_min. This test therefore PASSES both
    pre- and post-fix -- it is a regression/behavior-preservation test for
    the boundary's pre-existing carried-prior protection surviving the
    topology layer unmolested, not a fix-discriminating test. (Given
    weakest-link MIN aggregation plus this module's return-immediately-on-
    first-refusal control flow, NO multi-hop, same-batch construction can
    make a later hop's carried state change a REFUSE/EXECUTE outcome: any
    hop weak enough to matter is always caught at its own position
    regardless of what any prior seeds it with, and the loop exits the
    instant a hop refuses -- so a "poisoned by an earlier hop in this same
    batch" scenario can never be observed. The load-bearing, fix-
    discriminating proof of I2 is chain_kappa_min REPORTING, covered by
    the two tests below.)
    """
    hop = HopInput(
        envelope=_make_envelope(handoff_id="h0", prior_chain_kappa_min=0.3),
        produced_payload=GOOD_PAYLOAD,
        successor_representation_id="rep-1",
        successor_state={"i": 0},
        hop_kappa=0.9,
    )

    decision = accept_pipeline(
        [hop], certifier=_certifier_from_kappas([0.9]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "REFUSE"
    assert decision.gating_hop == 0


def test_pipeline_reports_true_cross_hop_min():
    hops = _make_hops([0.8, 0.4, 0.9])

    decision = accept_pipeline(
        hops, certifier=_certifier_from_kappas([0.8, 0.4, 0.9]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "REFUSE"
    assert decision.gating_hop == 1
    assert decision.detail["chain_kappa_min"] == 0.4


def test_pipeline_healthy_chain_reports_running_min():
    hops = _make_hops([0.8, 0.7, 0.9])

    decision = accept_pipeline(
        hops, certifier=_certifier_from_kappas([0.8, 0.7, 0.9]), cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "EXECUTE"
    assert decision.detail["chain_kappa_min"] == 0.7


def test_pipeline_wrong_representation_refuses():
    """A hop whose successor_representation_id disagrees with its
    envelope's representation_id must REFUSE at the receive boundary --
    no handoff can inherit authorization for a mismatched representation."""
    good_hop = _make_hops([0.8])[0]
    wrong_rep_hop = HopInput(
        envelope=_make_envelope(handoff_id="h-wrong-rep", representation_id="rep-1"),
        produced_payload=GOOD_PAYLOAD,
        successor_representation_id="rep-2",
        successor_state={"i": 0},
        hop_kappa=0.8,
    )
    hops = [good_hop, wrong_rep_hop]

    decision = accept_pipeline(
        hops, certifier=_fake_certifier_always_execute, cert_resolver=_cert_resolver, min_chain_kappa=0.5
    )

    assert decision.verdict == "REFUSE"
    assert decision.reason == "INCOMPATIBLE_REPRESENTATION"
    assert decision.gating_hop == 1
