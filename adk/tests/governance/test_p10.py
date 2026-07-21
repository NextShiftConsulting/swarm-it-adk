"""Tests for the P10 repair-vs-handoff-vs-refuse decision policy (V-013 T7).

decide() is a pure decision function over injected state + budget: no
network/model calls, no gate/kappa math. It consumes flags (capable,
successor_available, chain_incomparable, repair_improved_kappa) and decides
whether the current agent may REPAIR locally, must HAND OFF to a
capability-matched successor, or must REFUSE. Fail-closed: any budget limit
hit is REFUSE, never a default-permissive path.
"""

import dataclasses
from pathlib import Path

import pytest

from swarm_it.governance import get_trace, reset_trace
from swarm_it.governance.cycle_guard import CycleGuard
from swarm_it.governance.p10 import P10Budget, P10Decision, P10State, decide, enter_p10_cycle


DEFAULT_BUDGET = P10Budget(max_repair_retries=2, max_chain_hops=5, max_total_attempts=10)


def _make_state(**overrides) -> P10State:
    fields = dict(
        capable=True,
        successor_available=False,
        chain_incomparable=False,
        repair_attempts=0,
        hops=0,
        total_attempts=0,
        repair_improved_kappa=False,
    )
    fields.update(overrides)
    return P10State(**fields)


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_trace()
    yield
    reset_trace()


def test_repair_when_capable_with_budget():
    state = _make_state(capable=True, repair_attempts=0, successor_available=False)

    decision = decide(state, DEFAULT_BUDGET)

    assert decision.action == "REPAIR"
    assert decision.reason == "LOCAL_REPAIR"


def test_handoff_when_not_capable_but_successor():
    state = _make_state(capable=False, successor_available=True)

    decision = decide(state, DEFAULT_BUDGET)

    assert decision.action == "HANDOFF"
    assert decision.reason == "CAPABILITY_MATCHED_HANDOFF"


def test_handoff_when_repair_budget_exhausted():
    budget = P10Budget(max_repair_retries=2, max_chain_hops=5, max_total_attempts=10)
    state = _make_state(capable=True, repair_attempts=2, successor_available=True)

    decision = decide(state, budget)

    assert decision.action == "HANDOFF"
    assert decision.reason == "CAPABILITY_MATCHED_HANDOFF"


def test_handoff_when_repair_stalled():
    state = _make_state(
        capable=True,
        repair_attempts=1,
        repair_improved_kappa=False,
        successor_available=True,
    )

    decision = decide(state, DEFAULT_BUDGET)

    assert decision.action == "HANDOFF"
    assert decision.reason == "CAPABILITY_MATCHED_HANDOFF"


def test_refuse_when_no_path():
    state = _make_state(capable=False, successor_available=False)

    decision = decide(state, DEFAULT_BUDGET)

    assert decision.action == "REFUSE"
    assert decision.reason == "NO_PATH"


def test_refuse_on_incomparable():
    state = _make_state(
        chain_incomparable=True,
        capable=True,
        repair_attempts=0,
        successor_available=True,
    )

    decision = decide(state, DEFAULT_BUDGET)

    assert decision.action == "REFUSE"
    assert decision.reason == "CHAIN_INCOMPARABLE"


def test_refuse_on_max_hops():
    budget = P10Budget(max_repair_retries=2, max_chain_hops=3, max_total_attempts=10)
    state = _make_state(hops=3, capable=True, successor_available=True)

    decision = decide(state, budget)

    assert decision.action == "REFUSE"
    assert decision.reason == "MAX_CHAIN_HOPS_EXCEEDED"


def test_refuse_on_max_total_attempts():
    budget = P10Budget(max_repair_retries=2, max_chain_hops=5, max_total_attempts=4)
    state = _make_state(total_attempts=4, capable=True, successor_available=True)

    decision = decide(state, budget)

    assert decision.action == "REFUSE"
    assert decision.reason == "MAX_TOTAL_ATTEMPTS_EXCEEDED"


def test_decision_emits_trace():
    state = _make_state(capable=True, repair_attempts=0)

    decide(state, DEFAULT_BUDGET)

    trace = get_trace()
    assert trace[-1].event == "p10_decision"
    assert trace[-1].reason == "LOCAL_REPAIR"


def test_decision_is_frozen_dataclass():
    decision = P10Decision(action="REPAIR", reason="LOCAL_REPAIR")
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.action = "REFUSE"


def test_repair_continues_when_improving():
    state = _make_state(
        capable=True,
        repair_attempts=1,
        repair_improved_kappa=True,
        successor_available=True,
    )
    budget = P10Budget(max_repair_retries=2, max_chain_hops=5, max_total_attempts=10)

    decision = decide(state, budget)

    assert decision.action == "REPAIR"
    assert decision.reason == "LOCAL_REPAIR"


def test_handoff_on_budget_exhaustion_not_stall():
    state = _make_state(
        capable=True,
        repair_attempts=2,
        repair_improved_kappa=True,
        successor_available=True,
    )
    budget = P10Budget(max_repair_retries=2, max_chain_hops=5, max_total_attempts=10)

    decision = decide(state, budget)

    assert decision.action == "HANDOFF"
    assert decision.reason == "CAPABILITY_MATCHED_HANDOFF"


def test_repair_decision_enters_repair_mode_blocks_handoff():
    """enter_p10_cycle on a REPAIR decision must enter CycleGuard's
    "repair" mode, so a subsequent attempt to enter "handoff" inside it
    raises — proving REPAIR and HANDOFF are mutually exclusive at runtime
    (Claim 9) all the way from a P10Decision through the guard."""
    decision = P10Decision(action="REPAIR", reason="LOCAL_REPAIR")

    with enter_p10_cycle(decision):
        with pytest.raises(RuntimeError):
            with CycleGuard.enter("handoff"):
                pass


def test_handoff_decision_enters_handoff_mode_blocks_repair():
    """Symmetric case: a HANDOFF decision enters "handoff" mode, so a
    subsequent "repair" entry inside it raises."""
    decision = P10Decision(action="HANDOFF", reason="CAPABILITY_MATCHED_HANDOFF")

    with enter_p10_cycle(decision):
        with pytest.raises(RuntimeError):
            with CycleGuard.enter("repair"):
                pass


def test_refuse_decision_is_noop_context():
    """A REFUSE decision has nothing to guard: entering enter_p10_cycle
    must not raise and must not lock either mode, so a CycleGuard.enter
    of either mode is still allowed inside it."""
    decision = P10Decision(action="REFUSE", reason="NO_PATH")

    with enter_p10_cycle(decision):
        with CycleGuard.enter("repair"):
            pass
        with CycleGuard.enter("handoff"):
            pass


def test_no_prohibited_tokens_in_source():
    from swarm_it.governance import p10

    source = Path(p10.__file__).read_text(encoding="utf-8")
    assert "sigma" not in source.lower(), f"'sigma' found in {p10.__file__}"
    assert "kappa_gate" not in source.lower(), f"'kappa_gate' found in {p10.__file__}"
    assert "time.time(" not in source
    assert "datetime.now(" not in source
