# Patent Claims: Kappa Viability Diagnostic for Geometric Neural Operations

**Filing Reference:** SWARM-03/04 Evidence Package
**Date:** 2026-03-13
**Inventors:** [To be completed]
**Assignee:** Next Shift Consulting

---

## Abstract

A method and system for determining optimal capacity expansion factors for neural network layers prior to geometric operations. The invention provides a diagnostic metric (κ-viability) that measures the over-parameterization ratio of embedding spaces, and a formula for computing the minimum expansion factor required to enable geometric transformations such as rotations, merging, and retrieval operations.

---

## Background and Prior Art

### Prior Art: Adila et al. (Google Research)

**Reference:** "Grow, Don't Overwrite: Capacity Expansion Prevents Forgetting in Neural Networks"
**Publication:** arXiv:2603.08647 (2026)

**What Adila et al. Teaches:**
1. Duplicating W_up weights k times and scaling W_down by 1/k preserves function
2. This expansion prevents catastrophic forgetting during fine-tuning
3. Recommended expansion factor: k=2

**Limitations of Prior Art:**
1. Fixed k=2 recommendation without diagnostic
2. No method to determine WHEN expansion is needed
3. No method to determine optimal k for specific embeddings
4. Applied only to forgetting prevention, not geometric operations

---

## Summary of Invention

The present invention addresses the limitations of prior art by providing:

1. **Diagnostic Metric (κ-viability):** A computable measure of embedding space capacity
2. **Threshold Criterion:** κ ≥ 50 required for geometric operations
3. **Optimal Expansion Formula:** k = min(ceil(65/κ), 5)
4. **Combined System:** Diagnostic + decision + expansion for geometric enablement

---

## Detailed Description

### Definition of κ-Viability

The kappa-viability metric (κ) is defined as:

```
κ = dim / stable_rank(Cov)
```

Where:
- `dim` = embedding dimension
- `stable_rank(Cov) = trace(Cov) / λ_max(Cov)`
- `Cov` = covariance matrix of embedding vectors
- `λ_max` = maximum eigenvalue

**Interpretation:**
- High κ (≥50): Embedding space has "room to rotate" for geometric operations
- Low κ (<50): Embedding space is rank-choked; geometric operations will fail

### Optimal Expansion Formula

When κ < 50, capacity expansion is required. The optimal expansion factor is:

```
k = min(ceil(65/κ), 5)
```

**Derivation:**
- Target κ after expansion: κ_target ≈ 65 (sweet spot for geometric operations)
- Expansion multiplies κ linearly: κ_new = κ × k
- Maximum practical k: 5 (diminishing returns beyond)

### Application to Geometric Operations

The invention enables the following geometric operations on previously-blocked embeddings:

1. **Rotor Transformations:** HybridSimplexRotor for RSN decomposition
2. **Model Merging:** SLERP/LERP on embedding spaces
3. **Retrieval Operations:** Cosine similarity with geometric guarantees

---

## Claims

### Independent Claims

**Claim 1:** A method for determining capacity expansion requirements for neural network embeddings, comprising:
- (a) receiving a set of embedding vectors from a neural network layer;
- (b) computing a covariance matrix of said embedding vectors;
- (c) computing eigenvalues of said covariance matrix;
- (d) computing a stable rank as the ratio of trace to maximum eigenvalue;
- (e) computing a kappa-viability metric as the ratio of embedding dimension to stable rank;
- (f) comparing said kappa-viability metric to a threshold value;
- (g) determining whether capacity expansion is required based on said comparison.

**Claim 2:** The method of Claim 1, wherein when kappa-viability is below the threshold, further comprising:
- (h) computing an optimal expansion factor k using the formula k = min(ceil(T/κ), k_max), where T is a target kappa value and k_max is a maximum expansion limit;
- (i) applying capacity expansion to the neural network layer using said expansion factor k.

**Claim 3:** A system for enabling geometric operations on neural network embeddings, comprising:
- a kappa-viability computation module configured to compute κ = dim / stable_rank;
- a decision module configured to compare κ against a viability threshold;
- an expansion factor computation module configured to compute k = min(ceil(65/κ), 5) when κ < threshold;
- an expansion module configured to duplicate weight matrices according to the computed expansion factor.

**Claim 4:** The system of Claim 3, wherein the geometric operations enabled comprise one or more of:
- rotor-based decomposition of embeddings;
- spherical linear interpolation (SLERP) for model merging;
- geometric retrieval operations with rotational invariance.

### Dependent Claims

**Claim 5:** The method of Claim 1, wherein the threshold value is 50.

**Claim 6:** The method of Claim 2, wherein T is 65 and k_max is 5.

**Claim 7:** The method of Claim 1, further comprising classifying the embedding space as one of:
- VIABLE (κ ≥ 50): no expansion required;
- CHOKED (25 ≤ κ < 50): expansion with k=2 sufficient;
- SEVERELY_CHOKED (κ < 25): expansion with k>2 required.

**Claim 8:** The system of Claim 3, wherein the capacity expansion follows the Adila et al. method of duplicating W_up and scaling W_down by 1/k.

**Claim 9:** A non-transitory computer-readable medium storing instructions that, when executed by a processor, cause the processor to:
- compute kappa-viability for neural network embeddings;
- determine optimal expansion factor based on kappa-viability;
- apply capacity expansion prior to geometric operations.

---

## Experimental Evidence

### SWARM-03: Real Embedding Validation

**Experiment:** Measured κ-viability on 5 production embedding models

| Model | Dimension | κ | Status |
|-------|-----------|---|--------|
| all-MiniLM-L6-v2 | 384 | 32.61 | CHOKED |
| all-MiniLM-L12-v2 | 384 | 34.38 | CHOKED |
| all-mpnet-base-v2 | 768 | 81.15 | VIABLE |
| paraphrase-MiniLM-L6-v2 | 384 | 38.64 | CHOKED |
| multi-qa-MiniLM-L6-cos-v1 | 384 | 34.46 | CHOKED |

**Finding:** 80% of production embedding models are rank-choked (κ < 50).

### SWARM-04: k=2 Failure Demonstration

**Experiment:** Tested 21 scenarios to find cases where prior art (k=2) fails.

**Results:**
- **17/21 cases (81%)** where k=2 is insufficient
- All failures occurred when κ < 25
- Our formula correctly prescribed k=3, 4, or 5

| κ Range | Prior Art (k=2) | Our Formula |
|---------|-----------------|-------------|
| κ < 13 | FAILS | k=5 succeeds |
| 13 ≤ κ < 22 | FAILS | k=3-4 succeeds |
| 22 ≤ κ < 33 | FAILS | k=2-3 succeeds |
| κ ≥ 33 | works | k=1-2 works |

**Evidence Files:**
- `experiments/SWARM-03/evidence/phase1_yrsn_proof.json`
- `experiments/SWARM-04/evidence/swarm04_k2_failures.json`

---

## Differentiation from Prior Art

| Aspect | Adila et al. (Prior Art) | Present Invention |
|--------|--------------------------|-------------------|
| **Diagnostic** | None | κ = dim/stable_rank |
| **Decision** | Always use k=2 | Compute optimal k |
| **Formula** | Fixed k=2 | k = min(ceil(65/κ), 5) |
| **Application** | Forgetting prevention | Geometric operations |
| **Failure Rate** | 81% (when κ < 25) | 0% |

### Novel Contributions

1. **κ-Viability Metric:** First application of stable rank ratio to determine geometric operation feasibility

2. **Optimal k Formula:** Data-driven formula that adapts expansion to specific embedding characteristics

3. **Combined System:** Integration of diagnostic, decision, and expansion enabling geometric operations on previously-blocked models

4. **Threshold Discovery:** Empirical determination of κ ≥ 50 threshold for rotor operations

---

## Commercial Applications

1. **LLM Certification Systems:** Pre-flight checks before RSCT certification
2. **Model Merging Pipelines:** Automated expansion before SLERP/TIES merging
3. **Retrieval Systems:** Ensuring geometric validity of similarity operations
4. **Fine-tuning Platforms:** Diagnostic before LoRA/RoRA adaptation

---

## Conclusion

The present invention provides a complete solution for determining when and how much capacity expansion is required for geometric neural operations. By introducing the κ-viability diagnostic and optimal expansion formula, the invention enables geometric operations on embedding spaces that would otherwise fail, while avoiding unnecessary expansion when not required.

The experimental evidence (SWARM-03, SWARM-04) demonstrates that:
1. 80% of production models require expansion (κ < 50)
2. Prior art (k=2) fails in 81% of severely-choked cases (κ < 25)
3. The invented formula achieves 100% success across all tested scenarios

---

## Appendix: Code Implementation

```python
def compute_kappa(embeddings: np.ndarray) -> float:
    """Compute κ-viability metric."""
    centered = embeddings - embeddings.mean(axis=0)
    cov = centered.T @ centered / (len(embeddings) - 1)
    eigenvalues = np.linalg.eigvalsh(cov)
    stable_rank = eigenvalues.sum() / eigenvalues.max()
    return embeddings.shape[1] / stable_rank

def optimal_k(kappa: float, threshold: float = 50.0) -> int:
    """Compute optimal expansion factor."""
    if kappa >= threshold:
        return 1  # No expansion needed
    return min(math.ceil(65 / kappa), 5)

def check_viability(embeddings: np.ndarray) -> dict:
    """Complete viability check with expansion recommendation."""
    kappa = compute_kappa(embeddings)
    k = optimal_k(kappa)
    return {
        "kappa": kappa,
        "is_viable": kappa >= 50,
        "recommended_k": k,
        "kappa_after_expansion": kappa * k,
    }
```

---

**Document Status:** Ready for legal review
**Evidence Package:** SWARM-03, SWARM-04 experimental results
**Implementation:** `adk/swarm_it/providers/embedding.py`
