"""Per-topology acceptance policy for governed multi-agent handoffs.

Each supported topology (PIPELINE, HUB_SPOKE, MESH) gets its own
acceptance function with its own semantics — support is not claimed from
a shared interface alone. RING and HIERARCHICAL are OUT of scope: they
fail closed with a typed REFUSE rather than being silently accepted.

Gate authority stays with the injected `certifier` port (ADR-004/064):
this module contains no R/S/N math and no threshold decision beyond
reading ChainKappaTracker's aggregation of the per-hop enforced kappa
proxy (`hop_kappa`) each caller supplies. No forbidden dispersion or
enforcement-threshold lexemes, no wall-clock reads.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from swarm_it.governance.chain_kappa import ChainKappaTracker
from swarm_it.governance.envelope import HandoffEnvelope
from swarm_it.governance.trace import TraceRecord, emit
from swarm_it.topology.patterns import SwarmPattern

_SUPPORTED_PATTERNS = (SwarmPattern.PIPELINE, SwarmPattern.HUB_SPOKE, SwarmPattern.MESH)


class UnsupportedTopologyError(Exception):
    """Raised (by callers who choose to) for a topology outside T6 scope.

    `accept()` itself does not raise this — it fails closed with a
    REFUSE TopologyDecision instead, for consistency with every other
    fail-closed verdict in this module. The type is defined so a caller
    that wants exception-style handling for an out-of-scope pattern has
    a typed exception to raise/catch rather than inventing one ad hoc.
    """


@dataclass(frozen=True)
class TopologyDecision:
    """Outcome of a per-topology acceptance evaluation."""

    verdict: str
    reason: str
    gating_hop: Optional[int] = None
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class HopInput:
    """One governed hop/edge fed into a topology acceptance evaluation."""

    envelope: HandoffEnvelope
    produced_payload: bytes
    successor_representation_id: str
    successor_state: Any
    hop_kappa: Optional[float]


def _derived_verdict_ok(derived: Any) -> bool:
    # Duck-typed, matching receive_boundary/output_boundary: real
    # controlplane certs expose .allowed; simple test doubles may only
    # expose .verdict == "EXECUTE". Neither present fails closed.
    if hasattr(derived, "allowed"):
        return bool(derived.allowed)
    if hasattr(derived, "verdict"):
        return derived.verdict == "EXECUTE"
    return False


def _emit_decision(event: str, decision: TopologyDecision, handoff_id: Optional[str]) -> None:
    emit(
        TraceRecord(
            event="topology_decision",
            reason=decision.reason,
            handoff_id=handoff_id,
            detail={
                "verdict": decision.verdict,
                "gating_hop": decision.gating_hop,
                "pattern": event,
                **decision.detail,
            },
        )
    )


def _refuse(
    pattern_name: str, reason: str, gating_hop: Optional[int], handoff_id: Optional[str], detail: Optional[dict] = None
) -> TopologyDecision:
    decision = TopologyDecision(verdict="REFUSE", reason=reason, gating_hop=gating_hop, detail=detail or {})
    _emit_decision(pattern_name, decision, handoff_id)
    return decision


def _execute(pattern_name: str, reason: str, handoff_id: Optional[str], detail: Optional[dict] = None) -> TopologyDecision:
    decision = TopologyDecision(verdict="EXECUTE", reason=reason, gating_hop=None, detail=detail or {})
    _emit_decision(pattern_name, decision, handoff_id)
    return decision


def _certify_hop(
    pattern_name: str, hop: HopInput, index: int, certifier: Callable[[Any], Any]
) -> Optional[TopologyDecision]:
    """Call the injected certifier for one hop; return a REFUSE decision on
    a refusing/erroring verdict, or None when the hop is certified clean."""
    try:
        derived = certifier(hop.successor_state)
    except Exception as exc:
        return _refuse(
            pattern_name, "CERTIFIER_ERROR", index, hop.envelope.handoff_id, {"error": str(exc)}
        )
    if not _derived_verdict_ok(derived):
        return _refuse(
            pattern_name,
            "CERTIFIER_REFUSED",
            index,
            hop.envelope.handoff_id,
            {"derived_certificate_id": getattr(derived, "id", None)},
        )
    return None


def accept_pipeline(hops: list[HopInput], *, certifier: Callable[[Any], Any], min_chain_kappa: float) -> TopologyDecision:
    """PIPELINE (A -> B -> C, linear): feed hops in order through ONE
    ChainKappaTracker; the weakest hop gates the whole chain.

    gating_hop is the index of the hop that FIRST drove the running
    chain-kappa min below min_chain_kappa (evaluation stops there —
    later hops never get a chance to "fix" an already-refused chain).
    """
    tracker = ChainKappaTracker()
    last_handoff_id: Optional[str] = None

    for index, hop in enumerate(hops):
        last_handoff_id = hop.envelope.handoff_id

        cert_refusal = _certify_hop("pipeline", hop, index, certifier)
        if cert_refusal is not None:
            return cert_refusal

        state = tracker.observe(hop.envelope, hop.hop_kappa)

        if state.incomparable:
            return _refuse(
                "pipeline", "CHAIN_KAPPA_INCOMPARABLE", index, hop.envelope.handoff_id, {"chain_kappa_min": state.chain_kappa_min}
            )
        if state.chain_kappa_min is None or state.chain_kappa_min < min_chain_kappa:
            return _refuse(
                "pipeline",
                "CHAIN_KAPPA_BELOW_THRESHOLD",
                index,
                hop.envelope.handoff_id,
                {"chain_kappa_min": state.chain_kappa_min, "min_chain_kappa": min_chain_kappa},
            )

    return _execute("pipeline", "CHAIN_HEALTHY", last_handoff_id, {"hops": len(hops)})


def accept_hub_spoke(hops: list[HopInput], *, certifier: Callable[[Any], Any], min_chain_kappa: float) -> TopologyDecision:
    """HUB_SPOKE (coordinator <-> spokes): each spoke handoff is evaluated
    INDEPENDENTLY, on its own ChainKappaTracker, so one spoke's weakness
    can never be masked or diluted by another spoke's strength.

    The hub aggregates: ANY failing spoke (chain_kappa_min below
    threshold, incomparable, or certifier refusal) makes the whole hub
    result REFUSE — a failing spoke must never be silently passed by the
    hub. gating_hop is the failing spoke's index.
    """
    last_handoff_id: Optional[str] = None

    for index, hop in enumerate(hops):
        last_handoff_id = hop.envelope.handoff_id

        cert_refusal = _certify_hop("hub_spoke", hop, index, certifier)
        if cert_refusal is not None:
            return cert_refusal

        spoke_tracker = ChainKappaTracker()
        state = spoke_tracker.observe(hop.envelope, hop.hop_kappa)

        if state.incomparable:
            return _refuse(
                "hub_spoke",
                "SPOKE_CHAIN_KAPPA_INCOMPARABLE",
                index,
                hop.envelope.handoff_id,
                {"chain_kappa_min": state.chain_kappa_min},
            )
        if state.chain_kappa_min is None or state.chain_kappa_min < min_chain_kappa:
            return _refuse(
                "hub_spoke",
                "SPOKE_CHAIN_KAPPA_BELOW_THRESHOLD",
                index,
                hop.envelope.handoff_id,
                {"chain_kappa_min": state.chain_kappa_min, "min_chain_kappa": min_chain_kappa},
            )

    return _execute("hub_spoke", "ALL_SPOKES_HEALTHY", last_handoff_id, {"spokes": len(hops)})


def accept_mesh(hops: list[HopInput], *, certifier: Callable[[Any], Any], min_chain_kappa: float) -> TopologyDecision:
    """MESH (peer <-> peer): every edge is a governed handoff.

    No path may inherit authorization from an untraversed edge: an edge
    whose envelope.trace_parent does not correspond to an
    already-traversed edge (by handoff_id) in THIS mesh evaluation
    REFUSEs with reason="UNTRAVERSED_PARENT" — a root edge (trace_parent
    is None) is always allowed to start a traversal. Edges are otherwise
    threaded through one ChainKappaTracker so the mesh's aggregate
    chain-kappa is also enforced.
    """
    traversed_handoff_ids: set[str] = set()
    tracker = ChainKappaTracker()
    last_handoff_id: Optional[str] = None

    for index, hop in enumerate(hops):
        envelope = hop.envelope
        last_handoff_id = envelope.handoff_id

        if envelope.trace_parent is not None and envelope.trace_parent not in traversed_handoff_ids:
            return _refuse(
                "mesh",
                "UNTRAVERSED_PARENT",
                index,
                envelope.handoff_id,
                {"trace_parent": envelope.trace_parent, "traversed": sorted(traversed_handoff_ids)},
            )

        cert_refusal = _certify_hop("mesh", hop, index, certifier)
        if cert_refusal is not None:
            return cert_refusal

        state = tracker.observe(envelope, hop.hop_kappa)

        if state.incomparable:
            return _refuse(
                "mesh", "CHAIN_KAPPA_INCOMPARABLE", index, envelope.handoff_id, {"chain_kappa_min": state.chain_kappa_min}
            )
        if state.chain_kappa_min is None or state.chain_kappa_min < min_chain_kappa:
            return _refuse(
                "mesh",
                "CHAIN_KAPPA_BELOW_THRESHOLD",
                index,
                envelope.handoff_id,
                {"chain_kappa_min": state.chain_kappa_min, "min_chain_kappa": min_chain_kappa},
            )

        traversed_handoff_ids.add(envelope.handoff_id)

    return _execute("mesh", "MESH_HEALTHY", last_handoff_id, {"edges": len(hops)})


def accept(
    pattern: SwarmPattern,
    hops: list[HopInput],
    *,
    certifier: Callable[[Any], Any],
    min_chain_kappa: float,
    threshold: Optional[float] = None,
) -> TopologyDecision:
    """Dispatch to the per-topology acceptance function for `pattern`.

    Only PIPELINE, HUB_SPOKE, and MESH are in scope. Any other pattern
    (RING, HIERARCHICAL, or anything else) fails closed with a REFUSE
    TopologyDecision (reason="UNSUPPORTED_TOPOLOGY") rather than being
    silently accepted by a shared/default path.

    `threshold` is accepted for forward-compatible callers but is not
    itself gate math here — chain-kappa gating uses min_chain_kappa; a
    caller that also wants a per-hop threshold check must express it via
    the injected certifier.
    """
    if pattern not in _SUPPORTED_PATTERNS:
        decision = TopologyDecision(
            verdict="REFUSE",
            reason="UNSUPPORTED_TOPOLOGY",
            gating_hop=None,
            detail={"pattern": getattr(pattern, "value", str(pattern))},
        )
        _emit_decision(getattr(pattern, "value", str(pattern)), decision, None)
        return decision

    if pattern is SwarmPattern.PIPELINE:
        return accept_pipeline(hops, certifier=certifier, min_chain_kappa=min_chain_kappa)
    if pattern is SwarmPattern.HUB_SPOKE:
        return accept_hub_spoke(hops, certifier=certifier, min_chain_kappa=min_chain_kappa)
    return accept_mesh(hops, certifier=certifier, min_chain_kappa=min_chain_kappa)
