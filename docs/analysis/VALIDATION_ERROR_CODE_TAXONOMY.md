# Swarm It: Unified Validation Error Code Taxonomy

**Date:** 2026-02-24
**Purpose:** Unify pre-execution (RSCT modes) and post-execution (Type I-VI) validation into a single error code system
**Sources:**
- yrsn `collapse_classifier.py` — 16-mode RSCT taxonomy
- yrsn `llm_validation/type_*_detector.py` — Type I-VI hallucination detectors
- yrsn `Gap-6-taxonomy.md` — ISA-style error codes

---

## Executive Summary

RSCT provides **pre-execution gating** (prevent bad inputs from running). Type I-VI provides **post-execution validation** (detect bad outputs after running). Both are needed for a complete governance system.

This document proposes a **unified error code taxonomy** that:
1. Maps pre-execution modes to post-execution types
2. Assigns machine-readable codes
3. Defines feedback loops for threshold tuning

---

## 1. The Dual Validation Model

```
                    INPUT
                      │
                      ▼
        ┌─────────────────────────┐
        │   PRE-EXECUTION GATES   │
        │   (RSCT Modes 1.x-4.x)  │
        │                         │
        │   R + S + N = 1?        │
        │   N < 0.5?              │
        │   κ ≥ κ_req(σ)?         │
        └───────────┬─────────────┘
                    │
            ┌───────┴───────┐
            │               │
         REJECT          EXECUTE
            │               │
            ▼               ▼
        [BLOCKED]    ┌─────────────────────────┐
                     │   SOLVER (LLM/Agent)    │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │  POST-EXECUTION VALID.  │
                     │  (Type I-VI Detectors)  │
                     │                         │
                     │  Groundedness? (I)      │
                     │  Contradiction? (II)    │
                     │  Inversion? (III)       │
                     │  Drift? (IV)            │
                     │  Reasoning? (V)         │
                     │  Domain? (VI)           │
                     └───────────┬─────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                 VALID                    INVALID
                    │                         │
                    ▼                         ▼
               [OUTPUT]               [FLAG + FEEDBACK]
                                             │
                                             ▼
                               ┌─────────────────────────┐
                               │   CALIBRATION FEEDBACK  │
                               │   (Tighten Pre-Gates)   │
                               └─────────────────────────┘
```

---

## 2. Type I-VI Validation Summary

| Type | Name | What It Catches | Detection Method | RSCT Mapping |
|------|------|-----------------|------------------|--------------|
| **I** | Groundedness | Claims not supported by evidence | Subspace projection leakage | R proxy, N proxy |
| **II** | Contradiction | Claims that conflict with evidence | NLI cross-encoder + Gram-Schmidt | Mode 3.1 (Hallucination) |
| **III** | Inversion | Role/entity swaps (A did X to B → B did X to A) | Inversion vs negation subspace | Compliance-critical |
| **IV** | Drift | Same topic, wrong relationship | Bivector plane alignment | Mode 3.4 (OOD) |
| **V** | Reasoning | Multi-step reasoning failures | Cayley steering + trivector | σ (turbulence) |
| **VI** | Domain | Correct answer, wrong domain | QR domain subspace support | ω (OOD), Mode 3.4 |

---

## 3. Unified Error Code Schema

### Code Structure

```
V{gate}.{type}.{subtype}

Where:
  - V = Validation (distinguishes from RSCT M codes)
  - gate = 0 (pre), 1-4 (RSCT gates), 5 (post-execution)
  - type = Roman numeral I-VI or RSCT mode 1-4
  - subtype = Specific failure within type
```

### Pre-Execution Codes (RSCT Gates)

| Code | Name | Trigger | Action |
|------|------|---------|--------|
| **V1.1.1** | Noise Saturation | N ≥ 0.5 | REJECT |
| **V1.1.2** | Superfluous Drowning | S ≫ R | RE_ENCODE |
| **V1.1.3** | Dimensional Fracture | dim < 50 × stable_rank | REJECT |
| **V1.1.4** | Format Mismatch | Output schema invalid | REJECT |
| **V2.2.1** | Trajectory Divergence | σ > 0.7 | BLOCK |
| **V2.2.2** | Gradient Starvation | Loss stagnant | BLOCK |
| **V2.2.3** | Oobleck Jamming | σ_max > 2×σ_mean | BLOCK |
| **V2.2.4** | Substrate Degradation | Hardware damage | HALT |
| **V3.3.1** | Fluent Hallucination | High κ, low R | REPAIR |
| **V3.3.2** | Phasor Conflict | c < 0.4 | BLOCK |
| **V3.3.3** | Reward Hacking | Metric ↑, objective ↓ | BLOCK |
| **V3.3.4** | OOD Fabrication | Low ω | RE_ENCODE |
| **V4.4.1** | Weakest-Link Cascade | min(κ_i) < threshold | RE_ENCODE |
| **V4.4.2** | Cross-Modal Desync | κ_interface < 0.3 | REPAIR |
| **V4.4.3** | Stalled Navigation | Loop detected | TIMEOUT |
| **V4.4.4** | Gatekeeper Bypass | Certificate manipulation | ESCALATE |

### Post-Execution Codes (Type I-VI)

| Code | Name | Trigger | Feedback Action |
|------|------|---------|-----------------|
| **V5.I.1** | Unsupported Claim | leakage > 0.5 | Tighten N threshold |
| **V5.I.2** | Weak Grounding | support < 0.5 | Tighten R threshold |
| **V5.II.1** | Direct Contradiction | NLI score > 0.3 | Tighten κ_L |
| **V5.II.2** | Implicit Contradiction | NLI score 0.2-0.3 | Log + monitor |
| **V5.III.1** | Role Inversion | Inversion subspace match | Flag audit, tighten c |
| **V5.III.2** | Entity Swap | Agent A ↔ Agent B | Flag audit |
| **V5.IV.1** | Topic Drift | plane_cos < 0.7 | Tighten σ_thr |
| **V5.IV.2** | Relationship Loss | Same entities, wrong relation | Tighten κ_A |
| **V5.V.1** | Context Ignoring | τ < 0.05 | Tighten σ_thr |
| **V5.V.2** | Erratic Trajectory | trivector > 0.9 | Flag Mode 2.1 |
| **V5.V.3** | Cumulative Drift | rejection increases | Monitor + log |
| **V5.VI.1** | Domain Mismatch | wrong_domain_support > expected | Tighten ω, add domain bases |
| **V5.VI.2** | Cross-Domain Leak | Multi-domain support | Log for review |

---

## 4. Cross-Reference Matrix

### Type → RSCT Mode Mapping

| Post-Execution Type | Primary RSCT Mode | Feedback Target |
|---------------------|-------------------|-----------------|
| Type I (Groundedness) | 1.1 (Noise Saturation) | Gate 1: N threshold |
| Type II (Contradiction) | 3.1 (Fluent Hallucination) | Gate 4: κ_L |
| Type III (Inversion) | 3.2 (Phasor Conflict) | Gate 2: c threshold |
| Type IV (Drift) | 3.4 (OOD Fabrication) | Gate 3: σ_thr |
| Type V (Reasoning) | 2.1 (Trajectory Divergence) | σ_thr, loop detection |
| Type VI (Domain) | 3.4 (OOD Fabrication) | ω threshold, domain bases |

### ISA Error Code Mapping

| ISA Code | Meaning | Unified Code |
|----------|---------|--------------|
| E101 | Genus Collapse | V1.1.3 (Dimensional Fracture) |
| E102 | Genus Overflow | V1.1.1 (Noise Saturation) |
| E103 | Handle Discontinuity | V1.1.4 (Format Mismatch) |
| E201 | Phase Slip | V5.IV.1 (Topic Drift) |
| E202 | Torus Break | V4.4.1 (Weakest-Link) |
| E301 | Simplex Violation | V0.0.1 (R+S+N ≠ 1) |
| E302 | Coherence Drop | V3.3.2 (Phasor Conflict) |

---

## 5. Feedback Loop Implementation

When post-execution validation fails, feed back to tighten pre-execution gates:

```python
class ValidationFeedbackLoop:
    """
    Calibrate RSCT thresholds based on Type I-VI detection rates.
    """

    def __init__(self, gatekeeper):
        self.gatekeeper = gatekeeper
        self.type_counts = {f"type_{i}": 0 for i in ["I", "II", "III", "IV", "V", "VI"]}
        self.window_size = 100
        self.history = []

    def record_validation(self, validation_result: dict):
        """Record post-execution validation result."""
        self.history.append(validation_result)
        if len(self.history) > self.window_size:
            self.history.pop(0)

        # Count failures by type
        for vtype in self.type_counts:
            if validation_result.get(vtype, False):
                self.type_counts[vtype] += 1

    def compute_adjustments(self) -> dict:
        """Compute threshold adjustments based on failure rates."""
        n = len(self.history)
        if n < 10:
            return {}  # Not enough data

        adjustments = {}

        # Type I high → Tighten N threshold
        type_i_rate = self.type_counts["type_I"] / n
        if type_i_rate > 0.1:
            adjustments["N_threshold"] = -0.05  # Reduce threshold

        # Type II high → Tighten κ_L threshold
        type_ii_rate = self.type_counts["type_II"] / n
        if type_ii_rate > 0.05:
            adjustments["kappa_L_threshold"] = +0.05  # Increase threshold

        # Type V high → Tighten σ_thr
        type_v_rate = self.type_counts["type_V"] / n
        if type_v_rate > 0.1:
            adjustments["sigma_thr"] = -0.05  # Lower turbulence tolerance

        # Type VI high → Tighten ω threshold
        type_vi_rate = self.type_counts["type_VI"] / n
        if type_vi_rate > 0.1:
            adjustments["omega_threshold"] = +0.05

        return adjustments

    def apply_adjustments(self):
        """Apply computed adjustments to gatekeeper."""
        adjustments = self.compute_adjustments()
        for param, delta in adjustments.items():
            current = getattr(self.gatekeeper, param)
            setattr(self.gatekeeper, param, current + delta)
            print(f"Adjusted {param}: {current:.3f} → {current + delta:.3f}")
```

---

## 6. SDK Integration Proposal

### Certificate Extension

```python
@dataclass
class Certificate:
    # ... existing fields ...

    # Pre-execution (RSCT)
    rsct_mode: str              # "1.1", "3.1", etc.
    rsct_gate: Optional[str]
    rsct_remediation: str

    # Post-execution (Type I-VI)
    post_validation: Optional[PostValidationResult]

@dataclass
class PostValidationResult:
    """Results from Type I-VI validation."""

    # Type I: Groundedness
    type_i_score: float         # Leakage [0-1]
    type_i_unsupported: bool

    # Type II: Contradiction
    type_ii_score: float        # NLI contradiction [0-1]
    type_ii_contradicts: bool
    type_ii_context: Optional[str]  # Which evidence it contradicts

    # Type III: Inversion
    type_iii_score: float
    type_iii_is_inversion: bool
    type_iii_entities: Optional[Tuple[str, str]]  # Swapped entities

    # Type IV: Drift
    type_iv_score: float        # Plane misalignment [0-1]
    type_iv_drifted: bool

    # Type V: Reasoning
    type_v_score: float         # Aggregate reasoning score
    type_v_vibing: bool         # Context ignored?
    type_v_trajectory_jump: bool

    # Type VI: Domain
    type_vi_score: float        # Domain mismatch [0-1]
    type_vi_wrong_domain: Optional[str]
    type_vi_expected_domain: str

    # Unified error codes
    error_codes: List[str]      # ["V5.II.1", "V5.IV.1"]
```

### Detector Bundle

```python
from swarm_it.validation import (
    TypeIGroundednessDetector,
    TypeIIContradictionDetector,
    TypeIIIInversionDetector,
    TypeIVDriftDetector,
    TypeVReasoningDetector,
    TypeVIDomainDetector,
    ValidationBundle,
)

# Create unified validator
validator = ValidationBundle(
    embed_fn=sentence_transformer_embed,
    nli_model=nli_cross_encoder,
    domains={"sr117_mrm": sr117_exemplars, "general_ml": ml_exemplars},
)

# Validate output
result = validator.validate(
    context=["Revenue grew 15% in Q3"],
    output="Revenue declined 15% in Q3",
    expected_domain="financial_reporting",
)

# Check for errors
if result.has_errors:
    print(f"Error codes: {result.error_codes}")  # ["V5.II.1"]
```

---

## 7. Swarm-Specific Considerations

For multi-agent swarms, add **cross-agent validation**:

| Code | Name | What It Catches |
|------|------|-----------------|
| **V6.A.1** | Agent Output Contradiction | Agent A contradicts Agent B |
| **V6.A.2** | Agent Role Inversion | Agents swap responsibilities |
| **V6.A.3** | Consensus Breakdown | c < 0.4 across agents |
| **V6.A.4** | Cascade Failure | One agent's Type V causes others to fail |

---

## 8. Implementation Priority

| Priority | Component | Reason |
|----------|-----------|--------|
| P0 | Unified error code schema | Foundation for all reporting |
| P0 | Type I + II detectors | Most common hallucination types |
| P1 | Type V detector | Critical for multi-step reasoning |
| P1 | Feedback loop | Adaptive threshold tuning |
| P2 | Type III detector | Compliance (SR 11-7) |
| P2 | Type VI detector | Domain-specific applications |
| P3 | Cross-agent validation | Swarm-specific |

---

## 9. Open Questions

1. **Should Type I-VI run on every output?** Or only when RSCT mode suggests risk (e.g., Mode 3.1)?

2. **How to handle conflicting signals?** Pre-gate passes but post-validation fails → what threshold to adjust?

3. **Type III (Inversion) calibration:** Requires domain-specific inversion examples. Who provides these?

4. **Latency budget:** Type II (NLI) and Type VI (QR) are expensive. What's the SLA?

---

## Appendix A: Type I-VI Source Files

| Type | File | Key Class |
|------|------|-----------|
| I | `type_i_detector.py` | `TypeIGroundednessDetector` |
| II | `type_ii_detector.py` | `TypeIIContradictionDetector` |
| III | `type_iii_detector.py` | `TypeIIIInversionDetector` |
| IV | `type_iv_detector.py` | `TypeIVDetector` |
| V | `type_v_detector.py` | `TypeVReasoningDetector` |
| VI | `type_vi_detector.py` | `TypeVIDetector` |

All in: `/Users/rudy/GitHub/yrsn/src/yrsn/core/geometric/llm_validation/`

---

## Appendix B: Example Error Report

```json
{
  "certificate_id": "cert-12345",
  "timestamp": "2026-02-24T15:30:00Z",

  "pre_execution": {
    "rsct_mode": "0.0",
    "gate_reached": 5,
    "decision": "EXECUTE",
    "R": 0.65,
    "S": 0.20,
    "N": 0.15,
    "kappa_gate": 0.72,
    "sigma": 0.28
  },

  "post_execution": {
    "ran": true,
    "output": "Revenue declined 15% in Q3...",

    "type_i": {"score": 0.12, "unsupported": false},
    "type_ii": {"score": 0.85, "contradicts": true, "context": "Revenue grew 15%..."},
    "type_iii": {"score": 0.05, "is_inversion": false},
    "type_iv": {"score": 0.22, "drifted": false},
    "type_v": {"score": 0.18, "vibing": false, "trajectory_jump": false},
    "type_vi": {"score": 0.08, "wrong_domain": null},

    "error_codes": ["V5.II.1"],
    "severity": "CRITICAL",
    "action": "FLAG_FOR_REVIEW"
  },

  "feedback": {
    "recommendation": "Tighten kappa_L by 0.05",
    "applied": false,
    "reason": "Pending human approval"
  }
}
```
