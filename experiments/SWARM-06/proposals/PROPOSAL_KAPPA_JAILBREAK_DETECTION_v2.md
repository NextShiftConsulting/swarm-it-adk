# PROPOSAL v2: κ-Proxy Jailbreak Detection via Safe-Solver Incompatibility

**Proposal ID:** SWARM-06-P1-v2
**Status:** REVISED PER REVIEW COMMENTS
**Author:** SWARM Research Team
**Date:** 2026-03-16
**Revision:** v2.0 - Incorporates reviewer feedback

---

## Revision Summary

This revision addresses reviewer comments on the original proposal:

| # | Revision | Status |
|---|----------|--------|
| 1 | Label as κ-proxy experiment (not full DGM) | ✅ Incorporated |
| 2 | Low κ = incompatibility, not maliciousness | ✅ Incorporated |
| 3 | Intent-conditioned safe manifolds | ✅ Added |
| 4 | RSN/gates as supporting layers | ✅ Clarified |
| 5 | Operationalize σ (sigma) | ✅ Added |
| 6 | Add UNCERTAIN/abstain state | ✅ Added |
| 7 | Tighten anti-MARL language | ✅ Revised |
| 8 | Explicit attack families | ✅ Added |
| 9 | Robustness metrics beyond accuracy | ✅ Added |
| 10 | Frame as "security compatibility" | ✅ Adopted |

---

## Experiment Results: κ-Proxy v0 (Single Centroid)

**Status:** FAILED - No separation achieved

Before proceeding, we document that the simplest κ-proxy approach (single benign centroid) **does not separate jailbreaks from benign prompts**:

```
κ Distribution (Validation Set):
  Jailbreak: κ = 0.6502 ± 0.1408
  Benign:    κ = 0.6327 ± 0.1813

Cohen's d: -0.11 (negligible effect)
Test Accuracy: 43.2% (worse than random)
```

**Root Cause:** A single global centroid cannot capture the multi-modal nature of "safe interaction." Both jailbreaks and benign prompts can be about any topic - the difference is *intent*, not *topic*.

**Implication:** We need intent-conditioned or task-conditioned manifolds, as recommended in reviewer comment #3.

---

## Executive Summary (Revised)

This proposal tests whether **security compatibility** - measuring geometric incompatibility with modeled safe interaction solvers - can identify jailbreak risk. This is explicitly a **κ-proxy experiment**, not the full DGM κ formulation.

**Key conceptual framing:**
> This experiment does not attempt to prove that the system understands harmfulness directly. Rather, it tests whether jailbreak prompts occupy regions of representation space that are geometrically incompatible with modeled safe interaction solvers.

---

## Theoretical Distinction (NEW)

### κ-Proxy v1 (This Experiment)

Compatibility estimated using geometric surrogates:
- Intent-conditioned safe manifold distance
- Cluster-relative compatibility
- Mahalanobis distance to nearest safe region

### κ-Full (Future Work)

Full DGM formulation:
- Explicit representation graph G_R
- Explicit solver graph G_S
- Formal morphism/compatibility operator between them

This proposal implements κ-proxy v1 as a practical first step.

---

## Revised Classification States (NEW)

Instead of binary jailbreak/benign, we use four states:

| State | Meaning | Action |
|-------|---------|--------|
| **ADMISSIBLE** | Compatible with safe solver manifold | Proceed normally |
| **INCOMPATIBLE** | Geometric mismatch with safe manifold | Block + audit |
| **UNCERTAIN** | Near boundary, unclear compatibility | Human review / escalation |
| **UNSAFE** | Fails multiple gates (N-gate, coherence, κ) | Reject + alert |

**Critical:** Low κ indicates **incompatibility with the currently modeled safe solver**, which should be interpreted as:
- Elevated jailbreak risk, OR
- Distributional mismatch, OR
- Policy-incompatible geometry

It does NOT automatically mean malicious intent.

---

## Intent-Conditioned Safe Manifolds (NEW)

### Problem with Single Centroid

A global benign centroid incorrectly flags:
- Unusual but harmless prompts
- Novel benign domains
- Creative roleplay
- Red-team/security research prompts
- Harmless prompts with uncommon style

### Solution: Multi-Manifold Architecture

Build **intent-conditioned safe manifolds** rather than a single centroid:

```
Safe Manifolds:
├── M_general: General Q&A, information requests
├── M_creative: Creative writing, roleplay, fiction
├── M_technical: Code, math, technical queries
├── M_personal: Advice, emotional support
└── M_meta: Questions about AI, capabilities, limits

Compatibility Score:
  κ_local = max(κ(x, M_i) for M_i in manifolds)  # Best match
  κ_global = κ(x, M_all)                          # Overall safe distance

Classification:
  if κ_local > θ_high: ADMISSIBLE
  elif κ_local < θ_low: INCOMPATIBLE
  else: UNCERTAIN
```

### Manifold Construction

1. **Cluster benign training data** by intent/topic
2. **Compute per-cluster statistics** (centroid, covariance)
3. **For new input**: compute compatibility to nearest cluster
4. **Retain both local and global scores** for analysis

---

## Operationalizing σ (Sigma) (NEW)

### Definition

σ = instability under small semantic-preserving perturbations

### Measurement

Apply perturbations and measure compatibility variance:

```python
def compute_sigma(x, s_safe, n_perturbations=10):
    """Measure compatibility stability under perturbations."""
    perturbations = [
        paraphrase(x),           # Rephrase same meaning
        reorder_clauses(x),      # Reorder sentence parts
        insert_filler(x),        # Add "um", "well", etc.
        back_translate(x),       # Translate to/from another language
    ]

    kappa_values = [s_safe.compute_kappa(perturb(x)) for _ in range(n_perturbations)]
    sigma = np.std(kappa_values)

    return sigma
```

### Interpretation

| σ Value | Meaning | Risk |
|---------|---------|------|
| σ < 0.05 | Stable geometry | Low - genuine prompt |
| 0.05 ≤ σ < 0.15 | Moderate variance | Medium - monitor |
| σ ≥ 0.15 | Brittle geometry | High - possible adversarial |

**High σ indicates brittle or adversarial geometry** - the prompt may be carefully crafted to sit at a decision boundary.

---

## Revised Gate Architecture (NEW)

RSN and existing gates remain as supporting layers, not the main supervision target:

```
Input Prompt
     │
     ▼
┌─────────────────────────────────────────┐
│ Gate 1: Quality Filter (N-gate)         │
│ - Reject obvious corruption, nonsense   │
│ - High N → UNSAFE                        │
└─────────────────────────────────────────┘
     │ (passes)
     ▼
┌─────────────────────────────────────────┐
│ Gate 2: Coherence/Stability Filter      │
│ - Check internal consistency            │
│ - Phasor coherence < 0.4 → flag         │
└─────────────────────────────────────────┘
     │ (passes)
     ▼
┌─────────────────────────────────────────┐
│ Gate 3: κ-Proxy Compatibility Gate      │  ← THIS EXPERIMENT
│ - Compute κ_local, κ_global             │
│ - Compute σ (perturbation stability)    │
│ - Route to ADMISSIBLE/INCOMPATIBLE/     │
│   UNCERTAIN/UNSAFE                      │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Gate 4: Policy Decision/Routing         │
│ - Combine all gate signals              │
│ - Apply policy-specific thresholds      │
│ - Route: execute / escalate / block     │
└─────────────────────────────────────────┘
```

---

## Revised Anti-MARL Section (NEW)

### Attack Families (Explicit)

**A. Boundary-Hugging Attacks**
- Prompts crafted to remain close to safe manifold while attempting harmful outcomes
- **Mitigation:** Multi-manifold matching reduces single-boundary vulnerability; σ detects unstable geometry

**B. Probing Attacks**
- Repeated adaptive queries to infer decision boundary
- **Mitigation:** Rate limiting, query pattern detection, stochastic noise injection

**C. Encoder-Gaming Attacks**
- Prompts exploiting embedding model weaknesses or blind spots
- **Mitigation:** Multi-encoder ensemble, layer-wise analysis

**D. Benign-Set Contamination**
- Degradation from mislabeled or low-quality benign anchor data
- **Mitigation:** Data quality validation, periodic retraining, drift monitoring

### Revised Language (Tightened)

**Original (too strong):**
> "Cannot be gamed by adding safe words"

**Revised (accurate):**
> Is harder to game with lexical camouflage than keyword-based or policy-string detectors, but remains vulnerable to adaptive manifold-hugging and encoder-targeted attacks, which this experiment will explicitly test.

---

## Revised Success Criteria (NEW)

Beyond headline accuracy, we measure:

| Metric | Target | Rationale |
|--------|--------|-----------|
| Accuracy | > 85% | Primary performance |
| Precision | > 80% | Minimize false accusations |
| Recall | > 85% | Catch most jailbreaks |
| F1 Score | > 0.82 | Balance |
| AUROC | > 0.85 | Ranking quality |
| FPR on hard benign | < 10% | Don't block unusual but safe prompts |
| Paraphrase robustness | > 80% | Stability under rewording |
| Calibration (ECE) | < 0.10 | Confidence matches accuracy |
| σ-flagging precision | > 70% | High-σ predicts adversarial |

---

## Experimental Design (Revised)

### Phase 1: Intent-Conditioned Manifold Construction

1. Cluster benign training data (K=5-10 clusters)
2. Compute per-cluster TrainingDistributionStats
3. Save as `intent_manifolds.npz`

### Phase 2: Multi-Metric Evaluation

1. Compute κ_local (nearest manifold)
2. Compute κ_global (overall)
3. Compute σ (perturbation stability)
4. Classify with 4-state output

### Phase 3: Adversarial Testing

1. Generate paraphrase variants
2. Test boundary-hugging samples
3. Measure robustness metrics

### Phase 4: Gate Integration

1. Combine with existing N-gate, coherence gate
2. Evaluate full pipeline performance

---

## Implementation Plan

```python
# Phase 1: Build intent manifolds
clusters = cluster_benign_data(benign_embeddings, n_clusters=5)
intent_manifolds = {
    f"intent_{i}": SafeSolverDistribution.from_embeddings(cluster)
    for i, cluster in enumerate(clusters)
}

# Phase 2: Multi-metric classification
def classify_with_uncertainty(x, manifolds):
    # Local compatibility (best matching intent)
    kappa_local = max(m.compute_kappa(x) for m in manifolds.values())

    # Global compatibility
    kappa_global = global_manifold.compute_kappa(x)

    # Perturbation stability
    sigma = compute_sigma(x, manifolds)

    # 4-state classification
    if kappa_local > 0.7 and sigma < 0.1:
        return "ADMISSIBLE"
    elif kappa_local < 0.3 or sigma > 0.2:
        return "INCOMPATIBLE" if kappa_local < 0.3 else "UNSAFE"
    else:
        return "UNCERTAIN"
```

---

## Approval Status

**APPROVED WITH REVISIONS** per reviewer memo.

All 10 revision points have been incorporated into this v2 proposal.

---

## Next Steps

1. ☐ Implement intent-conditioned manifold clustering
2. ☐ Add σ (perturbation stability) measurement
3. ☐ Implement 4-state classification
4. ☐ Run adversarial testing suite
5. ☐ Generate comprehensive robustness metrics
6. ☐ Integrate with existing gate pipeline

---

**END OF PROPOSAL v2**
