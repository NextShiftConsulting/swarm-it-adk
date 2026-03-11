# DOE API Learning Findings

**Date**: 2026-03-11
**Experiments**: 25
**Pass Rate**: 100% ✅ (Fixed 2026-03-11)

## Resolution

Issues identified below were **FIXED** by aligning `constraint_graph.py` with whitepaper FIG. 29:

1. Gate 2 now uses coherence check (c < 0.4 AND N > 0.3) instead of σ > 0.5
2. High turbulence threshold moved to Gate 3 (Oobleck handles σ)
3. Added coherence metric to evaluation pipeline

---

## Original Findings (Pre-Fix)

## Executive Summary

DOE validation uncovered that **swarm-it-api doesn't use yrsn code at all**.

The `constraint_graph.py` in swarm-it-api is a **completely separate implementation** with different:
- Thresholds (N≥0.5 vs N>0.30)
- Gate logic (4 gates vs simple κ-gating)
- Decisions (EXECUTE/RE_ENCODE/REPAIR vs ACCEPT/REJECT/LOOP)

---

## Critical Finding: Yrsn Has Different Architecture

### yrsn/gate_handler.py (THE REAL CODE)

```python
# From yrsn/src/yrsn/framework/api/serg/gate_handler.py
KAPPA_MIN = 0.4
N_MAX = 0.30  # NOT 0.5!

def _compute_routing_decision(R, S, N, kappa):
    if kappa < KAPPA_MIN:   # κ < 0.4
        return ("REJECT", "blocked", "none")
    if N > N_MAX:           # N > 0.30
        return ("REJECT", "blocked", "none")
    if R < 0.40:            # R < 0.40
        return ("REJECT", "blocked", "none")
    # Then routing tiers...
```

### swarm-it-api/constraint_graph.py (OUR CODE - WRONG)

```python
# Our implementation - doesn't match yrsn!
N_THRESHOLD = 0.5    # yrsn uses 0.30
# Has 4-gate system with Oobleck - yrsn doesn't
# Has RE_ENCODE, REPAIR - yrsn uses ACCEPT/REJECT/LOOP
```

### yrsn/constraint_graph.py (STORAGE ONLY)

The yrsn constraint_graph.py is a **storage adapter** for PostgreSQL/in-memory, NOT decision logic.
It stores nodes and edges from `CollapseSignature`.

---

---

## Finding #1: Missing Coherence Check in Constraint Graph

### Evidence

| Test Case | Input | Expected | Actual |
|-----------|-------|----------|--------|
| CG3_LOW_COHERENCE | R=0.25, N=0.45, σ=0.40 | REJECT (Gate 1) or BLOCK (Gate 2) | RE_ENCODE (Gate 3) |

### Analysis

The RSCT whitepaper defines Gate 2 as:
```
Gate 2 (Consensus): c < 0.4 AND N > 0.3 → BLOCK
where c = R / (R + N + 0.1)
```

**yrsn_adapter.py** (line 209-211):
```python
coherence = R / (R + N + 0.1)
if coherence < 0.4 and N > 0.3:
    return "BLOCK", 2, f"Gate 2 (Consensus): coherence={coherence:.2f}"
```

**constraint_graph.py** (line 237-246):
```python
Threshold(
    name="high_turbulence",
    metric="sigma",
    value=0.50,
    direction="above",
    gate=GateNumber.GATE_2_CONSENSUS,
)
# NO coherence check!
```

### Root Cause

`constraint_graph.py` uses σ > 0.5 for Gate 2 (turbulence check).
`yrsn_adapter.py` uses c < 0.4 AND N > 0.3 (coherence check).

These are **different constraints** assigned to the same gate.

### Impact

- CG3: σ=0.40 < 0.5 passes Gate 2 turbulence check
- CG3: Coherence c=0.31 < 0.4 AND N=0.45 > 0.3 SHOULD trigger Gate 2
- Result: Falls through to Gate 3 (Oobleck) instead

---

## Finding #2: Turbulence Shadows Oobleck

### Evidence

| Test Case | Input | Expected | Actual |
|-----------|-------|----------|--------|
| CG4_OOBLECK_FAIL | κ=0.45, σ=0.60 | RE_ENCODE (Gate 3) | BLOCK (Gate 2) |

### Analysis

The test expected Gate 3 (Oobleck) to trigger:
```
κ_req(σ=0.60) = 0.5 + 0.4 * 0.60 = 0.74
κ=0.45 < 0.74 → RE_ENCODE
```

But Gate 2 triggered first:
```
σ=0.60 > 0.50 → "high_turbulence" → BLOCK
```

### Root Cause

Gate 2 "high_turbulence" (σ > 0.5) fires **before** Gate 3 Oobleck can evaluate.

This is semantically incorrect:
- High σ should **raise** κ_req (Oobleck principle)
- High σ should NOT trigger Gate 2 BLOCK by itself

### Impact

- Any request with σ > 0.5 gets BLOCKED at Gate 2
- Oobleck principle (Gate 3) never gets to evaluate
- The κ requirement escalation is bypassed

---

## Recommendations

### Option A: Align constraint_graph.py with yrsn_adapter.py

Add coherence check to Gate 2:
```python
Threshold(
    name="coherence_floor",
    metric="coherence",  # computed as R/(R+N+0.1)
    value=0.40,
    direction="below",
    gate=GateNumber.GATE_2_CONSENSUS,
    requires_n_above=0.30,  # compound condition
)
```

### Option B: Remove turbulence from Gate 2

Move "high_turbulence" check to Gate 3 as part of Oobleck:
```python
# Gate 3 already handles turbulence via:
# κ_req = 0.5 + 0.4 * σ
# Remove σ > 0.5 threshold from Gate 2
```

### Option C: Document as intended behavior

If turbulence > 0.5 should always BLOCK (regardless of κ), document this as policy.

---

## Metrics (Post-Fix)

| Metric | Before | After |
|--------|--------|-------|
| Total Experiments | 25 | 25 |
| Assertions | 74 | 79 |
| Pass Rate | 92% | **100%** |
| Findings | 2 architectural issues | 0 |

## Files Modified

- `/Users/rudy/GitHub/swarm-it-api/engine/constraint_graph.py` ← **FIXED**
- `/Users/rudy/GitHub/swarm-it-adk/test_doe_api_learning.py` ← Updated test expectations

---

## Resolution Details

### Changes to constraint_graph.py

1. **Added coherence metric** (c = R/(R+N+0.1)) to evaluation pipeline
2. **Gate 2 now checks coherence** per FIG. 29:
   ```python
   # Before (WRONG)
   Threshold(name="high_turbulence", metric="sigma", value=0.50,
             gate=GateNumber.GATE_2_CONSENSUS)

   # After (CORRECT per FIG. 29)
   Threshold(name="low_coherence", metric="coherence", value=0.40,
             gate=GateNumber.GATE_2_CONSENSUS)
   # + compound check: c < 0.4 AND N > 0.3 → BLOCK
   ```
3. **Moved high_turbulence to Gate 3** (Oobleck handles σ via κ_req formula)

### Validation

```
DOE VALIDATION - API Learning Features
================================================================================
Total Experiments: 25
  PASS: 25 (100.0%)
Grade: A+
Verdict: EXCELLENT - Production Ready
```

### Whitepaper Alignment

| Gate | FIG. 29 Spec | constraint_graph.py | Status |
|------|--------------|---------------------|--------|
| 1 | N ≥ 0.50 → REJECT | ✅ N ≥ 0.50 | Aligned |
| 2 | c < 0.4 → BLOCK | ✅ coherence < 0.4 AND N > 0.3 | **Fixed** |
| 3 | κ < κ_req(σ) → RE_ENCODE | ✅ Oobleck: 0.5 + 0.4σ | Aligned |
| 4 | κ_L < 0.3 → REPAIR | ✅ κ < 0.3 | Aligned |
