# RSCT Taxonomy Landscape: A Fresh Perspective for Swarm It

**Date:** 2026-02-24
**Purpose:** Synthesize the multiple taxonomy systems in yrsn into a coherent view for swarm-it SDK integration

---

## Executive Summary

The yrsn codebase contains **five distinct but overlapping taxonomies** for classifying AI system failures. This document maps their relationships and recommends which elements swarm-it should expose.

**Key Finding:** The taxonomies serve different purposes (detection vs. enforcement vs. compliance) but share a common foundation in the RSCT certificate space (α, κ, σ). Swarm-it should unify these into a **single user-facing API** while preserving the underlying richness.

---

## 1. Taxonomy Inventory

### 1.1 RSCT 16-Mode Collapse Taxonomy (Primary)
**Source:** `collapse_classifier.py`

The canonical taxonomy from the SOTA paper. Organized by **where the failure is caught** (which gate) and **what to do about it** (remediation).

| Group | Modes | Trigger | Gate |
|-------|-------|---------|------|
| **1. Encoding** | 1.1-1.4 | N ≥ 0.5, S ≫ R, dim fracture, format mismatch | Gate 1 |
| **2. Dynamics** | 2.1-2.4 | σ > σ_thr, gradient starvation, Oobleck jam, substrate degradation | Gate 2/3 |
| **3. Semantic** | 3.1-3.4 | High κ + low R (hallucination), c < c_min (conflict), reward hacking, OOD | Gate 2/4 |
| **4. Execution** | 4.1-4.4 | Weakest link, cross-modal desync, stalled navigation, gatekeeper bypass | Gate 3/4 |

**Remediations:** REJECT, BLOCK, RE_ENCODE, REPAIR, PROCEED, ESCALATE

---

### 1.2 Extended 40-Type Degradation Taxonomy
**Source:** `degradation_taxonomy.py`

Expands the 16 modes with **domain-specific degradations** for Context Quality ISA (CQ-ISA) compliance.

| Domain | Types | Examples |
|--------|-------|----------|
| Original 16 | 16 | HALLUCINATION, POISONING, RSN_COLLAPSE, etc. |
| Context | 7 | QUERY_MISMATCH, CONTEXT_FRAGMENTATION, INFORMATION_LOSS |
| Temporal | 5 | RECENCY_BIAS, CONCEPT_DRIFT, PREDICTION_STALENESS |
| Adversarial | 4 | PROMPT_INJECTION, JAILBREAK_ATTEMPT, BACKDOOR_TRIGGER |
| Hardware | 4 | MEMORY_CORRUPTION, QUANTIZATION_ERROR, THERMAL_THROTTLING |
| Statistical | 4 | OUTLIER_CONTAMINATION, BIAS_AMPLIFICATION, VARIANCE_INFLATION |

**Metadata per type:** Geometric domain (COMPRESSION/NEUTRAL/EXPANSION), severity, theta signature, enforcement action.

---

### 1.3 Four-Tier Constraint Taxonomy
**Source:** `constraint_taxonomy.py`

Classifies constraints by **how permanent they are** (curriculum-learning inspired).

| Tier | Behavior | Violation | Memristor Model |
|------|----------|-----------|-----------------|
| **ACTUAL** | Permanent, never forgets | FATAL | Threshold Adaptive |
| **CONSOLIDATED** | Long-term, validated | CRITICAL | Bounded Drift |
| **LEARNED** | Medium-term, being reinforced | WARNING | Linear Ion Drift |
| **EMERGENT** | Short-term, new discoveries | ADVISORY | Nonlinear Ion Drift |

**Tier transitions:** CRYSTALLIZE (emergent→learned), HARDEN (learned→actual), DECAY (learned→emergent), SOFTEN (actual→learned).

---

### 1.4 Hardware Failure Taxonomy
**Source:** `failure_taxonomy.py`

Maps **CrossSim hardware mechanisms** to YRSN failure types. Specific to neuromorphic/analog compute.

| Mechanism | YRSN Labels | R/S/N Signature |
|-----------|-------------|-----------------|
| ADC/DAC quantization | HALLUCINATION, DISTRACTION | R↓, N↑ |
| Read noise | HALLUCINATION, INSTABILITY | R↓, N↑↑ |
| Programming error | POISONING, SHIFT | R↓, S↓, N↑ |
| Conductance drift | HALLUCINATION, DECAY, PHASE_TRANSITION | R↓ over time |
| Nonlinearities | HALLUCINATION, MISCALIBRATION | High confidence + low R |
| Parasitics/crosstalk | DISTRACTION, POISONING | S↑, N↑ |

---

### 1.5 Context Integrity Failure Codes (ISA-Style)
**Source:** `Gap-6-taxonomy.md`

Hardware-oriented **error codes** for a hypothetical CQC coprocessor.

| Category | Codes | Topological Trigger |
|----------|-------|---------------------|
| **100: Connectivity** | E101 Genus Collapse, E102 Genus Overflow, E103 Handle Discontinuity | Handlebody structure violations |
| **200: Geodesic Drift** | E201 Phase Slip, E202 Torus Break | Distance from baseline exceeds threshold |
| **300: Invariant Violations** | E301 Simplex Violation, E302 Coherence Drop | R+S+N ≠ 1, κ < floor |

---

## 2. Taxonomy Relationships

```
                    ┌─────────────────────────────────────┐
                    │   RSCT Certificate Space            │
                    │   (α, κ_gate, σ, R, S, N, c)        │
                    └─────────────┬───────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ 16-Mode RSCT  │       │ 40-Type         │       │ 4-Tier          │
│ (WHERE caught)│       │ Degradation     │       │ Constraint      │
│               │       │ (WHAT happened) │       │ (HOW permanent) │
└───────┬───────┘       └────────┬────────┘       └────────┬────────┘
        │                        │                         │
        │ ┌──────────────────────┘                         │
        │ │                                                │
        ▼ ▼                                                ▼
┌───────────────┐                                 ┌─────────────────┐
│ Hardware      │                                 │ ISA Error       │
│ Failure       │                                 │ Codes           │
│ (substrate)   │                                 │ (E1xx, E2xx...) │
└───────────────┘                                 └─────────────────┘
```

### Key Insight: Same Signal, Different Lenses

All taxonomies derive from the same underlying signals but answer different questions:

| Taxonomy | Question Answered |
|----------|-------------------|
| 16-Mode RSCT | "Which gate catches this, and what action is needed?" |
| 40-Type Degradation | "What specific failure pattern is this?" |
| 4-Tier Constraint | "How seriously should we treat this violation?" |
| Hardware Failure | "What physical mechanism caused this?" |
| ISA Error Codes | "What machine-readable code represents this?" |

---

## 3. Recommendations for Swarm It SDK

### 3.1 Expose: Unified Classification API

Create a single `classify()` method that returns all relevant taxonomies:

```python
from swarm_it import SwarmIt

swarm = SwarmIt()
cert = swarm.certify("What is the capital of France?")

# Primary: 16-mode RSCT
cert.rsct_mode           # "3.1"
cert.rsct_group          # "SEMANTIC"
cert.rsct_remediation    # "REPAIR"

# Extended: 40-type degradation
cert.degradation_type    # "HALLUCINATION"
cert.degradation_domain  # "EXPANSION"

# Severity: 4-tier
cert.constraint_tier     # "LEARNED"
cert.severity            # "WARNING"

# Machine-readable
cert.error_code          # "E302" (if applicable)
```

### 3.2 Expose: Detectors (for Multi-Agent)

The specialized detectors are critical for swarm monitoring:

```python
from swarm_it.detectors import (
    GradientStarvationDetector,  # Mode 2.2
    RewardHackingDetector,       # Mode 3.3
    GatekeeperBypassDetector,    # Mode 4.4
)

# Track agent learning progress
detector = GradientStarvationDetector(window_size=10)
for step in agent_steps:
    detector.update(loss=step.loss, grad_norm=step.grad_norm)
    is_starved, reason = detector.is_starved()
```

### 3.3 Expose: Tier Transitions (for Governance)

Constraint tier evolution is valuable for compliance dashboards:

```python
from swarm_it.governance import TierTransitionDetector

detector = TierTransitionDetector()

# Record signals over time
detector.record_signal("budget_limit", value=0.8)

# Check for tier promotion/demotion
event = detector.check_transition(constraint)
if event:
    print(f"Tier changed: {event.transition_type}")  # CRYSTALLIZE, HARDEN, DECAY
```

### 3.4 Hide: Hardware-Specific Details

The CrossSim/neuromorphic taxonomy is **too specialized** for the SDK. Keep it internal to yrsn for specialized deployments.

### 3.5 Hide: ISA Error Codes (for Now)

The E1xx/E2xx codes are designed for hardware coprocessors. Don't expose until there's a CQC chip product.

---

## 4. Proposed SDK Type Hierarchy

```python
# swarm_it/taxonomy.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional

class RSCTGroup(Enum):
    """Four collapse groups from RSCT paper."""
    ENCODING = 1       # α < α_min or N > ηR
    DYNAMICS = 2       # σ > σ_thr or ΔV_t4 > 0
    SEMANTIC = 3       # high κ_gate, low c or κ_A
    EXECUTION = 4      # κ_gate = min(κ_i) < κ_req

class RSCTRemediation(Enum):
    """Remediation actions from RSCT Algorithm 1."""
    PROCEED = "PROCEED"
    PROCEED_CAUTIOUS = "PROCEED_CAUTIOUS"
    REJECT = "REJECT"
    BLOCK = "BLOCK"
    RE_ENCODE = "RE_ENCODE"
    REPAIR = "REPAIR"
    HALT = "HALT"
    TIMEOUT = "TIMEOUT"
    ESCALATE = "ESCALATE"

class DegradationDomain(Enum):
    """Geometric domain from degradation taxonomy."""
    COMPRESSION = "COMPRESSION"
    NEUTRAL = "NEUTRAL"
    EXPANSION = "EXPANSION"

class Severity(Enum):
    """Four-tier severity levels."""
    TRACE = "TRACE"       # Emergent tier
    MINOR = "MINOR"       # Emergent/Learned
    WARNING = "WARNING"   # Learned
    CRITICAL = "CRITICAL" # Consolidated
    FATAL = "FATAL"       # Actual

@dataclass
class TaxonomyClassification:
    """Unified taxonomy classification for a certificate."""

    # 16-Mode RSCT
    rsct_mode: str                    # "1.1", "3.1", etc.
    rsct_group: RSCTGroup
    rsct_gate: Optional[str]          # "Gate1", "Gate2", etc.
    rsct_remediation: RSCTRemediation
    rsct_trigger: str                 # Human-readable trigger

    # 40-Type Degradation
    degradation_type: str             # "HALLUCINATION", etc.
    degradation_domain: DegradationDomain
    theta_signature: Optional[float]  # If available

    # 4-Tier Severity
    severity: Severity
    enforcement_action: str           # "LOG", "WARN", "BLOCK", "ESCALATE"

    # Confidence
    confidence: float                 # 0-1

    def to_dict(self) -> dict:
        return {
            "rsct": {
                "mode": self.rsct_mode,
                "group": self.rsct_group.name,
                "gate": self.rsct_gate,
                "remediation": self.rsct_remediation.value,
                "trigger": self.rsct_trigger,
            },
            "degradation": {
                "type": self.degradation_type,
                "domain": self.degradation_domain.value,
                "theta": self.theta_signature,
            },
            "severity": {
                "level": self.severity.value,
                "action": self.enforcement_action,
            },
            "confidence": self.confidence,
        }
```

---

## 5. Mode Names Reference (All 16)

For documentation and user-facing output:

| Mode | Name | One-Liner |
|------|------|-----------|
| 1.1 | Noise Saturation | N ≥ 0.5, encoding is garbage |
| 1.2 | Superfluous Drowning | S ≫ R, signal lost in fluff |
| 1.3 | Dimensional Fracture | Embedding space too small for rotor |
| 1.4 | Format Mismatch | Output doesn't match expected schema |
| 2.1 | Trajectory Divergence | σ > 0.7, solver is unstable |
| 2.2 | Gradient Starvation | Learning has stalled |
| 2.3 | Oobleck Jamming | Turbulence spike (σ_max > 2×σ_mean) |
| 2.4 | Substrate Degradation | Hardware is physically damaged |
| 3.1 | Fluent Hallucination | High κ, low R — confident but wrong |
| 3.2 | Phasor Conflict | c < 0.4, agents disagree |
| 3.3 | Reward Hacking | Optimizing proxy, not objective |
| 3.4 | OOD Fabrication | Out-of-distribution extrapolation |
| 4.1 | Weakest-Link Cascade | min(κ_i) pulls down whole system |
| 4.2 | Cross-Modal Desync | κ_interface < 0.3, modalities misaligned |
| 4.3 | Stalled Navigation | Reasoning loop detected |
| 4.4 | Gatekeeper Bypass | Adversarial manipulation of certificates |

---

## 6. For Multi-Agent Swarms: Mode 3.2 and 4.x Matter Most

When agents coordinate, these modes dominate:

| Mode | Swarm Relevance |
|------|-----------------|
| **3.2 Phasor Conflict** | Agents have incompatible outputs (c < 0.4) |
| **4.1 Weakest-Link Cascade** | One bad agent tanks the whole swarm |
| **4.2 Cross-Modal Desync** | Interface between agents breaks down |
| **4.3 Stalled Navigation** | Swarm stuck in a loop |

**Swarm-specific certificate fields:**
- `consensus`: Phasor coherence across all agents
- `kappa_interface_min`: Weakest agent-to-agent link
- `weakest_agent_id`: Which agent is dragging down κ_gate

---

## 7. Implementation Priority

| Priority | Component | Reason |
|----------|-----------|--------|
| P0 | 16-mode classification (`classify_rsct`) | Core paper taxonomy |
| P0 | Mode names and descriptions | User-facing output |
| P1 | Severity mapping | Enforcement decisions |
| P1 | Remediation enum | Actionable SDK response |
| P2 | Detectors (starvation, hacking, bypass) | Multi-agent monitoring |
| P2 | Tier transitions | Governance dashboards |
| P3 | 40-type degradation | Extended diagnostics |
| P3 | Theta signatures | Advanced users only |

---

## 8. Open Questions

1. **Should the SDK compute theta?** Theta requires the rotor embedding, which isn't available in API-only mode.

2. **Should tier transitions be automatic?** Or should they require explicit governance approval?

3. **How granular should error codes be?** E101/E102/E103 are useful for hardware, but may confuse SDK users.

4. **Should we expose degradation_taxonomy.py's 40 types?** Or stick with the 16-mode canonical set?

---

## Appendix: File Locations in yrsn

| Taxonomy | Path |
|----------|------|
| 16-Mode RSCT | `src/yrsn/core/decomposition/collapse_classifier.py` |
| 40-Type Degradation | `src/yrsn/core/decomposition/degradation_taxonomy.py` |
| 4-Tier Constraint | `src/yrsn/core/decomposition/constraint_taxonomy.py` |
| Hardware Failure | `src/yrsn/benchmarks/failure_taxonomy.py` |
| ISA Error Codes | `docs/production/Gap-6-taxonomy.md` |
| SOTA Paper Table | `docs/primary/SOTA_Intelligence...tex` (Table 3) |
