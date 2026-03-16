# RSCT AutoTuning

Autonomous threshold optimization using the Karpathy autoresearch pattern.

**Goal:** Maximize F1 score by tuning RSCT gate thresholds.

---

## Setup

1. **Agree on run tag**: Propose a tag based on today's date (e.g., `mar15`). The branch `autotuning/<tag>` must not already exist.

2. **Create the branch**:
   ```bash
   cd /Users/rudy/GitHub/swarm-it-adk
   git checkout -b autotuning/<tag>
   ```

3. **Read the in-scope files**:
   - `autotuning/thresholds.yaml` — **THE FILE YOU MODIFY**
   - `autotuning/evaluate.py` — Fixed evaluation harness (READ ONLY)
   - `autotuning/program.md` — These instructions

4. **Verify evaluation works**:
   ```bash
   cd /Users/rudy/GitHub/swarm-it-adk/autotuning
   python evaluate.py
   ```

5. **Initialize results.tsv** if not exists:
   ```bash
   echo "commit\tf1_score\tfpr\tfnr\tstatus\tdescription" > results.tsv
   ```

6. **Confirm and go**: Confirm setup looks good, then start the loop.

---

## The Loop

**LOOP FOREVER:**

1. **Modify** `thresholds.yaml` with an experimental change
   - Adjust one threshold by ±0.05
   - Or try a coupling formula
   - Or add a tier multiplier

2. **Commit** the change:
   ```bash
   git add thresholds.yaml
   git commit -m "try: <description of change>"
   ```

3. **Run** the evaluation:
   ```bash
   python evaluate.py > run.log 2>&1
   ```

4. **Check** the result:
   ```bash
   grep "^f1_score:" run.log
   ```

5. **Decide**:
   - If f1_score **improved** → **KEEP** the commit
   - If f1_score **same or worse** → **DISCARD**:
     ```bash
     git reset --hard HEAD~1
     ```

6. **Log** to results.tsv:
   ```bash
   echo "<commit>\t<f1>\t<fpr>\t<fnr>\t<keep|discard>\t<description>" >> results.tsv
   ```

7. **Repeat** — go back to step 1

---

## What You CAN Modify

In `thresholds.yaml`, you can change:

### Core Thresholds
```yaml
thresholds:
  N_max: 0.50         # Try: 0.40, 0.45, 0.55, 0.60
  coherence_min: 0.40  # Try: 0.30, 0.35, 0.45, 0.50
  kappa_base: 0.50     # Try: 0.40, 0.45, 0.55, 0.60
  kappa_lambda: 0.40   # Try: 0.30, 0.35, 0.45, 0.50
  kappa_grounding: 0.30 # Try: 0.20, 0.25, 0.35, 0.40
```

### Tier Multipliers
```yaml
experimental:
  tier_multipliers:
    EMERGENT: 1.0   # Try: 0.95, 1.05
    LEARNED: 0.95   # Try: 0.90, 1.00
    ACTUAL: 0.90    # Try: 0.85, 0.95
```

### Coupling Experiments
```yaml
experimental:
  coupling:
    enabled: true
    coherence_adjusted: "coherence_min * (1 + N * 0.1)"
```

---

## What You CANNOT Modify

- `evaluate.py` — Fixed evaluation harness
- `data/validation_set.jsonl` — Fixed test data
- The evaluation metric (F1 score)
- The timeout (2 minutes)

---

## Simplicity Criterion

All else being equal, simpler is better:

| Change | F1 Improvement | Decision |
|--------|----------------|----------|
| +20 lines complexity | +0.001 | **DISCARD** |
| -10 lines (simpler) | +0.001 | **KEEP** |
| +5 lines | +0.050 | **KEEP** |
| Remove feature | +0.000 | **KEEP** (simpler) |

---

## Constraints

**NEVER violate:**
- All thresholds must be in [0.1, 0.9]
- Cannot disable any gate
- Gate order must be 1 → 2 → 3 → 4

---

## Results Format

Tab-separated (NOT comma), 6 columns:

```
commit	f1_score	fpr	fnr	status	description
a1b2c3d	0.800000	0.10	0.20	keep	baseline
b2c3d4e	0.820000	0.08	0.18	keep	lower N_max to 0.45
c3d4e5f	0.790000	0.12	0.18	discard	raise coherence_min to 0.5
d4e5f6g	0.000000	0.00	0.00	crash	coupling formula syntax error
```

---

## Experiment Ideas Queue

Try these in order, keeping what works:

### Phase 1: Individual Threshold Sweeps
1. N_max: [0.40, 0.45, 0.55, 0.60]
2. coherence_min: [0.30, 0.35, 0.45, 0.50]
3. kappa_base: [0.40, 0.45, 0.55, 0.60]
4. kappa_lambda: [0.30, 0.35, 0.45, 0.50]
5. kappa_grounding: [0.20, 0.25, 0.35, 0.40]

### Phase 2: Combined Changes
Based on Phase 1 results, try combining the best values.

### Phase 3: Tier Multipliers
Try making ACTUAL tier stricter (0.90) and EMERGENT more lenient (1.05).

### Phase 4: Coupling (Advanced)
If Phase 1-3 plateau, try coupling formulas.

---

## NEVER STOP

Once the loop has begun, **do NOT pause to ask**:
- "Should I continue?"
- "Is this a good stopping point?"
- "Do you want me to keep going?"

The human may be asleep. Run **indefinitely** until manually interrupted.

If you run out of ideas:
- Re-read evaluation results for patterns
- Try more radical changes
- Combine previous near-misses
- Try the opposite of what failed

---

## Expected Results

After 2-4 hours (~60-120 experiments):

| Metric | Baseline | Expected |
|--------|----------|----------|
| F1 | 0.80 | 0.85+ |
| FPR | 0.10 | 0.05 |
| FNR | 0.20 | 0.10 |

---

## Crash Recovery

If evaluation crashes:
1. Read `run.log` tail for error
2. If syntax error in YAML → fix and retry
3. If fundamental issue → discard and move on
4. Log "crash" status in results.tsv

```bash
tail -n 20 run.log
```

---

## When Done

When manually stopped, generate summary:

```bash
# Best result
sort -t$'\t' -k2 -rn results.tsv | head -5

# Experiment stats
wc -l results.tsv
grep -c "keep" results.tsv
grep -c "discard" results.tsv
```
