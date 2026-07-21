"""ChainKappaTracker — weakest-link tracking of the enforced kappa proxy.

Chain-kappa here aggregates the R*(1-N) ENFORCED kappa proxy that each hop
contributes (the same value Agent.kappa_compat exposes) — it is NOT true
kappa. Whether this proxy is a faithful stand-in for true kappa across a
chain of handoffs is an open question tracked under ADR-078; nothing in
this module asserts decision-correctness or "chain kappa safe" — it only
tracks the proxy so the aggregation is auditable.

Aggregation is weakest-link minimum (ADR-approved), never average or
product: a single weak hop caps the whole chain, and a later, stronger
hop must never silently raise that cap back up.
"""

import statistics
from dataclasses import dataclass
from typing import Optional

from swarm_it.governance.envelope import HandoffEnvelope
from swarm_it.governance.trace import TraceRecord, emit


@dataclass(frozen=True)
class ChainKappaState:
    """Running weakest-link view of the enforced kappa proxy for one chain."""

    chain_kappa_min: Optional[float]
    chain_kappa_dispersion: float
    hops: int
    comparable_hops: int
    incomparable: bool
    is_proxy: bool


class ChainKappaTracker:
    """Tracks weakest-link chain-kappa proxy state across hops of one chain.

    One instance tracks exactly one chain: call observe() once per hop, in
    order, on the same instance. State is fail-safe on missing or
    incomparable values — a hop is never imputed, it is excluded from the
    running min/dispersion and flags the chain as incomparable instead.

    `hops` counts every observe() call (including incomparable ones);
    `comparable_hops` counts only the ones that actually backed the
    running min/dispersion. Use comparable_hops when you need to know how
    much evidence the min/dispersion actually rest on.
    """

    def __init__(self) -> None:
        self._hop_kappas: list[float] = []
        self._chain_kappa_min: Optional[float] = None
        self._hops: int = 0
        self._comparable_hops: int = 0
        self._incomparable: bool = False
        self._first_representation_id: Optional[str] = None

    @classmethod
    def from_envelope(cls, envelope: HandoffEnvelope) -> "ChainKappaTracker":
        """Seed a new tracker from a HandoffEnvelope's prior-chain evidence.

        A receiving hop must be able to continue the running chain
        aggregate from the envelope's carried fields alone, without
        sharing the sender's in-memory tracker.

        - Running min (enforcement-critical): seeded from
          envelope.prior_chain_kappa_min so weakest-link min-monotonicity
          holds ACROSS the boundary — a later, higher local observe() can
          never raise it back up. If prior_chain_kappa_min is None, the
          seeded min stays None until a comparable local hop arrives.
        - hops: seeded from envelope.prior_hops; each subsequent local
          observe() increments it.
        - Dispersion (diagnostic, not enforcement) is NOT seeded: the
          envelope carries only the prior dispersion *summary*, not the
          prior raw hop values, so a pooled cross-boundary stdev cannot be
          honestly reconstructed. Post-seed chain_kappa_dispersion
          reflects only the hops this tracker directly observes locally
          after seeding. envelope.prior_chain_dispersion is carried
          forward as evidence only, recorded in the seed TraceRecord.
        """
        tracker = cls()
        tracker._chain_kappa_min = envelope.prior_chain_kappa_min
        tracker._hops = envelope.prior_hops

        emit(
            TraceRecord(
                event="chain_kappa_seed",
                reason="SEEDED_FROM_ENVELOPE",
                handoff_id=envelope.handoff_id,
                detail={
                    "prior_chain_kappa_min": envelope.prior_chain_kappa_min,
                    "prior_chain_dispersion": envelope.prior_chain_dispersion,
                    "prior_hops": envelope.prior_hops,
                },
                trace_parent=envelope.trace_parent,
            )
        )

        return tracker

    def observe(self, envelope: HandoffEnvelope, hop_kappa: Optional[float]) -> ChainKappaState:
        """Record one hop's enforced kappa proxy and return the running state.

        hop_kappa is the per-agent ENFORCED proxy kappa for this hop (the
        caller passes agent.kappa_compat) — the R*(1-N) proxy, not true
        kappa. A hop with hop_kappa=None, or whose envelope.representation_id
        differs from the chain's first observed representation_id, is not
        comparable: it is excluded from the running min/dispersion and the
        chain is flagged incomparable=True (sticky — never clears).
        """
        if self._first_representation_id is None:
            self._first_representation_id = envelope.representation_id
            representation_mismatch = False
        else:
            representation_mismatch = envelope.representation_id != self._first_representation_id

        if representation_mismatch:
            self._incomparable = True
        if hop_kappa is None:
            self._incomparable = True

        comparable = hop_kappa is not None and not representation_mismatch
        if comparable:
            self._hop_kappas.append(hop_kappa)
            self._comparable_hops += 1
            if self._chain_kappa_min is None or hop_kappa < self._chain_kappa_min:
                self._chain_kappa_min = hop_kappa

        self._hops += 1

        dispersion = statistics.pstdev(self._hop_kappas) if len(self._hop_kappas) >= 1 else 0.0

        state = ChainKappaState(
            chain_kappa_min=self._chain_kappa_min,
            chain_kappa_dispersion=dispersion,
            hops=self._hops,
            comparable_hops=self._comparable_hops,
            incomparable=self._incomparable,
            is_proxy=True,
        )

        emit(
            TraceRecord(
                event="chain_kappa_observe",
                reason="INCOMPARABLE" if self._incomparable else "OBSERVED",
                handoff_id=envelope.handoff_id,
                detail={
                    "hop_kappa": hop_kappa,
                    "chain_kappa_min": state.chain_kappa_min,
                    "incomparable": state.incomparable,
                },
                trace_parent=envelope.trace_parent,
            )
        )

        return state
