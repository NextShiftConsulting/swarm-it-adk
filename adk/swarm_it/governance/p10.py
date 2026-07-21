"""P10 repair-vs-handoff-vs-refuse decision policy (Claim 9 / V-013 T7).

When a hop is unhealthy, this decides whether the CURRENT agent may
REPAIR locally, must HAND OFF to a capability-matched successor, or must
REFUSE. It is pure decision logic over injected state + budget: no
network/model calls, no gate or kappa math (it consumes flags such as
capable/successor_available/chain_incomparable, it does not compute
kappa itself). This module never enters CycleGuard — deciding "REPAIR"
or "HANDOFF" here only picks the mode; the caller is responsible for
actually entering CycleGuard.enter("repair") / CycleGuard.enter("handoff")
under the morph-repair/handoff XOR mutual exclusion (Claim 9).

Fail-closed by construction: any budget limit hit (chain hops, total
attempts) or an incomparable chain-kappa signal is REFUSE before REPAIR
or HANDOFF is ever considered. There is no default-permissive path.
"""

from dataclasses import dataclass

from swarm_it.governance.trace import TraceRecord, emit


@dataclass(frozen=True)
class P10Budget:
    """Budget limits governing how much repair/handoff activity is allowed."""

    max_repair_retries: int
    max_chain_hops: int
    max_total_attempts: int


@dataclass(frozen=True)
class P10State:
    """Snapshot of the flags decide() needs — no gate/kappa math inside."""

    capable: bool
    successor_available: bool
    chain_incomparable: bool
    repair_attempts: int
    hops: int
    total_attempts: int
    repair_improved_kappa: bool = False


@dataclass(frozen=True)
class P10Decision:
    """The chosen action and the reason code that produced it."""

    action: str
    reason: str


def decide(state: P10State, budget: P10Budget) -> P10Decision:
    """Decide REPAIR, HANDOFF, or REFUSE for one unhealthy hop.

    Evaluated in strict priority order, fail-closed:

    1. Fail-closed guards (REFUSE): incomparable chain-kappa, chain-hop
       budget exhausted, or total-attempt budget exhausted.
    2. REPAIR: the agent is capable AND repair budget remains AND the
       repair track record has not stalled (first repair, or the last
       repair improved chain-kappa).
    3. HANDOFF: repair is not permitted (not capable, budget exhausted,
       or stalled) but a capability-matched successor is available.
    4. REFUSE (NO_PATH): none of the above — no repair path and no
       successor to hand off to.
    """
    if state.chain_incomparable:
        decision = P10Decision(action="REFUSE", reason="CHAIN_INCOMPARABLE")
    elif state.hops >= budget.max_chain_hops:
        decision = P10Decision(action="REFUSE", reason="MAX_CHAIN_HOPS_EXCEEDED")
    elif state.total_attempts >= budget.max_total_attempts:
        decision = P10Decision(action="REFUSE", reason="MAX_TOTAL_ATTEMPTS_EXCEEDED")
    else:
        repair_stalled = state.repair_attempts > 0 and not state.repair_improved_kappa
        repair_permitted = (
            state.capable and state.repair_attempts < budget.max_repair_retries and not repair_stalled
        )
        if repair_permitted:
            decision = P10Decision(action="REPAIR", reason="LOCAL_REPAIR")
        elif state.successor_available:
            decision = P10Decision(action="HANDOFF", reason="CAPABILITY_MATCHED_HANDOFF")
        else:
            decision = P10Decision(action="REFUSE", reason="NO_PATH")

    emit(
        TraceRecord(
            event="p10_decision",
            reason=decision.reason,
            handoff_id=None,
            detail={
                "action": decision.action,
                "capable": state.capable,
                "successor_available": state.successor_available,
                "chain_incomparable": state.chain_incomparable,
                "repair_attempts": state.repair_attempts,
                "hops": state.hops,
                "total_attempts": state.total_attempts,
                "repair_improved_kappa": state.repair_improved_kappa,
            },
            trace_parent=None,
        )
    )

    return decision
