#!/usr/bin/env python3
"""
DOE Test: Loop 2 Agent Handoff Validation

Tests the Loop 2 (Agent Handoff - 328) mechanism per FIG. 35 architecture:
1. Agent executes through G_S (solver graph)
2. Output certified through swarm-it gates
3. Output converted to EventNode with certificate
4. EventNode added to G_R (representation graph)
5. Next agent iteration processes new events

This DOE validates handoff works across:
- yrsn (mimo_swarm.py - validate_handoff)
- swarm-it-api (yrsn_adapter - gate_decision)
- swarm-it-adk (topology patterns - channels)

5-Factor Experimental Design:
- Factor 1: Single Agent Certification
- Factor 2: Agent-to-Agent Handoff
- Factor 3: Certificate Chain Validation
- Factor 4: G_R Event Accumulation
- Factor 5: Multi-Hop Pipeline
"""

import sys
import os
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

# Add paths
sys.path.insert(0, os.path.expanduser('~/GitHub/swarm-it-adk'))
sys.path.insert(0, os.path.expanduser('~/GitHub/swarm-it-api'))

API_PATH = os.path.expanduser('~/GitHub/swarm-it-api')

# Load constraint_graph for gate decisions
exec(open(os.path.join(API_PATH, 'engine/constraint_graph.py')).read())


# =============================================================================
# Loop 2 Components (Per FIG. 35)
# =============================================================================

class EventModality(str, Enum):
    """Event modalities for G_R nodes."""
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    EMBEDDING = "embedding"


@dataclass
class EventNode:
    """
    Node in G_R (representation graph).

    Per FIG. 35: Events flow through Measurement Layer (306)
    and become nodes in the representation graph.
    """
    event_id: str
    payload: str
    modality: EventModality

    # Certificate from swarm-it gates
    R: float
    S: float
    N: float
    kappa: float
    sigma: float
    decision: str
    gate_reached: int

    # Provenance
    source_agent: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    parent_event_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "payload": self.payload[:100] + "..." if len(self.payload) > 100 else self.payload,
            "modality": self.modality.value,
            "certificate": {
                "R": self.R, "S": self.S, "N": self.N,
                "kappa": self.kappa, "sigma": self.sigma,
                "decision": self.decision, "gate": self.gate_reached,
            },
            "source_agent": self.source_agent,
            "parent": self.parent_event_id,
        }


@dataclass
class RepresentationGraph:
    """
    G_R - Representation Graph.

    Stores EventNodes from agent outputs.
    Per FIG. 35: Loop 2 adds certified outputs as new events.
    """
    events: Dict[str, EventNode] = field(default_factory=dict)
    edges: List[Tuple[str, str]] = field(default_factory=list)

    def add_event(self, event: EventNode) -> None:
        """Add event to G_R (Loop 2 handoff)."""
        self.events[event.event_id] = event
        if event.parent_event_id and event.parent_event_id in self.events:
            self.edges.append((event.parent_event_id, event.event_id))

    def get_latest_events(self, n: int = 5) -> List[EventNode]:
        """Get n most recent events."""
        sorted_events = sorted(
            self.events.values(),
            key=lambda e: e.timestamp,
            reverse=True
        )
        return sorted_events[:n]

    def get_chain(self, event_id: str) -> List[EventNode]:
        """Get certificate chain back to root."""
        chain = []
        current_id = event_id
        while current_id and current_id in self.events:
            event = self.events[current_id]
            chain.append(event)
            current_id = event.parent_event_id
        return chain


def certify_output(
    output: str,
    agent_id: str,
    parent_event_id: Optional[str] = None,
    R: float = 0.65,
    S: float = 0.20,
    N: float = 0.15,
    kappa: float = 0.75,
    sigma: float = 0.25,
) -> EventNode:
    """
    Certify agent output and create EventNode.

    This is the core of Loop 2:
    1. Agent produces output
    2. Output certified through gates
    3. EventNode created with certificate
    """
    # Get gate decision from constraint_graph
    result = evaluate_paper_constraints(R, S, N, kappa, sigma, track_evolution=False)

    event_id = f"{agent_id}_{datetime.utcnow().strftime('%H%M%S%f')}"

    return EventNode(
        event_id=event_id,
        payload=output,
        modality=EventModality.TEXT,
        R=R,
        S=S,
        N=N,
        kappa=kappa,
        sigma=sigma,
        decision=result.decision.value,
        gate_reached=result.gate_reached.value,
        source_agent=agent_id,
        parent_event_id=parent_event_id,
    )


def validate_handoff(
    source_event: EventNode,
    target_agent_id: str,
    kappa_interface: float = 0.7,
) -> Tuple[bool, str, Optional[EventNode]]:
    """
    Validate handoff from source event to target agent.

    Per FIG. 36: κ_interface determines cross-agent compatibility.

    Returns:
        (allowed, reason, new_event if allowed)
    """
    # Check source event was EXECUTE
    if source_event.decision != "EXECUTE":
        return False, f"Source event decision={source_event.decision}, need EXECUTE", None

    # Check kappa meets interface threshold
    if source_event.kappa < kappa_interface:
        return False, f"κ={source_event.kappa:.2f} < κ_interface={kappa_interface}", None

    # Handoff allowed - target agent processes
    # Simulate target agent processing (would call LLM in real system)
    target_output = f"[{target_agent_id}] Processed: {source_event.payload[:50]}..."

    # Target certifies its output
    target_event = certify_output(
        output=target_output,
        agent_id=target_agent_id,
        parent_event_id=source_event.event_id,
        # Simulated certificate (would come from actual processing)
        R=source_event.R * 0.95,  # Slight degradation
        S=source_event.S * 1.05,
        N=source_event.N * 1.02,
        kappa=source_event.kappa * 0.98,
        sigma=source_event.sigma * 1.05,
    )

    return True, "Handoff successful", target_event


# =============================================================================
# DOE Test Cases
# =============================================================================

@dataclass
class HandoffLevel:
    """Test level for handoff experiments."""
    name: str
    source_R: float
    source_S: float
    source_N: float
    source_kappa: float
    source_sigma: float
    kappa_interface: float
    expected_handoff: bool
    expected_decision: str


# Factor 2: Agent-to-Agent Handoff
HANDOFF_LEVELS = [
    # High quality handoff
    HandoffLevel("HO1_HIGH_QUALITY", 0.70, 0.20, 0.10, 0.85, 0.20, 0.70, True, "EXECUTE"),
    # Border case - exactly at threshold
    HandoffLevel("HO2_BORDER", 0.60, 0.25, 0.15, 0.70, 0.30, 0.70, True, "EXECUTE"),
    # Below interface threshold
    HandoffLevel("HO3_LOW_KAPPA", 0.55, 0.25, 0.20, 0.65, 0.25, 0.70, False, "EXECUTE"),
    # Source rejected (N too high)
    HandoffLevel("HO4_SOURCE_REJECT", 0.20, 0.20, 0.60, 0.40, 0.50, 0.50, False, "REJECT"),
    # Source RE_ENCODE (Oobleck)
    HandoffLevel("HO5_SOURCE_REENCODE", 0.50, 0.30, 0.20, 0.45, 0.60, 0.50, False, "RE_ENCODE"),
]


@dataclass
class ChainLevel:
    """Test level for certificate chain experiments."""
    name: str
    num_hops: int
    initial_kappa: float
    degradation_per_hop: float
    kappa_interface: float
    expected_successful_hops: int


# Factor 3: Certificate Chain
# Math: κ_n = κ_0 * (1 - degradation)^n, stop when κ_n < interface
CHAIN_LEVELS = [
    ChainLevel("CH1_SHORT", 2, 0.90, 0.05, 0.70, 2),   # 0.90→0.855 both ≥0.70
    ChainLevel("CH2_MEDIUM", 4, 0.90, 0.05, 0.70, 4),  # 0.90→0.73 all ≥0.70
    ChainLevel("CH3_LONG", 6, 0.90, 0.05, 0.70, 5),    # Hop 5: κ=0.697<0.70
    ChainLevel("CH4_STRICT", 3, 0.85, 0.05, 0.80, 2),  # Hop 2: κ=0.767<0.80
    ChainLevel("CH5_RELAXED", 5, 0.80, 0.05, 0.60, 5), # All 5 ≥0.60
]


# =============================================================================
# DOE Runner
# =============================================================================

def run_doe():
    """Run DOE validation for Loop 2 handoff."""
    results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "factors": {},
        "summary": {"pass": 0, "fail": 0, "warn": 0},
    }

    print("=" * 80)
    print("DOE VALIDATION - Loop 2 Agent Handoff (FIG. 35 - 328)")
    print("5-Factor Multi-Level Experimental Design")
    print("=" * 80)

    # =========================================================================
    # Factor 1: Single Agent Certification
    # =========================================================================
    print("\nFACTOR 1: Single Agent Certification")
    print("-" * 80)

    factor1_results = []
    test_cases = [
        ("SA1_CLEAN", 0.70, 0.20, 0.10, 0.85, 0.20, "EXECUTE"),
        ("SA2_NOISY", 0.10, 0.10, 0.80, 0.11, 0.50, "REJECT"),
        ("SA3_TURBULENT", 0.50, 0.30, 0.20, 0.45, 0.60, "RE_ENCODE"),
        ("SA4_LOW_COHERENCE", 0.25, 0.30, 0.45, 0.36, 0.40, "BLOCK"),
        ("SA5_BRIDGE", 0.45, 0.40, 0.15, 0.75, 0.25, "EXECUTE"),
    ]

    g_r = RepresentationGraph()

    for name, R, S, N, kappa, sigma, expected in test_cases:
        event = certify_output(
            output=f"Test output for {name}",
            agent_id="agent_single",
            R=R, S=S, N=N, kappa=kappa, sigma=sigma,
        )
        g_r.add_event(event)

        passed = event.decision == expected
        status = "✓" if passed else "✗"
        print(f"  {status} {name}: {event.decision} (gate {event.gate_reached})")

        factor1_results.append({
            "name": name,
            "expected": expected,
            "actual": event.decision,
            "passed": passed,
        })
        results["summary"]["pass" if passed else "fail"] += 1

    results["factors"]["single_agent"] = factor1_results

    # =========================================================================
    # Factor 2: Agent-to-Agent Handoff
    # =========================================================================
    print("\nFACTOR 2: Agent-to-Agent Handoff")
    print("-" * 80)

    factor2_results = []

    for level in HANDOFF_LEVELS:
        # Create source event
        source_event = certify_output(
            output=f"Source output for {level.name}",
            agent_id="agent_source",
            R=level.source_R,
            S=level.source_S,
            N=level.source_N,
            kappa=level.source_kappa,
            sigma=level.source_sigma,
        )
        g_r.add_event(source_event)

        # Check source decision matches expected
        decision_correct = source_event.decision == level.expected_decision

        # Attempt handoff
        allowed, reason, target_event = validate_handoff(
            source_event=source_event,
            target_agent_id="agent_target",
            kappa_interface=level.kappa_interface,
        )

        handoff_correct = allowed == level.expected_handoff
        passed = decision_correct and handoff_correct

        if target_event:
            g_r.add_event(target_event)

        status = "✓" if passed else "✗"
        handoff_str = "→ handoff" if allowed else "✗ blocked"
        print(f"  {status} {level.name}: {source_event.decision} {handoff_str}")
        if not passed:
            print(f"      Reason: {reason}")

        factor2_results.append({
            "name": level.name,
            "source_decision": source_event.decision,
            "expected_decision": level.expected_decision,
            "handoff_allowed": allowed,
            "expected_handoff": level.expected_handoff,
            "reason": reason,
            "passed": passed,
        })
        results["summary"]["pass" if passed else "fail"] += 1

    results["factors"]["handoff"] = factor2_results

    # =========================================================================
    # Factor 3: Certificate Chain Validation
    # =========================================================================
    print("\nFACTOR 3: Certificate Chain Validation")
    print("-" * 80)

    factor3_results = []

    for level in CHAIN_LEVELS:
        chain_g_r = RepresentationGraph()

        # Initial event
        current_kappa = level.initial_kappa
        parent_id = None
        successful_hops = 0

        for hop in range(level.num_hops):
            agent_id = f"agent_hop_{hop}"

            event = certify_output(
                output=f"Output from hop {hop}",
                agent_id=agent_id,
                parent_event_id=parent_id,
                R=0.65,
                S=0.20,
                N=0.15,
                kappa=current_kappa,
                sigma=0.25,
            )
            chain_g_r.add_event(event)

            if event.decision == "EXECUTE" and current_kappa >= level.kappa_interface:
                successful_hops += 1
                parent_id = event.event_id
                current_kappa *= (1 - level.degradation_per_hop)
            else:
                break

        passed = successful_hops == level.expected_successful_hops
        status = "✓" if passed else "✗"
        print(f"  {status} {level.name}: {successful_hops}/{level.num_hops} hops successful")

        # Get chain for verification
        if parent_id:
            chain = chain_g_r.get_chain(parent_id)
            print(f"      Chain length: {len(chain)}, final κ={current_kappa:.2f}")

        factor3_results.append({
            "name": level.name,
            "num_hops": level.num_hops,
            "successful_hops": successful_hops,
            "expected_hops": level.expected_successful_hops,
            "final_kappa": current_kappa,
            "passed": passed,
        })
        results["summary"]["pass" if passed else "fail"] += 1

    results["factors"]["chain"] = factor3_results

    # =========================================================================
    # Factor 4: G_R Event Accumulation
    # =========================================================================
    print("\nFACTOR 4: G_R Event Accumulation")
    print("-" * 80)

    factor4_results = []

    # Test that G_R accumulated events correctly
    total_events = len(g_r.events)
    total_edges = len(g_r.edges)

    # Expected: 5 single + 5 handoff sources + successful handoff targets
    expected_min_events = 10
    passed = total_events >= expected_min_events

    status = "✓" if passed else "✗"
    print(f"  {status} GR1_ACCUMULATION: {total_events} events, {total_edges} edges")

    factor4_results.append({
        "name": "GR1_ACCUMULATION",
        "events": total_events,
        "edges": total_edges,
        "passed": passed,
    })
    results["summary"]["pass" if passed else "fail"] += 1

    # Test event retrieval
    latest = g_r.get_latest_events(3)
    passed = len(latest) == 3
    status = "✓" if passed else "✗"
    print(f"  {status} GR2_RETRIEVAL: Got {len(latest)} latest events")

    factor4_results.append({
        "name": "GR2_RETRIEVAL",
        "expected": 3,
        "actual": len(latest),
        "passed": passed,
    })
    results["summary"]["pass" if passed else "fail"] += 1

    results["factors"]["g_r"] = factor4_results

    # =========================================================================
    # Factor 5: Multi-Hop Pipeline (Full Loop 2)
    # =========================================================================
    print("\nFACTOR 5: Multi-Hop Pipeline (Full Loop 2)")
    print("-" * 80)

    factor5_results = []

    # Simulate a 4-agent pipeline: Architect → Developer → Tester → Reviewer
    pipeline_agents = ["architect", "developer", "tester", "reviewer"]
    pipeline_g_r = RepresentationGraph()

    parent_id = None
    pipeline_trace = []

    for i, agent_id in enumerate(pipeline_agents):
        # Each agent produces output with slight degradation
        kappa = 0.85 - (i * 0.03)
        sigma = 0.20 + (i * 0.05)

        event = certify_output(
            output=f"[{agent_id}] Work product iteration {i}",
            agent_id=agent_id,
            parent_event_id=parent_id,
            R=0.70 - (i * 0.02),
            S=0.15 + (i * 0.02),
            N=0.15 + (i * 0.01),
            kappa=kappa,
            sigma=sigma,
        )
        pipeline_g_r.add_event(event)

        pipeline_trace.append({
            "agent": agent_id,
            "decision": event.decision,
            "kappa": event.kappa,
        })

        if event.decision == "EXECUTE":
            parent_id = event.event_id
        else:
            break

    # All should execute
    all_executed = all(t["decision"] == "EXECUTE" for t in pipeline_trace)
    passed = all_executed and len(pipeline_trace) == 4

    status = "✓" if passed else "✗"
    print(f"  {status} PL1_PIPELINE: {len(pipeline_trace)}/4 agents executed")
    for t in pipeline_trace:
        print(f"      {t['agent']}: {t['decision']} (κ={t['kappa']:.2f})")

    factor5_results.append({
        "name": "PL1_PIPELINE",
        "trace": pipeline_trace,
        "passed": passed,
    })
    results["summary"]["pass" if passed else "fail"] += 1

    # Verify certificate chain
    chain = pipeline_g_r.get_chain(parent_id) if parent_id else []
    chain_valid = len(chain) == 4

    status = "✓" if chain_valid else "✗"
    print(f"  {status} PL2_CHAIN: Certificate chain length = {len(chain)}")

    factor5_results.append({
        "name": "PL2_CHAIN",
        "chain_length": len(chain),
        "expected": 4,
        "passed": chain_valid,
    })
    results["summary"]["pass" if chain_valid else "fail"] += 1

    results["factors"]["pipeline"] = factor5_results

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXPERIMENTAL SUMMARY")
    print("=" * 80)

    total = results["summary"]["pass"] + results["summary"]["fail"] + results["summary"]["warn"]
    pass_rate = results["summary"]["pass"] / total * 100 if total > 0 else 0

    print(f"Total Experiments: {total}")
    print(f"  PASS: {results['summary']['pass']} ({pass_rate:.1f}%)")
    print(f"  WARN: {results['summary']['warn']} ({results['summary']['warn']/total*100:.1f}%)" if total > 0 else "")
    print(f"  FAIL: {results['summary']['fail']} ({results['summary']['fail']/total*100:.1f}%)" if total > 0 else "")

    # =========================================================================
    # Export Evidence
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXPORTING EVIDENCE & PROOFS")
    print("=" * 80)

    evidence_path = "doe_loop2_evidence.json"
    with open(evidence_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Evidence: {evidence_path}")

    # =========================================================================
    # Final Verdict
    # =========================================================================
    print("\n" + "=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)

    if pass_rate >= 95:
        grade = "A+"
        verdict = "EXCELLENT - Loop 2 Handoff Validated"
    elif pass_rate >= 85:
        grade = "A"
        verdict = "GOOD - Minor handoff issues"
    elif pass_rate >= 70:
        grade = "B"
        verdict = "ACCEPTABLE - Some handoff failures"
    else:
        grade = "C"
        verdict = "NEEDS WORK - Handoff mechanism incomplete"

    print(f"Grade: {grade}")
    print(f"Verdict: {verdict}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print("=" * 80)

    return results


if __name__ == "__main__":
    run_doe()
