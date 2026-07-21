"""Per-topology acceptance policy for governed multi-agent handoffs.

Each supported topology (PIPELINE, HUB_SPOKE, MESH) gets its own
acceptance function with its own semantics — support is not claimed from
a shared interface alone. RING and HIERARCHICAL are OUT of scope: they
fail closed with a typed REFUSE rather than being silently accepted.

Every hop is routed through the REAL receive/output boundaries
(`validate_on_receive` / `recertify_on_output`) — this module never
certifies a hop's successor state directly. That means a hop whose
`produced_payload` does not match its envelope's `payload_hash`, or
whose `successor_representation_id` is incompatible with the envelope,
is caught and REFUSEd at the boundary before this module's own
chain-kappa bookkeeping ever runs; a topology-layer accept can never be
satisfied by a tampered or wrong-representation handoff.

Gate authority stays with the injected `certifier` port (ADR-004/064):
this module contains no R/S/N math and no threshold decision beyond
reading ChainKappaTracker's aggregation of the per-hop CERTIFIER-DERIVED
kappa_compat — read from `validate_on_receive`'s `ReceiveVerdict.
derived_kappa_compat`, never the raw caller-supplied `HopInput.hop_kappa`
directly. That value only feeds the injected certifier(s); the topology
layer never trusts a caller's unreconciled claim about a hop's kappa. No
forbidden dispersion or enforcement-threshold lexemes, no wall-clock
reads.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from swarm_it.governance.chain_kappa import ChainKappaTracker
from swarm_it.governance.cycle_guard import CycleGuard
from swarm_it.governance.envelope import HandoffEnvelope
from swarm_it.governance.output_boundary import recertify_on_output
from swarm_it.governance.receive_boundary import validate_on_receive
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
    # Fixture/caller convenience only: feeds the injected (fake/real)
    # certifier so it can derive kappa_compat for this hop. The topology
    # tracker never reads this field directly — it aggregates the
    # CERTIFIED derived value returned on the receive verdict instead.
    hop_kappa: Optional[float]


def _emit_decision(
    event: str, decision: TopologyDecision, handoff_id: Optional[str], trace_parent: Optional[str]
) -> None:
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
            trace_parent=trace_parent,
        )
    )


def _refuse(
    pattern_name: str,
    reason: str,
    gating_hop: Optional[int],
    handoff_id: Optional[str],
    detail: Optional[dict] = None,
    trace_parent: Optional[str] = None,
) -> TopologyDecision:
    decision = TopologyDecision(verdict="REFUSE", reason=reason, gating_hop=gating_hop, detail=detail or {})
    _emit_decision(pattern_name, decision, handoff_id, trace_parent)
    return decision


def _execute(
    pattern_name: str, reason: str, handoff_id: Optional[str], detail: Optional[dict] = None, trace_parent: Optional[str] = None
) -> TopologyDecision:
    decision = TopologyDecision(verdict="EXECUTE", reason=reason, gating_hop=None, detail=detail or {})
    _emit_decision(pattern_name, decision, handoff_id, trace_parent)
    return decision


def _cross_hop_boundaries(
    pattern_name: str,
    hop: HopInput,
    index: int,
    *,
    cert_resolver: Callable[[str], Optional[Any]],
    certifier: Callable[[Any], Any],
    min_chain_kappa: float,
    now_epoch: Optional[float],
) -> tuple[Optional[TopologyDecision], Optional[float]]:
    """Route one hop through the real receive-then-output boundaries.

    Returns (REFUSE TopologyDecision, None) when either boundary fails the
    hop closed (tampered payload, incompatible representation, unresolved
    or stale predecessor cert, a refusing/erroring certifier verdict, a
    below-threshold/incomparable chain-kappa read at the receive boundary,
    or a passing receive verdict that somehow carries no certified kappa),
    or (None, derived_kappa_compat) once the hop has cleanly crossed both
    boundaries — derived_kappa_compat is the CERTIFIER-DERIVED value read
    off the receive verdict, the only kappa this hop's caller may feed
    into the topology's own ChainKappaTracker.

    Nothing here re-derives or overrides the boundaries' own verdicts —
    their `reason` is propagated as-is so a topology-layer REFUSE always
    traces back to the exact boundary check that fired.
    """
    receive_verdict = validate_on_receive(
        hop.envelope,
        hop.produced_payload,
        successor_representation_id=hop.successor_representation_id,
        cert_resolver=cert_resolver,
        certifier=certifier,
        successor_state=hop.successor_state,
        min_chain_kappa=min_chain_kappa,
        now_epoch=now_epoch,
    )
    if not receive_verdict.ok:
        return (
            _refuse(
                pattern_name,
                receive_verdict.reason,
                index,
                hop.envelope.handoff_id,
                {"boundary": "receive"},
                hop.envelope.trace_parent,
            ),
            None,
        )

    # Defensive: an ok=True enforcement-mode verdict should always carry a
    # certified kappa. If it somehow doesn't, this must fail closed rather
    # than let the topology tracker silently fall back to the caller's
    # unreconciled hop.hop_kappa.
    if receive_verdict.derived_kappa_compat is None:
        return (
            _refuse(
                pattern_name,
                "UNCERTIFIED_HOP_KAPPA",
                index,
                hop.envelope.handoff_id,
                {"boundary": "receive"},
                hop.envelope.trace_parent,
            ),
            None,
        )

    output_verdict = recertify_on_output(hop.successor_state, certifier=certifier, handoff_id=hop.envelope.handoff_id)
    if not output_verdict.released:
        return (
            _refuse(
                pattern_name,
                output_verdict.reason,
                index,
                hop.envelope.handoff_id,
                {"boundary": "output"},
                hop.envelope.trace_parent,
            ),
            None,
        )

    return None, receive_verdict.derived_kappa_compat


def accept_pipeline(
    hops: list[HopInput],
    *,
    certifier: Callable[[Any], Any],
    cert_resolver: Callable[[str], Optional[Any]],
    min_chain_kappa: float,
    now_epoch: Optional[float] = None,
) -> TopologyDecision:
    """PIPELINE (A -> B -> C, linear): each hop is routed through the real
    receive/output boundaries, then fed in order through ONE
    ChainKappaTracker; the weakest hop gates the whole chain.

    gating_hop is the index of the hop that FIRST drove the running
    chain-kappa min below min_chain_kappa, or the first hop refused by a
    boundary check (evaluation stops there — later hops never get a
    chance to "fix" an already-refused chain).
    """
    tracker = ChainKappaTracker()
    last_handoff_id: Optional[str] = None
    last_trace_parent: Optional[str] = None

    for index, hop in enumerate(hops):
        last_handoff_id = hop.envelope.handoff_id
        last_trace_parent = hop.envelope.trace_parent

        boundary_refusal, derived_kappa = _cross_hop_boundaries(
            "pipeline",
            hop,
            index,
            cert_resolver=cert_resolver,
            certifier=certifier,
            min_chain_kappa=min_chain_kappa,
            now_epoch=now_epoch,
        )
        if boundary_refusal is not None:
            return boundary_refusal

        state = tracker.observe(hop.envelope, derived_kappa)

        if state.incomparable:
            return _refuse(
                "pipeline",
                "CHAIN_KAPPA_INCOMPARABLE",
                index,
                hop.envelope.handoff_id,
                {"chain_kappa_min": state.chain_kappa_min},
                hop.envelope.trace_parent,
            )
        if state.chain_kappa_min is None or state.chain_kappa_min < min_chain_kappa:
            return _refuse(
                "pipeline",
                "CHAIN_KAPPA_BELOW_THRESHOLD",
                index,
                hop.envelope.handoff_id,
                {"chain_kappa_min": state.chain_kappa_min, "min_chain_kappa": min_chain_kappa},
                hop.envelope.trace_parent,
            )

    return _execute("pipeline", "CHAIN_HEALTHY", last_handoff_id, {"hops": len(hops)}, last_trace_parent)


def accept_hub_spoke(
    hops: list[HopInput],
    *,
    certifier: Callable[[Any], Any],
    cert_resolver: Callable[[str], Optional[Any]],
    min_chain_kappa: float,
    now_epoch: Optional[float] = None,
) -> TopologyDecision:
    """HUB_SPOKE (coordinator <-> spokes): each spoke handoff is routed
    through the real receive/output boundaries and evaluated
    INDEPENDENTLY, on its own ChainKappaTracker, so one spoke's weakness
    can never be masked or diluted by another spoke's strength.

    The hub aggregates: ANY failing spoke (boundary refusal,
    chain_kappa_min below threshold, or incomparable) makes the whole hub
    result REFUSE — a failing spoke must never be silently passed by the
    hub. gating_hop is the failing spoke's index.
    """
    last_handoff_id: Optional[str] = None
    last_trace_parent: Optional[str] = None

    for index, hop in enumerate(hops):
        last_handoff_id = hop.envelope.handoff_id
        last_trace_parent = hop.envelope.trace_parent

        boundary_refusal, derived_kappa = _cross_hop_boundaries(
            "hub_spoke",
            hop,
            index,
            cert_resolver=cert_resolver,
            certifier=certifier,
            min_chain_kappa=min_chain_kappa,
            now_epoch=now_epoch,
        )
        if boundary_refusal is not None:
            return boundary_refusal

        spoke_tracker = ChainKappaTracker()
        state = spoke_tracker.observe(hop.envelope, derived_kappa)

        if state.incomparable:
            return _refuse(
                "hub_spoke",
                "SPOKE_CHAIN_KAPPA_INCOMPARABLE",
                index,
                hop.envelope.handoff_id,
                {"chain_kappa_min": state.chain_kappa_min},
                hop.envelope.trace_parent,
            )
        if state.chain_kappa_min is None or state.chain_kappa_min < min_chain_kappa:
            return _refuse(
                "hub_spoke",
                "SPOKE_CHAIN_KAPPA_BELOW_THRESHOLD",
                index,
                hop.envelope.handoff_id,
                {"chain_kappa_min": state.chain_kappa_min, "min_chain_kappa": min_chain_kappa},
                hop.envelope.trace_parent,
            )

    return _execute("hub_spoke", "ALL_SPOKES_HEALTHY", last_handoff_id, {"spokes": len(hops)}, last_trace_parent)


def accept_mesh(
    hops: list[HopInput],
    *,
    certifier: Callable[[Any], Any],
    cert_resolver: Callable[[str], Optional[Any]],
    min_chain_kappa: float,
    now_epoch: Optional[float] = None,
) -> TopologyDecision:
    """MESH (peer <-> peer): every edge is a governed handoff, routed
    through the real receive/output boundaries.

    The whole traversal runs inside CycleGuard.enter("handoff") (canonical
    Claim 9 / repair-vs-handoff mutual exclusion): a mesh acceptance
    evaluation IS a handoff-mode traversal, never a repair cycle.

    No path may inherit authorization from an untraversed edge: an edge
    whose envelope.trace_parent does not correspond to an
    already-traversed edge (by handoff_id) in THIS mesh evaluation
    REFUSEs with reason="UNTRAVERSED_PARENT" — a root edge (trace_parent
    is None) is always allowed to start a traversal, and always starts a
    NEW lineage.

    Chain-kappa is tracked per LINEAGE, not globally: each connected
    component (traced back to its root edge) gets its OWN
    ChainKappaTracker, keyed by that root's handoff_id. This is what
    keeps an unrelated, weak/incomparable lineage from poisoning a
    healthy one — two independent root edges must never be forced onto
    one shared running chain-kappa aggregate.
    """
    traversed_handoff_ids: set[str] = set()
    lineage_root_of: dict[str, str] = {}
    lineage_trackers: dict[str, ChainKappaTracker] = {}
    last_handoff_id: Optional[str] = None
    last_trace_parent: Optional[str] = None

    with CycleGuard.enter("handoff"):
        for index, hop in enumerate(hops):
            envelope = hop.envelope
            last_handoff_id = envelope.handoff_id
            last_trace_parent = envelope.trace_parent

            if envelope.trace_parent is not None and envelope.trace_parent not in traversed_handoff_ids:
                return _refuse(
                    "mesh",
                    "UNTRAVERSED_PARENT",
                    index,
                    envelope.handoff_id,
                    {"trace_parent": envelope.trace_parent, "traversed": sorted(traversed_handoff_ids)},
                    envelope.trace_parent,
                )

            lineage_root = (
                envelope.handoff_id if envelope.trace_parent is None else lineage_root_of[envelope.trace_parent]
            )
            lineage_root_of[envelope.handoff_id] = lineage_root
            tracker = lineage_trackers.setdefault(lineage_root, ChainKappaTracker())

            boundary_refusal, derived_kappa = _cross_hop_boundaries(
                "mesh",
                hop,
                index,
                cert_resolver=cert_resolver,
                certifier=certifier,
                min_chain_kappa=min_chain_kappa,
                now_epoch=now_epoch,
            )
            if boundary_refusal is not None:
                return boundary_refusal

            state = tracker.observe(envelope, derived_kappa)

            if state.incomparable:
                return _refuse(
                    "mesh",
                    "CHAIN_KAPPA_INCOMPARABLE",
                    index,
                    envelope.handoff_id,
                    {"chain_kappa_min": state.chain_kappa_min, "lineage_root": lineage_root},
                    envelope.trace_parent,
                )
            if state.chain_kappa_min is None or state.chain_kappa_min < min_chain_kappa:
                return _refuse(
                    "mesh",
                    "CHAIN_KAPPA_BELOW_THRESHOLD",
                    index,
                    envelope.handoff_id,
                    {
                        "chain_kappa_min": state.chain_kappa_min,
                        "min_chain_kappa": min_chain_kappa,
                        "lineage_root": lineage_root,
                    },
                    envelope.trace_parent,
                )

            traversed_handoff_ids.add(envelope.handoff_id)

    return _execute("mesh", "MESH_HEALTHY", last_handoff_id, {"edges": len(hops)}, last_trace_parent)


def accept(
    pattern: SwarmPattern,
    hops: list[HopInput],
    *,
    certifier: Callable[[Any], Any],
    cert_resolver: Callable[[str], Optional[Any]],
    min_chain_kappa: float,
    now_epoch: Optional[float] = None,
) -> TopologyDecision:
    """Dispatch to the per-topology acceptance function for `pattern`.

    Only PIPELINE, HUB_SPOKE, and MESH are in scope. Any other pattern
    (RING, HIERARCHICAL, or anything else) fails closed with a REFUSE
    TopologyDecision (reason="UNSUPPORTED_TOPOLOGY") rather than being
    silently accepted by a shared/default path.
    """
    if pattern not in _SUPPORTED_PATTERNS:
        decision = TopologyDecision(
            verdict="REFUSE",
            reason="UNSUPPORTED_TOPOLOGY",
            gating_hop=None,
            detail={"pattern": getattr(pattern, "value", str(pattern))},
        )
        _emit_decision(getattr(pattern, "value", str(pattern)), decision, None, None)
        return decision

    if pattern is SwarmPattern.PIPELINE:
        return accept_pipeline(
            hops, certifier=certifier, cert_resolver=cert_resolver, min_chain_kappa=min_chain_kappa, now_epoch=now_epoch
        )
    if pattern is SwarmPattern.HUB_SPOKE:
        return accept_hub_spoke(
            hops, certifier=certifier, cert_resolver=cert_resolver, min_chain_kappa=min_chain_kappa, now_epoch=now_epoch
        )
    return accept_mesh(
        hops, certifier=certifier, cert_resolver=cert_resolver, min_chain_kappa=min_chain_kappa, now_epoch=now_epoch
    )
