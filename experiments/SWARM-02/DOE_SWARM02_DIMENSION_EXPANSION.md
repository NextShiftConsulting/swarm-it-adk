# DOE: SWARM-02 Dimension Expansion for Rotor Capacity

**Experiment ID:** SWARM-02
**Domain:** Geometric ML / Rotor Capacity
**Status:** DRAFT
**Created:** 2026-03-13
**Reference:** arXiv:2603.08647 (Adila et al., "Grow, Don't Overwrite")

---

## Abstract

Test whether MLP dimension expansion (per Adila et al.) increases the over-parameterization ratio κ and enables rotors to work in previously "rank-choked" scenarios.

**Core Question:** Does doubling MLP dimension reliably increase κ and improve rotor performance on real data?

---

## Background

### The κ Problem (Sudjianto, SSRN 6101568)

```
κ = dim / stable_rank(Cov)

κ < 50:  "rank-choked" — rotor can't find rotation plane
κ ≥ 50:  "room to rotate" — rotor can align subspaces
```

### The Proposed Fix (Adila et al., arXiv:2603.08647)

```python
# Double MLP hidden dimension
W_up_new = [W_up | W_up]           # h × 2p
W_down_new = [W_down/2; W_down/2]  # 2p × h

# Function-preserving: output identical at initialization
```

### Hypothesis

Doubling MLP dimension should approximately double κ, moving rank-choked scenarios into "room to rotate" territory.

---

## Hypotheses

### H1: κ Doubles with Dimension Expansion

**Statement:** After MLP dimension expansion (k=2), κ_new ≈ 2 × κ_original (±20%)

| Variable Type | Description |
|---------------|-------------|
| Independent | Expansion factor k ∈ {1, 2, 3, 4} |
| Dependent | κ = dim / stable_rank(Cov) |
| Control | Same input data, same model architecture |

**Metrics:**
- `kappa_ratio`: κ_expanded / κ_original
- `expected`: 2.0 for k=2

**Evidence Required:** `evidence/h1_kappa_scaling.json`

---

### H2: Rank-Choked Scenarios Become Viable

**Statement:** Scenarios with κ_original < 50 achieve κ_expanded ≥ 50 after k=2 expansion

| Variable Type | Description |
|---------------|-------------|
| Independent | Original κ ∈ {20, 30, 40, 45} |
| Dependent | Expanded κ after k=2 |
| Control | Expansion factor k=2 |

**Metrics:**
- `kappa_before`: Original κ
- `kappa_after`: Expanded κ
- `threshold_crossed`: κ_after ≥ 50

**Evidence Required:** `evidence/h2_threshold_crossing.json`

---

### H3: Rotor Performance Improves

**Statement:** Rotor accuracy improves by ≥10% when κ crosses from <50 to ≥50

| Variable Type | Description |
|---------------|-------------|
| Independent | κ regime (choked vs adequate) |
| Dependent | Rotor classification accuracy |
| Control | Same downstream task |

**Metrics:**
- `accuracy_before`: Accuracy with κ < 50
- `accuracy_after`: Accuracy with κ ≥ 50
- `improvement`: (after - before) / before

**Evidence Required:** `evidence/h3_rotor_accuracy.json`

---

### H4: Function Preservation Holds

**Statement:** Model output is identical (MSE < 1e-6) before and after expansion at initialization

| Variable Type | Description |
|---------------|-------------|
| Independent | Expansion (none vs k=2) |
| Dependent | Output MSE |
| Control | Same input batch |

**Metrics:**
- `mse_before_after`: Mean squared error between outputs
- `max_abs_diff`: Maximum absolute difference

**Evidence Required:** `evidence/h4_function_preservation.json`

---

### H5: RSN Decomposition Improves

**Statement:** RSN decomposition correlation with ground truth improves when κ ≥ 50

| Variable Type | Description |
|---------------|-------------|
| Independent | κ regime |
| Dependent | RSN correlation with labels |
| Control | Same evaluation set |

**Metrics:**
- `rsn_correlation_before`: Pearson r with κ < 50
- `rsn_correlation_after`: Pearson r with κ ≥ 50

**Evidence Required:** `evidence/h5_rsn_quality.json`

---

## Experimental Protocol

### Phase 1: Synthetic Validation

1. Create synthetic embeddings with controlled stable_rank
2. Compute κ before expansion
3. Apply dimension expansion (k=2)
4. Compute κ after expansion
5. Verify κ_ratio ≈ 2.0

### Phase 2: Real Data (CIFAR-10 Embeddings)

1. Load CIFAR-10 embeddings (ResNet/ViT features)
2. Compute stable_rank and κ
3. If κ < 50: apply expansion
4. Train rotor on original vs expanded
5. Compare classification accuracy

### Phase 3: Real Data (Text Embeddings)

1. Load text embeddings (sentence-transformers)
2. Same protocol as Phase 2
3. Evaluate on text classification task

### Phase 4: Cross-Modal

1. Combine vision + text embeddings
2. Test rotor on multimodal task
3. Compare κ and accuracy before/after expansion

---

## Data Sources

| Source | Type | Size | κ Expected |
|--------|------|------|------------|
| Synthetic (low rank) | Generated | 1000 | 20-40 |
| Synthetic (high rank) | Generated | 1000 | 60-100 |
| CIFAR-10 (ResNet) | Embeddings | 10000 | ~30-50 |
| CIFAR-10 (ViT) | Embeddings | 10000 | ~40-60 |
| SentenceTransformers | Text | 5000 | ~25-45 |

---

## Success Criteria

| Hypothesis | Criterion | Status |
|------------|-----------|--------|
| H1 | κ_ratio ∈ [1.8, 2.2] for k=2 | PENDING |
| H2 | ≥80% of choked scenarios cross threshold | PENDING |
| H3 | Accuracy improvement ≥10% | PENDING |
| H4 | MSE < 1e-6 | PENDING |
| H5 | Correlation improvement ≥0.05 | PENDING |

---

## Dashboard Telemetry

### Expected Ranges

| Metric | Before Expansion | After Expansion |
|--------|------------------|-----------------|
| κ | 20-45 | 40-90 |
| stable_rank | ~5 | ~5 (unchanged) |
| dim | p | 2p |
| Rotor accuracy | 60-75% | 75-90% |

---

## Proofs Required

1. `proof_kappa_scaling.md` - Mathematical proof that κ scales with dimension
2. `proof_function_preservation.md` - Proof of the scaling trick

---

## Code Requirements

```python
# Key functions to implement
def compute_kappa(features: torch.Tensor) -> float
def expand_mlp_dimension(W_up, W_down, k=2) -> Tuple[Tensor, Tensor]
def verify_function_preservation(model_original, model_expanded, inputs) -> float
def train_rotor_and_evaluate(features, labels, kappa_threshold=50) -> dict
```

---

## Timeline

1. Implement expansion utilities
2. Synthetic validation (H1, H4)
3. Real data experiments (H2, H3, H5)
4. Generate visualizations
5. Write proofs

---

## References

- Adila et al. (2026). "Grow, Don't Overwrite." arXiv:2603.08647
- Sudjianto (2024). "RoRA: Low-Rank Rotational Adaptation." SSRN 6101568
- YRSN rotor.py: `check_rotor_capacity()`
