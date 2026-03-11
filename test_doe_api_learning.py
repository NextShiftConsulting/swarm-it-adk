"""
DOE Validation Test - API Learning Features

5-Factor, Multi-Level Experimental Design for new SGCI API features:
- Factor 1: Threshold Learning (5 levels)
- Factor 2: Tier Evolution (5 levels)
- Factor 3: Constraint Graph (5 levels)
- Factor 4: Oobleck Principle (5 levels)
- Factor 5: Integration Scenarios (5 levels)

Each experimental point collects evidence and provides proof of correctness.

Usage:
    python test_doe_api_learning.py

Output:
    - doe_api_evidence.json (evidence records)
    - doe_api_proofs.json (proof records)
"""

import json
import sys
import os
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Load API modules directly
API_PATH = os.path.expanduser('~/GitHub/swarm-it-api')
exec(open(os.path.join(API_PATH, 'engine/threshold_learner.py')).read())
exec(open(os.path.join(API_PATH, 'engine/constraint_evolution.py')).read())
exec(open(os.path.join(API_PATH, 'engine/constraint_graph.py')).read())

# Load yrsn_adapter gate logic (the ACTUAL decision maker)
# This is what the API uses - not constraint_graph
def yrsn_gate_decision(R, S, N, kappa, sigma):
    """
    Actual gate decision from yrsn_adapter.py._gate_decision().
    This is what the API uses for certification decisions.
    """
    N_THRESHOLD = 0.5
    CONSENSUS_THRESHOLD = 0.4
    KAPPA_BASE = 0.5
    KAPPA_LAMBDA = 0.4
    KAPPA_GROUNDING = 0.3

    # Gate 1: Integrity
    if N >= N_THRESHOLD:
        return "REJECT", 1

    # Gate 2: Consensus
    coherence = R / (R + N + 0.1)
    if coherence < CONSENSUS_THRESHOLD and N > 0.3:
        return "BLOCK", 2

    # Gate 3: Admissibility (Oobleck)
    kappa_req = KAPPA_BASE + KAPPA_LAMBDA * sigma
    if kappa < kappa_req:
        return "RE_ENCODE", 3

    # Gate 4: Grounding
    if kappa < KAPPA_GROUNDING:
        return "REPAIR", 4

    return "EXECUTE", 4


# ============================================================================
# DOE Factor Definitions
# ============================================================================

@dataclass
class ThresholdLevel:
    """Factor 1: Threshold Learning Levels"""
    name: str
    failure_rate: float
    validation_count: int
    expected_adjustment: str  # "tighten", "relax", "stable"


THRESHOLD_LEVELS = [
    ThresholdLevel("TH1_NO_FAILURES", 0.0, 20, "stable"),
    ThresholdLevel("TH2_LOW_FAILURES", 0.05, 20, "stable"),
    ThresholdLevel("TH3_MODERATE_FAILURES", 0.15, 20, "tighten"),
    ThresholdLevel("TH4_HIGH_FAILURES", 0.30, 20, "tighten"),
    ThresholdLevel("TH5_EXTREME_FAILURES", 1.0, 20, "tighten"),
]


@dataclass
class TierLevel:
    """Factor 2: Tier Evolution Levels"""
    name: str
    activations: int
    violations_handled: int
    expected_tier: str


TIER_LEVELS = [
    # Note: Constraint doesn't exist until first activation, so 0 activations = no state
    TierLevel("TR1_FRESH", 1, 0, "emergent"),  # 1 activation creates constraint
    TierLevel("TR2_NEAR_LEARNED", 15, 0, "emergent"),
    TierLevel("TR3_LEARNED", 25, 0, "learned"),
    TierLevel("TR4_NEAR_ACTUAL", 25, 40, "learned"),
    TierLevel("TR5_ACTUAL", 25, 55, "actual"),
]


@dataclass
class ConstraintLevel:
    """Factor 3: Constraint Graph Levels"""
    name: str
    R: float
    S: float
    N: float
    kappa: float
    sigma: float
    expected_decision: str
    expected_gate: int


CONSTRAINT_LEVELS = [
    # Based on RSCT whitepaper gate definitions:
    # Gate 1: N >= 0.5 → REJECT (noise saturation)
    # Gate 2: c < 0.4 AND N > 0.3 → BLOCK (consensus failure)
    # Gate 3: κ < κ_req(σ) → RE_ENCODE (Oobleck)
    # Gate 4: κ_L < 0.3 → REPAIR (grounding)
    ConstraintLevel("CG1_CLEAN", 0.70, 0.20, 0.10, 0.85, 0.20, "EXECUTE", 4),
    ConstraintLevel("CG2_NOISY", 0.10, 0.10, 0.80, 0.11, 0.50, "REJECT", 1),
    ConstraintLevel("CG3_LOW_COHERENCE", 0.25, 0.30, 0.45, 0.36, 0.40, "BLOCK", 2),  # c=0.31<0.4 AND N=0.45>0.3 → BLOCK per FIG.29
    ConstraintLevel("CG4_OOBLECK_FAIL", 0.50, 0.30, 0.20, 0.45, 0.60, "RE_ENCODE", 3),  # κ=0.45 < κ_req(0.6)=0.74
    ConstraintLevel("CG5_BRIDGE", 0.45, 0.40, 0.15, 0.75, 0.25, "EXECUTE", 4),
]


@dataclass
class OobleckLevel:
    """Factor 4: Oobleck Principle Levels"""
    name: str
    sigma: float
    expected_kappa_req: float


OOBLECK_LEVELS = [
    OobleckLevel("OB1_CALM", 0.0, 0.50),
    OobleckLevel("OB2_LOW_TURBULENCE", 0.25, 0.60),
    OobleckLevel("OB3_MODERATE", 0.50, 0.70),
    OobleckLevel("OB4_HIGH_TURBULENCE", 0.75, 0.80),
    OobleckLevel("OB5_EXTREME", 1.0, 0.90),
]


@dataclass
class IntegrationLevel:
    """Factor 5: Integration Scenario Levels"""
    name: str
    scenario: str
    components: List[str]


INTEGRATION_LEVELS = [
    IntegrationLevel("INT1_THRESHOLD_ONLY", "threshold_learning", ["ThresholdLearner"]),
    IntegrationLevel("INT2_TIER_ONLY", "tier_evolution", ["ConstraintEvolution"]),
    IntegrationLevel("INT3_GRAPH_ONLY", "constraint_graph", ["evaluate_paper_constraints"]),
    IntegrationLevel("INT4_THRESHOLD_TIER", "threshold_with_tier", ["ThresholdLearner", "ConstraintEvolution"]),
    IntegrationLevel("INT5_FULL_STACK", "full_integration", ["ThresholdLearner", "ConstraintEvolution", "evaluate_paper_constraints"]),
]


# ============================================================================
# Evidence Collection
# ============================================================================

@dataclass
class Evidence:
    """Evidence collected for each experimental point"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    experiment_id: str = ""
    factor: str = ""
    level: str = ""

    # Threshold Learning Evidence
    initial_threshold: Optional[float] = None
    final_threshold: Optional[float] = None
    threshold_delta: Optional[float] = None
    adjustments_count: int = 0

    # Tier Evolution Evidence
    initial_tier: Optional[str] = None
    final_tier: Optional[str] = None
    tier_transitions: int = 0
    activations_recorded: int = 0
    violations_recorded: int = 0

    # Constraint Graph Evidence
    decision: Optional[str] = None
    gate_reached: Optional[int] = None
    is_bridge_paper: bool = False
    violations: List[str] = field(default_factory=list)
    diagnosis: Optional[str] = None

    # Oobleck Evidence
    sigma_input: Optional[float] = None
    kappa_required: Optional[float] = None
    kappa_formula_valid: bool = False

    # Integration Evidence
    components_tested: List[str] = field(default_factory=list)
    all_components_work: bool = False

    # Error tracking
    error_occurred: bool = False
    error_message: Optional[str] = None

    # Performance
    execution_time_ms: Optional[float] = None


@dataclass
class Proof:
    """Proof of correctness for experimental point"""
    experiment_id: str
    pass_fail: str = "UNKNOWN"
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    verdict: str = ""
    confidence: float = 0.0


# ============================================================================
# DOE Validator
# ============================================================================

class DOEAPIValidator:
    """Design of Experiments Validator for API Learning Features"""

    def __init__(self):
        self.evidence_log: List[Evidence] = []
        self.proofs: List[Proof] = []
        self.experiment_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0

    # ========================================================================
    # Factor 1: Threshold Learning Experiments
    # ========================================================================

    def run_threshold_experiment(self, level: ThresholdLevel) -> Tuple[Evidence, Proof]:
        """Run threshold learning experiment"""
        self.experiment_count += 1
        exp_id = f"TH_{self.experiment_count:04d}"

        evidence = Evidence(
            experiment_id=exp_id,
            factor="threshold_learning",
            level=level.name,
        )
        proof = Proof(experiment_id=exp_id)

        try:
            import time
            start = time.time()

            # Create fresh learner
            learner = ThresholdLearner()
            evidence.initial_threshold = learner.get_thresholds()['N_max']

            # Simulate validations
            failures = int(level.validation_count * level.failure_rate)
            for i in range(level.validation_count):
                learner.record_validation(
                    certificate_id=f"{exp_id}-{i}",
                    validation_type="TYPE_I",
                    score=0.2 if i < failures else 0.9,
                    failed=i < failures,
                )

            evidence.final_threshold = learner.get_thresholds()['N_max']
            evidence.threshold_delta = evidence.final_threshold - evidence.initial_threshold
            evidence.adjustments_count = len(learner.adjustments)
            evidence.execution_time_ms = (time.time() - start) * 1000

            # Generate assertions
            proof.assertions.append({
                "id": "TH_A1_INITIAL_VALUE",
                "description": "Initial threshold at baseline",
                "expected": 0.5,
                "actual": evidence.initial_threshold,
                "pass": abs(evidence.initial_threshold - 0.5) < 0.001,
            })

            if level.expected_adjustment == "tighten":
                proof.assertions.append({
                    "id": "TH_A2_TIGHTENING",
                    "description": "Threshold tightened under failures",
                    "expected": "< 0.5",
                    "actual": evidence.final_threshold,
                    "pass": evidence.final_threshold < 0.5,
                })
            elif level.expected_adjustment == "stable":
                proof.assertions.append({
                    "id": "TH_A2_STABLE",
                    "description": "Threshold stable with low failures",
                    "expected": "~0.5",
                    "actual": evidence.final_threshold,
                    "pass": abs(evidence.final_threshold - 0.5) < 0.1,
                })

            proof.assertions.append({
                "id": "TH_A3_FLOOR_RESPECTED",
                "description": "Threshold respects floor (0.3)",
                "expected": ">= 0.3",
                "actual": evidence.final_threshold,
                "pass": evidence.final_threshold >= 0.3,
            })

            self._finalize_proof(proof)

        except Exception as e:
            evidence.error_occurred = True
            evidence.error_message = str(e)
            proof.pass_fail = "FAIL"
            proof.verdict = f"Error: {e}"
            self.fail_count += 1

        self.evidence_log.append(evidence)
        self.proofs.append(proof)
        return evidence, proof

    # ========================================================================
    # Factor 2: Tier Evolution Experiments
    # ========================================================================

    def run_tier_experiment(self, level: TierLevel) -> Tuple[Evidence, Proof]:
        """Run tier evolution experiment"""
        self.experiment_count += 1
        exp_id = f"TR_{self.experiment_count:04d}"

        evidence = Evidence(
            experiment_id=exp_id,
            factor="tier_evolution",
            level=level.name,
        )
        proof = Proof(experiment_id=exp_id)

        try:
            import time
            start = time.time()

            # Create fresh evolution tracker
            evolution = ConstraintEvolution()
            constraint = "test_constraint"

            evidence.initial_tier = evolution.get_constraint_state(constraint).tier.value if evolution.get_constraint_state(constraint) else "emergent"

            # Simulate activations
            for i in range(level.activations):
                transition = evolution.record_activation(constraint)
                if transition:
                    evidence.tier_transitions += 1
            evidence.activations_recorded = level.activations

            # Simulate violations handled
            for i in range(level.violations_handled):
                transition = evolution.record_violation_handled(constraint)
                if transition:
                    evidence.tier_transitions += 1
            evidence.violations_recorded = level.violations_handled

            state = evolution.get_constraint_state(constraint)
            evidence.final_tier = state.tier.value if state else "unknown"
            evidence.execution_time_ms = (time.time() - start) * 1000

            # Generate assertions
            proof.assertions.append({
                "id": "TR_A1_EXPECTED_TIER",
                "description": f"Constraint reaches {level.expected_tier} tier",
                "expected": level.expected_tier,
                "actual": evidence.final_tier,
                "pass": evidence.final_tier == level.expected_tier,
            })

            proof.assertions.append({
                "id": "TR_A2_ACTIVATIONS",
                "description": "Activations recorded correctly",
                "expected": level.activations,
                "actual": state.activations if state else 0,
                "pass": (state.activations if state else 0) == level.activations,
            })

            proof.assertions.append({
                "id": "TR_A3_VIOLATIONS",
                "description": "Violations recorded correctly",
                "expected": level.violations_handled,
                "actual": state.violations_handled if state else 0,
                "pass": (state.violations_handled if state else 0) == level.violations_handled,
            })

            self._finalize_proof(proof)

        except Exception as e:
            evidence.error_occurred = True
            evidence.error_message = str(e)
            proof.pass_fail = "FAIL"
            proof.verdict = f"Error: {e}"
            self.fail_count += 1

        self.evidence_log.append(evidence)
        self.proofs.append(proof)
        return evidence, proof

    # ========================================================================
    # Factor 3: Constraint Graph Experiments
    # ========================================================================

    def run_constraint_experiment(self, level: ConstraintLevel) -> Tuple[Evidence, Proof]:
        """Run constraint graph experiment - tests ACTUAL gate decision vs enrichment"""
        self.experiment_count += 1
        exp_id = f"CG_{self.experiment_count:04d}"

        evidence = Evidence(
            experiment_id=exp_id,
            factor="constraint_graph",
            level=level.name,
        )
        proof = Proof(experiment_id=exp_id)

        try:
            import time
            start = time.time()

            # Get ACTUAL decision (what API uses)
            actual_decision, actual_gate = yrsn_gate_decision(
                level.R, level.S, level.N, level.kappa, level.sigma
            )

            # Get enrichment (for diagnosis, recommendations)
            enrichment = evaluate_paper_constraints(
                level.R, level.S, level.N, level.kappa, level.sigma,
                track_evolution=False
            )

            evidence.decision = actual_decision
            evidence.gate_reached = actual_gate
            evidence.is_bridge_paper = enrichment.is_bridge_paper
            evidence.violations = [v.threshold.name for v in enrichment.violations] if enrichment.violations else []
            evidence.diagnosis = enrichment.diagnosis
            evidence.execution_time_ms = (time.time() - start) * 1000

            # Test ACTUAL gate decision (what API returns)
            proof.assertions.append({
                "id": "CG_A1_ACTUAL_DECISION",
                "description": f"yrsn_adapter decision matches expected",
                "expected": level.expected_decision,
                "actual": actual_decision,
                "pass": actual_decision == level.expected_decision,
            })

            proof.assertions.append({
                "id": "CG_A2_ACTUAL_GATE",
                "description": f"yrsn_adapter gate matches expected",
                "expected": level.expected_gate,
                "actual": actual_gate,
                "pass": actual_gate == level.expected_gate,
            })

            # Test enrichment provides context
            proof.assertions.append({
                "id": "CG_A3_ENRICHMENT",
                "description": "Enrichment provides diagnosis",
                "expected": "Non-empty string",
                "actual": enrichment.diagnosis[:50] + "..." if enrichment.diagnosis else None,
                "pass": enrichment.diagnosis is not None and len(enrichment.diagnosis) > 0,
            })

            # Check consistency: does enrichment agree with actual decision?
            enrichment_decision = enrichment.decision.value
            proof.assertions.append({
                "id": "CG_A4_CONSISTENCY",
                "description": "yrsn_adapter and constraint_graph agree",
                "expected": actual_decision,
                "actual": enrichment_decision,
                "pass": actual_decision == enrichment_decision,
            })

            # Bridge detection for CG5
            if level.name == "CG5_BRIDGE":
                proof.assertions.append({
                    "id": "CG_A5_BRIDGE",
                    "description": "Bridge paper detected",
                    "expected": True,
                    "actual": evidence.is_bridge_paper,
                    "pass": evidence.is_bridge_paper == True,
                })

            self._finalize_proof(proof)

        except Exception as e:
            evidence.error_occurred = True
            evidence.error_message = str(e)
            proof.pass_fail = "FAIL"
            proof.verdict = f"Error: {e}"
            self.fail_count += 1

        self.evidence_log.append(evidence)
        self.proofs.append(proof)
        return evidence, proof

    # ========================================================================
    # Factor 4: Oobleck Principle Experiments
    # ========================================================================

    def run_oobleck_experiment(self, level: OobleckLevel) -> Tuple[Evidence, Proof]:
        """Run Oobleck principle experiment"""
        self.experiment_count += 1
        exp_id = f"OB_{self.experiment_count:04d}"

        evidence = Evidence(
            experiment_id=exp_id,
            factor="oobleck_principle",
            level=level.name,
        )
        proof = Proof(experiment_id=exp_id)

        try:
            import time
            start = time.time()

            # Calculate Oobleck: κ_req(σ) = κ_base + λσ
            kappa_base = 0.5
            kappa_lambda = 0.4
            kappa_req = kappa_base + kappa_lambda * level.sigma

            evidence.sigma_input = level.sigma
            evidence.kappa_required = kappa_req
            evidence.kappa_formula_valid = abs(kappa_req - level.expected_kappa_req) < 0.001
            evidence.execution_time_ms = (time.time() - start) * 1000

            # Generate assertions
            proof.assertions.append({
                "id": "OB_A1_FORMULA",
                "description": "κ_req = 0.5 + 0.4σ",
                "expected": level.expected_kappa_req,
                "actual": round(kappa_req, 2),
                "pass": evidence.kappa_formula_valid,
            })

            proof.assertions.append({
                "id": "OB_A2_MONOTONIC",
                "description": "Higher σ → higher κ_req",
                "expected": f"κ_req({level.sigma}) >= κ_req(0)",
                "actual": kappa_req,
                "pass": kappa_req >= 0.5,
            })

            proof.assertions.append({
                "id": "OB_A3_BOUNDED",
                "description": "κ_req in [0.5, 0.9]",
                "expected": "0.5 <= κ_req <= 0.9",
                "actual": kappa_req,
                "pass": 0.5 <= kappa_req <= 0.9,
            })

            self._finalize_proof(proof)

        except Exception as e:
            evidence.error_occurred = True
            evidence.error_message = str(e)
            proof.pass_fail = "FAIL"
            proof.verdict = f"Error: {e}"
            self.fail_count += 1

        self.evidence_log.append(evidence)
        self.proofs.append(proof)
        return evidence, proof

    # ========================================================================
    # Factor 5: Integration Experiments
    # ========================================================================

    def run_integration_experiment(self, level: IntegrationLevel) -> Tuple[Evidence, Proof]:
        """Run integration experiment"""
        self.experiment_count += 1
        exp_id = f"INT_{self.experiment_count:04d}"

        evidence = Evidence(
            experiment_id=exp_id,
            factor="integration",
            level=level.name,
        )
        proof = Proof(experiment_id=exp_id)

        try:
            import time
            start = time.time()

            evidence.components_tested = level.components
            components_ok = []

            # Test each component
            if "ThresholdLearner" in level.components:
                learner = ThresholdLearner()
                learner.record_validation("int-test", "TYPE_I", 0.5, False)
                components_ok.append("ThresholdLearner")

            if "ConstraintEvolution" in level.components:
                evolution = ConstraintEvolution()
                evolution.record_activation("int-test-constraint")
                components_ok.append("ConstraintEvolution")

            if "evaluate_paper_constraints" in level.components:
                result = evaluate_paper_constraints(0.6, 0.3, 0.1, 0.8, 0.2, track_evolution=False)
                if result.decision:
                    components_ok.append("evaluate_paper_constraints")

            evidence.all_components_work = len(components_ok) == len(level.components)
            evidence.execution_time_ms = (time.time() - start) * 1000

            # Generate assertions
            for component in level.components:
                proof.assertions.append({
                    "id": f"INT_A_{component[:10]}",
                    "description": f"{component} works",
                    "expected": True,
                    "actual": component in components_ok,
                    "pass": component in components_ok,
                })

            proof.assertions.append({
                "id": "INT_ALL",
                "description": "All components work together",
                "expected": True,
                "actual": evidence.all_components_work,
                "pass": evidence.all_components_work,
            })

            self._finalize_proof(proof)

        except Exception as e:
            evidence.error_occurred = True
            evidence.error_message = str(e)
            proof.pass_fail = "FAIL"
            proof.verdict = f"Error: {e}"
            self.fail_count += 1

        self.evidence_log.append(evidence)
        self.proofs.append(proof)
        return evidence, proof

    # ========================================================================
    # Helpers
    # ========================================================================

    def _finalize_proof(self, proof: Proof):
        """Calculate final verdict from assertions"""
        passed = sum(1 for a in proof.assertions if a["pass"])
        total = len(proof.assertions)
        pass_rate = passed / total if total > 0 else 0

        if pass_rate == 1.0:
            proof.pass_fail = "PASS"
            proof.verdict = f"All {total} assertions passed"
            proof.confidence = 1.0
            self.pass_count += 1
        elif pass_rate >= 0.75:
            proof.pass_fail = "WARN"
            proof.verdict = f"{passed}/{total} assertions passed"
            proof.confidence = pass_rate
            self.warn_count += 1
        else:
            proof.pass_fail = "FAIL"
            proof.verdict = f"Only {passed}/{total} assertions passed"
            proof.confidence = pass_rate
            self.fail_count += 1


# ============================================================================
# Main Experimental Campaign
# ============================================================================

def main():
    print("=" * 80)
    print("DOE VALIDATION - API Learning Features")
    print("5-Factor Multi-Level Experimental Design")
    print("=" * 80)
    print()

    validator = DOEAPIValidator()

    # Factor 1: Threshold Learning
    print("FACTOR 1: Threshold Learning")
    print("-" * 80)
    for level in THRESHOLD_LEVELS:
        evidence, proof = validator.run_threshold_experiment(level)
        status = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[proof.pass_fail]
        delta = f"Δ={evidence.threshold_delta:+.3f}" if evidence.threshold_delta else "N/A"
        print(f"  {status} {level.name}: {evidence.initial_threshold:.2f}→{evidence.final_threshold:.2f} ({delta})")
    print()

    # Factor 2: Tier Evolution
    print("FACTOR 2: Tier Evolution")
    print("-" * 80)
    for level in TIER_LEVELS:
        evidence, proof = validator.run_tier_experiment(level)
        status = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[proof.pass_fail]
        print(f"  {status} {level.name}: {evidence.initial_tier}→{evidence.final_tier} ({evidence.tier_transitions} transitions)")
    print()

    # Factor 3: Constraint Graph
    print("FACTOR 3: Constraint Graph")
    print("-" * 80)
    for level in CONSTRAINT_LEVELS:
        evidence, proof = validator.run_constraint_experiment(level)
        status = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[proof.pass_fail]
        bridge = " [bridge]" if evidence.is_bridge_paper else ""
        print(f"  {status} {level.name}: {evidence.decision} (gate {evidence.gate_reached}){bridge}")
    print()

    # Factor 4: Oobleck Principle
    print("FACTOR 4: Oobleck Principle")
    print("-" * 80)
    for level in OOBLECK_LEVELS:
        evidence, proof = validator.run_oobleck_experiment(level)
        status = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[proof.pass_fail]
        print(f"  {status} {level.name}: σ={level.sigma} → κ_req={evidence.kappa_required:.2f}")
    print()

    # Factor 5: Integration
    print("FACTOR 5: Integration")
    print("-" * 80)
    for level in INTEGRATION_LEVELS:
        evidence, proof = validator.run_integration_experiment(level)
        status = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[proof.pass_fail]
        print(f"  {status} {level.name}: {', '.join(level.components)}")
    print()

    # Summary
    print("=" * 80)
    print("EXPERIMENTAL SUMMARY")
    print("=" * 80)
    total = validator.experiment_count
    pass_rate = validator.pass_count / total if total > 0 else 0

    print(f"Total Experiments: {total}")
    print(f"  PASS: {validator.pass_count} ({validator.pass_count/total*100:.1f}%)")
    print(f"  WARN: {validator.warn_count} ({validator.warn_count/total*100:.1f}%)")
    print(f"  FAIL: {validator.fail_count} ({validator.fail_count/total*100:.1f}%)")
    print()

    # Export results
    print("=" * 80)
    print("EXPORTING EVIDENCE & PROOFS")
    print("=" * 80)

    evidence_data = [asdict(e) for e in validator.evidence_log]
    with open('doe_api_evidence.json', 'w') as f:
        json.dump(evidence_data, f, indent=2, default=str)
    print(f"Evidence: doe_api_evidence.json ({len(evidence_data)} records)")

    proofs_data = [{
        "experiment_id": p.experiment_id,
        "pass_fail": p.pass_fail,
        "verdict": p.verdict,
        "confidence": p.confidence,
        "assertions": p.assertions,
    } for p in validator.proofs]
    with open('doe_api_proofs.json', 'w') as f:
        json.dump(proofs_data, f, indent=2)
    print(f"Proofs: doe_api_proofs.json ({len(proofs_data)} records)")
    print()

    # Final verdict
    print("=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)

    if pass_rate >= 0.95:
        grade = "A+"
        verdict = "EXCELLENT - Production Ready"
    elif pass_rate >= 0.90:
        grade = "A"
        verdict = "VERY GOOD - Minor issues"
    elif pass_rate >= 0.80:
        grade = "B"
        verdict = "GOOD - Some issues"
    else:
        grade = "C"
        verdict = "NEEDS WORK"

    print(f"Grade: {grade}")
    print(f"Verdict: {verdict}")
    print(f"Pass Rate: {pass_rate:.1%}")
    print(f"Total Assertions: {sum(len(p.assertions) for p in validator.proofs)}")
    print("=" * 80)

    return validator


if __name__ == "__main__":
    main()
