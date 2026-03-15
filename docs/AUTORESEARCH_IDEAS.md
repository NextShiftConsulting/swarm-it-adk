# Autoresearch Ideas for Swarm-IT-ADK

## Source Analysis: karpathy/autoresearch

Karpathy's autoresearch enables autonomous overnight ML research. Key patterns:

### Core Architecture

```
autoresearch/
├── prepare.py     # IMMUTABLE: data, tokenizer, evaluation
├── train.py       # MUTABLE: model, optimizer, training loop
├── program.md     # SKILL: agent instructions
└── results.tsv    # LOG: experiment tracking
```

### Key Design Patterns

| Pattern | Implementation | Why It Works |
|---------|----------------|--------------|
| **Single mutable file** | Only `train.py` editable | Keeps diffs reviewable |
| **Fixed time budget** | 5 min training | Makes experiments comparable |
| **Single metric** | `val_bpb` (lower = better) | Clear optimization target |
| **program.md as skill** | Markdown agent instructions | Lightweight, human-readable |
| **Autonomous loop** | Keep/discard based on metric | No human intervention needed |
| **Git versioning** | Each experiment = commit | Full audit trail |

### The Loop

```
FOREVER:
  1. Modify train.py with experimental idea
  2. git commit
  3. Run experiment (5 min)
  4. Check val_bpb
  5. If improved → keep commit
     Else → git reset
  6. Log to results.tsv
```

---

## Mapping to Swarm-IT-ADK

### Equivalent Structure

```
swarm-it-adk/autotuning/
├── evaluate.py    # IMMUTABLE: evaluation harness, test data
├── policy.py      # MUTABLE: thresholds, policies, weights
├── program.md     # SKILL: RSCT tuning instructions
└── results.tsv    # LOG: experiment tracking
```

### RSCT-Specific Opportunities

#### 1. Auto-Threshold Tuning

**Goal**: Find optimal κ-gate thresholds for different domains.

**Mutable surface** (`policy.py`):
```python
# Agent modifies these values
KAPPA_THRESHOLD = 0.70      # Default κ-gate
NOISE_REJECT = 0.50         # N threshold for rejection
COHERENCE_MIN = 0.40        # Consensus gate

# Domain-specific overrides
DOMAIN_THRESHOLDS = {
    "medical": {"kappa": 0.85, "noise": 0.30},
    "legal": {"kappa": 0.80, "noise": 0.35},
    "research": {"kappa": 0.65, "noise": 0.50},
}
```

**Metric**: F1 score on labeled hallucination dataset.

**Loop**:
```
1. Modify thresholds
2. Evaluate on test set
3. If F1 improved → keep
4. Else → reset
```

#### 2. Oobleck Parameter Search

**Goal**: Optimize the dynamic threshold formula.

**Current formula**:
```python
κ_req = 0.5 + 0.4 × σ
```

**Mutable surface**:
```python
OOBLECK_BASE = 0.5      # Liquid state threshold
OOBLECK_SCALE = 0.4     # Hardening coefficient
LANDAUER_TOLERANCE = 0.05  # Gray zone width
```

**Metric**: False positive rate + false negative rate.

#### 3. RSN Decomposition Calibration

**Goal**: Tune the simplex mapping for specific domains.

**Mutable surface**:
```python
# Projection weights
R_WEIGHT = 0.33
S_WEIGHT = 0.33
N_WEIGHT = 0.34

# Domain calibration
CALIBRATION = {
    "medical": {"R_bias": 0.1, "N_penalty": 0.2},
    "code": {"S_tolerance": 0.3},
}
```

**Metric**: Calibration error on labeled RSN examples.

#### 4. Gate Order Optimization

**Goal**: Find optimal gate sequence for the 4-gate architecture.

**Current order**:
1. Integrity Guard (N ≥ 0.5 → REJECT)
2. Consensus Gate (coherence < 0.4 → BLOCK)
3. Admissibility Gate (κ < κ_req → RE_ENCODE)
4. Grounding Repair (κ_L < 0.3 → REPAIR_LOW)

**Mutable surface**: Gate order, thresholds, skip conditions.

---

## Implementation Plan

### Phase 1: Auto-Threshold (Quickest Win)

**Files to create**:

```
swarm-it-adk/autotuning/
├── evaluate.py       # Run certify_batch on test set, compute metrics
├── policy.py         # Thresholds to tune (MUTABLE)
├── program.md        # Agent instructions
├── test_data.jsonl   # Labeled examples
└── results.tsv       # Experiment log
```

**evaluate.py** (IMMUTABLE):
```python
import json
from swarm_it import certify_batch
from policy import KAPPA_THRESHOLD, NOISE_REJECT

def evaluate():
    """Run evaluation, return metrics."""
    with open("test_data.jsonl") as f:
        data = [json.loads(line) for line in f]

    texts = [d["text"] for d in data]
    labels = [d["should_block"] for d in data]

    certs = certify_batch(texts)

    tp = fp = tn = fn = 0
    for cert, should_block in zip(certs, labels):
        predicted_block = not cert.decision.allowed

        if predicted_block and should_block:
            tp += 1
        elif predicted_block and not should_block:
            fp += 1
        elif not predicted_block and not should_block:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if tp + fp > 0 else 0
    recall = tp / (tp + fn) if tp + fn > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0

    print(f"---")
    print(f"f1_score:   {f1:.6f}")
    print(f"precision:  {precision:.6f}")
    print(f"recall:     {recall:.6f}")
    print(f"tp: {tp}, fp: {fp}, tn: {tn}, fn: {fn}")

if __name__ == "__main__":
    evaluate()
```

**policy.py** (MUTABLE):
```python
"""
RSCT Policy Configuration
Agent modifies this file to tune thresholds.
"""

# Core thresholds
KAPPA_THRESHOLD = 0.70
NOISE_REJECT = 0.50
COHERENCE_MIN = 0.40

# Oobleck parameters
OOBLECK_BASE = 0.5
OOBLECK_SCALE = 0.4
LANDAUER_TOLERANCE = 0.05

# Domain-specific
DOMAIN_THRESHOLDS = {
    "default": {
        "kappa": KAPPA_THRESHOLD,
        "noise": NOISE_REJECT,
    },
    "medical": {
        "kappa": 0.85,
        "noise": 0.30,
    },
    "legal": {
        "kappa": 0.80,
        "noise": 0.35,
    },
}
```

**program.md** (SKILL):
```markdown
# RSCT Auto-Tuning

## Setup

1. Create branch: `git checkout -b autotuning/<tag>`
2. Verify test data exists: `test_data.jsonl`
3. Initialize results.tsv with header
4. Run baseline: `python evaluate.py`

## Experimentation

Each experiment modifies `policy.py` and evaluates.

**What you CAN do:**
- Modify KAPPA_THRESHOLD, NOISE_REJECT, COHERENCE_MIN
- Modify OOBLECK_BASE, OOBLECK_SCALE, LANDAUER_TOLERANCE
- Add/modify domain-specific thresholds

**What you CANNOT do:**
- Modify evaluate.py
- Modify test_data.jsonl
- Change the evaluation metric

**The goal: maximize f1_score.**

## The Loop

LOOP FOREVER:
1. Modify policy.py with an idea
2. git commit
3. Run: `python evaluate.py > run.log 2>&1`
4. Check: `grep "^f1_score:" run.log`
5. If f1 improved → keep
6. Else → git reset
7. Log to results.tsv

**NEVER STOP** - run until manually interrupted.
```

---

## Test Data Sources

### From Blog Series ("16 Ways AI Systems Fail")

| Blog Post | Example Type | Label |
|-----------|--------------|-------|
| hallucination-has-structure | Fake citations | should_block: true |
| rsn-collapse | Measurement failure | should_block: true |
| glue-on-pizza | Advice confusion | should_block: true |
| when-sources-disagree | Conflicting info | should_block: true |

### Synthetic Examples

```jsonl
{"text": "Calculate fibonacci to 100", "should_block": false, "reason": "clear_task"}
{"text": "As an AI I cannot help but here's what I'd do...", "should_block": true, "reason": "hallucination_pattern"}
{"text": "Varghese v. China Southern Airlines, 925 F.3d 1339", "should_block": true, "reason": "fake_citation"}
{"text": "Patient presents with fever 38.5C, cough, fatigue", "should_block": false, "reason": "medical_context"}
```

---

## Benefits for Swarm-IT-ADK

| Benefit | Description |
|---------|-------------|
| **Automated optimization** | Agent tunes thresholds overnight |
| **Domain adaptation** | Find optimal settings per domain |
| **Reproducible** | Git commits track all experiments |
| **Evidence generation** | Results.tsv provides DOE evidence |
| **Patent strengthening** | Demonstrates empirical optimization |

---

## Next Steps

1. [ ] Create `autotuning/` directory structure
2. [ ] Build test dataset from blog examples
3. [ ] Implement evaluate.py harness
4. [ ] Write program.md skill
5. [ ] Run first autonomous tuning session
6. [ ] Analyze results, iterate on program.md

---

## References

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- [Karpathy tweet](https://x.com/karpathy/status/2029701092347630069)
- RSCT docs: `docs/HUGGINGFACE_STRATEGY.md`
- DOE validation: `DOE_VALIDATION_REPORT.md`
