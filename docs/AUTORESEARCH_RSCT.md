# Autoresearch for RSCT Threshold Tuning

**Inspired by:** [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
**Date:** 2026-03-15
**Status:** PROPOSAL

---

## Connection to Our DOE Framework

We already have a mature DOE (Design of Experiments) system. The Karpathy autoresearch pattern is essentially **DOE with a single hypothesis optimized in a forever loop**.

### Pattern Equivalence

| Our DOE | Karpathy | Unified |
|---------|----------|---------|
| Hypothesis | "Try X" | **Hypothesis** |
| Factors/levels | `train.py` edits | **Mutable config** |
| Theorems | `prepare.py` | **Invariants** |
| Evidence JSON | results.tsv | **Evidence log** |
| VERIFIED/FAIL | keep/discard | **Decision** |
| Dashboard | progress.png | **Visualization** |
| Proofs | Best commit | **Artifacts** |

### Key Difference

```
DOE:         H1 → test → evidence → H2 → test → evidence → ...
Autoresearch: modify → test → keep/discard → modify → test → ...
```

**DOE** explores hypothesis space breadth-first.
**Autoresearch** optimizes metric depth-first.

### Unified Pattern: DOE-Autoresearch Hybrid

```python
# Phase 1: DOE (breadth-first hypothesis validation)
for hypothesis in [H1_gate_accuracy, H2_oobleck, H3_simplex]:
    evidence = run_experiment(hypothesis)
    assert_theorems(evidence)
    log_evidence(evidence)

# Phase 2: Autoresearch (depth-first optimization)
LOOP FOREVER:
    modify(thresholds.yaml)
    evidence = run_experiment(H_OPTIMIZE_F1)
    if evidence.f1 > best_f1:
        keep_commit()
        best_f1 = evidence.f1
    else:
        discard_commit()
```

---

## The Karpathy Pattern

```
LOOP FOREVER:
  1. Modify train.py with experimental idea
  2. Run 5-minute training
  3. If val_bpb improved → keep commit
  4. If val_bpb worse → git reset
  5. Log to results.tsv
```

**Key insights:**
- Single mutable file
- Fixed time budget
- Binary keep/discard decision
- Autonomous forever loop
- Simplicity criterion: "0.001 improvement with 20 lines of hacky code? Not worth it"

---

## RSCT Adaptation: AutoThreshold

### The Problem

RSCT has 5 threshold parameters that control gate behavior:

```python
BASELINE_THRESHOLDS = {
    "N_max": 0.5,           # Gate 1: Noise ceiling
    "coherence_min": 0.4,   # Gate 2: Consensus floor
    "kappa_base": 0.5,      # Gate 3: Compatibility base
    "kappa_lambda": 0.4,    # Gate 3: Oobleck coefficient
    "kappa_grounding": 0.3, # Gate 4: Grounding floor
}
```

Currently these are hand-tuned. We want autonomous optimization.

### The Pattern

```
LOOP FOREVER:
  1. Modify thresholds.yaml with experimental change
  2. Run validation suite (fixed 1000 samples, 2-minute budget)
  3. Compute metrics (FPR, FNR, F1)
  4. If F1 improved → keep commit
  5. If F1 worse → git reset
  6. Log to results.tsv
```

---

## File Structure

```
swarm-it-adk/
├── autothreshold/
│   ├── thresholds.yaml     # THE FILE AGENT MODIFIES
│   ├── evaluate.py         # Fixed evaluation harness (READ ONLY)
│   ├── program.md          # Agent instructions
│   └── results.tsv         # Experiment log
└── data/
    └── validation_set.pkl  # Frozen validation examples
```

### thresholds.yaml (Mutable)

```yaml
# AutoThreshold Configuration
# This file is modified by the agent during experimentation

version: 1
experiment_tag: "mar15-run1"

thresholds:
  N_max: 0.5
  coherence_min: 0.4
  kappa_base: 0.5
  kappa_lambda: 0.4
  kappa_grounding: 0.3

# Experimental parameters the agent can try:
# - Adjust individual thresholds ±0.05
# - Add coupling terms (e.g., kappa_base = f(N))
# - Add per-constraint tier multipliers
# - Try adaptive thresholds based on input characteristics
```

### evaluate.py (Read Only)

```python
"""
Fixed evaluation harness for AutoThreshold.
DO NOT MODIFY - this is the ground truth.
"""

import yaml
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

# Fixed constants
VALIDATION_SAMPLES = 1000
TIME_BUDGET_SECONDS = 120  # 2 minutes
EVAL_BATCH_SIZE = 50

@dataclass
class EvalResult:
    f1_score: float
    precision: float
    recall: float
    fpr: float  # False positive rate
    fnr: float  # False negative rate
    throughput: float  # samples/sec
    gate_stats: dict  # Per-gate failure counts

def load_thresholds(path: str = "thresholds.yaml") -> dict:
    """Load thresholds from YAML."""
    with open(path) as f:
        config = yaml.safe_load(f)
    return config["thresholds"]

def load_validation_set() -> List[Tuple[str, bool]]:
    """
    Load frozen validation set.
    Returns list of (prompt, ground_truth_safe) tuples.
    """
    import pickle
    with open("data/validation_set.pkl", "rb") as f:
        return pickle.load(f)

def evaluate(thresholds: dict) -> EvalResult:
    """
    Run evaluation with given thresholds.

    Returns EvalResult with metrics.
    Runs for fixed TIME_BUDGET_SECONDS.
    """
    from engine.rsct_gates import RSCTCertifier

    certifier = RSCTCertifier(thresholds=thresholds)
    validation_set = load_validation_set()

    tp, fp, tn, fn = 0, 0, 0, 0
    gate_failures = {f"gate_{i}": 0 for i in range(1, 5)}

    start = time.time()
    samples_processed = 0

    for prompt, ground_truth_safe in validation_set:
        if time.time() - start > TIME_BUDGET_SECONDS:
            break

        cert = certifier.certify(prompt)

        # Compare prediction to ground truth
        predicted_safe = cert.decision == "PROCEED"

        if ground_truth_safe and predicted_safe:
            tp += 1
        elif ground_truth_safe and not predicted_safe:
            fn += 1  # False negative (blocked safe content)
        elif not ground_truth_safe and predicted_safe:
            fp += 1  # False positive (allowed unsafe content)
        else:
            tn += 1

        # Track gate failures
        if cert.failed_gate:
            gate_failures[f"gate_{cert.failed_gate}"] += 1

        samples_processed += 1

    elapsed = time.time() - start

    # Compute metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
    throughput = samples_processed / elapsed

    return EvalResult(
        f1_score=f1,
        precision=precision,
        recall=recall,
        fpr=fpr,
        fnr=fnr,
        throughput=throughput,
        gate_stats=gate_failures,
    )

def main():
    """Run evaluation and print results."""
    thresholds = load_thresholds()
    result = evaluate(thresholds)

    print("---")
    print(f"f1_score:     {result.f1_score:.6f}")
    print(f"precision:    {result.precision:.6f}")
    print(f"recall:       {result.recall:.6f}")
    print(f"fpr:          {result.fpr:.6f}")
    print(f"fnr:          {result.fnr:.6f}")
    print(f"throughput:   {result.throughput:.1f}")
    print(f"gate_stats:   {result.gate_stats}")

if __name__ == "__main__":
    main()
```

### program.md (Agent Instructions)

```markdown
# AutoThreshold

Autonomous threshold tuning for RSCT gates.

## Setup

1. **Agree on run tag**: e.g., `mar15`
2. **Create branch**: `git checkout -b autothreshold/<tag>`
3. **Read files**:
   - `thresholds.yaml` — the file you modify
   - `evaluate.py` — fixed evaluation (READ ONLY)
4. **Verify data**: Check `data/validation_set.pkl` exists
5. **Initialize results.tsv**

## The Loop

LOOP FOREVER:

1. Modify `thresholds.yaml` with experimental change
2. `uv run evaluate.py > run.log 2>&1`
3. `grep "^f1_score:" run.log`
4. If f1_score improved → keep commit
5. If f1_score worse → git reset
6. Log to results.tsv

## What You CAN Modify

- Individual threshold values (±0.05 increments)
- Add coupling terms between thresholds
- Add tier-based multipliers
- Try adaptive formulas

## What You CANNOT Modify

- `evaluate.py` (read only)
- Validation set
- Time budget

## Simplicity Criterion

- +0.001 F1 with 5 lines of complexity? Keep.
- +0.001 F1 with 20 lines of hacks? Discard.
- -0.001 F1 but simpler? Keep.

## Results Format

```
commit	f1_score	fpr	fnr	status	description
a1b2c3d	0.850000	0.05	0.10	keep	baseline
b2c3d4e	0.855000	0.04	0.10	keep	lower N_max to 0.45
c3d4e5f	0.845000	0.06	0.10	discard	raise coherence_min to 0.5
```
```

---

## Experimental Ideas Queue

The agent should try these in order, keeping what works:

### Phase 1: Individual Threshold Sweeps

```yaml
# Try each threshold at ±0.05, ±0.10
experiments:
  - N_max: [0.4, 0.45, 0.55, 0.6]
  - coherence_min: [0.3, 0.35, 0.45, 0.5]
  - kappa_base: [0.4, 0.45, 0.55, 0.6]
  - kappa_lambda: [0.3, 0.35, 0.45, 0.5]
  - kappa_grounding: [0.2, 0.25, 0.35, 0.4]
```

### Phase 2: Coupled Thresholds

```yaml
# Try coupling terms
experiments:
  - kappa_effective: "kappa_base + kappa_lambda * (1 - N)"
  - coherence_adjusted: "coherence_min * (1 + N * 0.1)"
```

### Phase 3: Constraint Tier Multipliers

```yaml
# Per-tier threshold adjustments
tier_multipliers:
  EMERGENT: 1.0
  LEARNED: 0.9   # Stricter for learned constraints
  ACTUAL: 0.8    # Strictest for regulatory
```

### Phase 4: Input-Dependent Thresholds

```yaml
# Adaptive based on input characteristics
adaptive:
  long_text_multiplier: 0.95  # Stricter for long inputs
  high_entropy_multiplier: 1.05  # More lenient for high entropy
```

---

---

## Integration with swarm-doe Skill

Instead of creating a separate autoresearch system, we add **H9: Threshold Optimization** to our existing DOE framework.

### H9: Autonomous Threshold Optimization

**Statement:** Autonomous threshold tuning improves F1 score by ≥5% over baseline.

| Variable Type | Description |
|---------------|-------------|
| Independent | Threshold values (N_max, coherence_min, kappa_*, etc.) |
| Dependent | F1, FPR, FNR |
| Control | Fixed validation set, time budget |

**Metrics:**
- `f1_improvement`: Expected ≥ 0.05 (5%)
- `fpr_reduction`: Expected ≥ 0.02 (2%)
- `experiments_run`: Expected ≥ 100

**Evidence Required:** `evidence/h9_threshold_optimization.json`

### Adding to swarm-doe SKILL.md

```markdown
### H9: Threshold Optimization (Autoresearch Mode)

**Experiment Loop:**
1. Load current best thresholds
2. Generate mutation (±0.05 on random threshold)
3. Run validation suite (2 min budget)
4. If F1 improved → save as new best
5. Log to evidence JSON
6. Repeat until stopped

**Run Command:**
```bash
cd /Users/rudy/GitHub/swarm-it-adk
python -m autothreshold.optimize --time-budget 8h --output evidence/h9_threshold_optimization.json
```

**Success Criteria:**
- F1 improvement ≥ 5%
- No regression in any gate accuracy
- Evidence log with ≥ 100 experiments
```

### DOE Evidence Format (Already Have This)

```json
{
  "experiment": "H9_threshold_optimization",
  "timestamp": "2026-03-15T12:00:00Z",
  "hypothesis": "Autonomous tuning improves F1 by ≥5%",
  "factors": {
    "N_max": [0.45, 0.50, 0.55],
    "coherence_min": [0.35, 0.40, 0.45],
    "kappa_base": [0.45, 0.50, 0.55]
  },
  "results": [
    {"commit": "a1b2c3d", "f1": 0.850, "status": "baseline"},
    {"commit": "b2c3d4e", "f1": 0.855, "status": "keep"},
    {"commit": "c3d4e5f", "f1": 0.848, "status": "discard"}
  ],
  "theorems_validated": {
    "simplex": true,
    "kappa_bounds": true,
    "gate_order": true
  },
  "best_thresholds": {
    "N_max": 0.45,
    "coherence_min": 0.38,
    "kappa_base": 0.52
  },
  "improvement": {
    "f1_delta": 0.052,
    "fpr_delta": -0.023,
    "experiments_run": 127
  }
}
```

---

## Expected Results

After 8 hours of autonomous tuning (~240 experiments):

| Metric | Baseline | Expected |
|--------|----------|----------|
| F1 | 0.85 | 0.90+ |
| FPR | 0.10 | 0.05 |
| FNR | 0.15 | 0.08 |

---

## Integration with ThresholdLearner

Once AutoThreshold finds optimal values:

```python
# Update baseline in threshold_learner.py
BASELINE_THRESHOLDS = {
    "N_max": 0.45,          # Tuned from 0.5
    "coherence_min": 0.38,  # Tuned from 0.4
    "kappa_base": 0.52,     # Tuned from 0.5
    "kappa_lambda": 0.42,   # Tuned from 0.4
    "kappa_grounding": 0.28,# Tuned from 0.3
}
```

The ThresholdLearner then does online fine-tuning from this optimized baseline.

---

## Comparison: Karpathy vs RSCT

| Aspect | Karpathy | RSCT AutoThreshold |
|--------|----------|-------------------|
| Mutable file | `train.py` | `thresholds.yaml` |
| Time budget | 5 min | 2 min |
| Metric | val_bpb (lower) | F1 (higher) |
| Keep condition | bpb improved | F1 improved |
| Complexity | Model architecture | Threshold formulas |
| Experiments/hour | ~12 | ~30 |

---

## Safety Considerations

**Guardrails:**
- Thresholds clamped to [0.1, 0.9] range
- Cannot disable gates entirely
- Validation set includes known-bad examples
- Human review before production deployment

**Rollback:**
- All experiments on branch
- Main branch unchanged until human approval
- results.tsv provides full audit trail

---

## Next Steps

1. [ ] Create `autothreshold/` directory structure
2. [ ] Generate validation set (1000 labeled examples)
3. [ ] Implement `evaluate.py`
4. [ ] Write initial `thresholds.yaml`
5. [ ] Test single experiment cycle
6. [ ] Run overnight (8 hours)
7. [ ] Analyze results and propose new baseline

---

## Appendix: Results Analysis Script

```python
"""Analyze autothreshold results."""
import pandas as pd

df = pd.read_csv("results.tsv", sep="\t")

# Best result
best = df[df["status"] == "keep"].sort_values("f1_score", ascending=False).head(1)
print(f"Best F1: {best['f1_score'].values[0]:.6f}")
print(f"Commit: {best['commit'].values[0]}")
print(f"Description: {best['description'].values[0]}")

# Experiment stats
print(f"\nTotal experiments: {len(df)}")
print(f"Kept: {len(df[df['status'] == 'keep'])}")
print(f"Discarded: {len(df[df['status'] == 'discard'])}")
print(f"Crashed: {len(df[df['status'] == 'crash'])}")

# Improvement trajectory
kept = df[df["status"] == "keep"]
print(f"\nF1 improvement: {kept['f1_score'].iloc[0]:.4f} → {kept['f1_score'].iloc[-1]:.4f}")
```
