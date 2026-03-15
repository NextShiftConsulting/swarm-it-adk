# SWARM-05: Discovery-Inspired Experiments

**Date:** 2026-03-15
**Source:** swarm-it-discovery tier3-log findings
**Status:** PROPOSED

---

## Experiment Ideas from Discovery Pipeline

### E1: Incremental Conflict Learning Across Gates

**Inspiration:** arxiv:2603.12232 - "Incremental Neural Network Verification via Learned Conflicts"

**Key Insight:** Reuse learned infeasible regions across verification queries. "Conflicts learned for a query remain valid under refinement."

**RSCT Application:**
When Gate 1 (Integrity) rejects due to N > 0.5, that "conflict" could propagate to Gate 3 (Admissibility) to tighten κ requirements for similar inputs.

**Hypothesis H13:** Cross-gate conflict propagation reduces false negatives by 15%

| Variable | Type | Range |
|----------|------|-------|
| conflict_memory_size | Independent | 100, 500, 1000 |
| propagation_decay | Independent | 0.9, 0.95, 0.99 |
| gate_pairs | Independent | [1→3], [2→4], [1→2→3→4] |
| false_negative_rate | Dependent | - |

**Implementation Sketch:**
```python
class ConflictCache:
    """Cache learned conflicts from gate failures."""

    def __init__(self, max_size: int = 500):
        self.conflicts = {}  # embedding_hash → (gate, reason, timestamp)

    def record_conflict(self, embedding: np.ndarray, gate: int, reason: str):
        key = hash(embedding.tobytes())
        self.conflicts[key] = (gate, reason, time.time())

    def check_similar(self, embedding: np.ndarray, threshold: float = 0.95):
        """Check if similar embeddings have known conflicts."""
        # Could use LSH for efficient similarity search
        pass
```

---

### E2: Token-Level Noise Partitioning (STAMP-inspired)

**Inspiration:** arxiv:2603.12237 - "STAMP: Selective Task-Aware Mechanism for Text Privacy"

**Key Insight:** "Selectively allocates privacy budgets across tokens by jointly considering (i) token importance to downstream task, and (ii) privacy sensitivity."

**RSCT Application:**
Instead of computing a single N value for the entire text, compute per-token noise estimates. High-importance tokens with high noise → stronger rejection signal.

**Hypothesis H14:** Per-token noise weighting improves hallucination detection F1 by 10%

| Variable | Type | Range |
|----------|------|-------|
| token_importance_method | Independent | attention, gradient, tf-idf |
| aggregation | Independent | max, weighted_mean, top_k_mean |
| k (for top_k) | Independent | 3, 5, 10 |
| hallucination_f1 | Dependent | - |

**Implementation Sketch:**
```python
def compute_token_noise(text: str, embeddings: np.ndarray, attention_weights: np.ndarray):
    """Compute per-token noise weighted by importance."""

    # Get per-token embeddings (from model)
    token_embeddings = get_token_embeddings(text)

    # Compute per-token noise estimate
    token_noise = []
    for i, tok_emb in enumerate(token_embeddings):
        # N_i = distance to nearest training example
        n_i = compute_noise_component(tok_emb)
        importance_i = attention_weights[i]
        token_noise.append((n_i, importance_i))

    # Aggregate: importance-weighted noise
    weighted_n = sum(n * imp for n, imp in token_noise) / sum(imp for _, imp in token_noise)

    # Also track max noise on high-importance tokens
    high_imp_n = max(n for n, imp in token_noise if imp > 0.1)

    return weighted_n, high_imp_n
```

---

### E3: Iterative Grounding Repair (EndoCoT-inspired)

**Inspiration:** arxiv:2603.12252 - "EndoCoT: Scaling Endogenous Chain-of-Thought Reasoning"

**Key Insight:** "Iteratively refining latent thought states" + "terminal thought grounding module ensures reasoning trajectory remains grounded in textual supervision."

**RSCT Application:**
Gate 4 (Grounding Repair) currently does single-pass repair. EndoCoT suggests iterative refinement with a terminal grounding check.

**Hypothesis H15:** Iterative grounding repair (max 3 iterations) improves κ_L by 20%

| Variable | Type | Range |
|----------|------|-------|
| max_iterations | Independent | 1, 2, 3, 5 |
| convergence_threshold | Independent | 0.01, 0.05, 0.1 |
| grounding_method | Independent | cosine, contrastive, hybrid |
| final_kappa_L | Dependent | - |
| iterations_used | Dependent | - |

**Implementation Sketch:**
```python
def iterative_grounding_repair(embedding: np.ndarray, sources: List[np.ndarray],
                                max_iter: int = 3, threshold: float = 0.05):
    """Iteratively repair grounding until convergence or max iterations."""

    current = embedding.copy()
    history = [compute_kappa_L(current, sources)]

    for i in range(max_iter):
        # Repair step: project toward source centroid
        centroid = np.mean(sources, axis=0)
        direction = centroid - current
        current = current + 0.3 * direction  # Step size
        current = current / np.linalg.norm(current)  # Normalize

        kappa_L = compute_kappa_L(current, sources)
        history.append(kappa_L)

        # Check convergence
        if abs(kappa_L - history[-2]) < threshold:
            break

    return current, kappa_L, i + 1
```

---

### E4: Dynamic Threshold Calibration (COVID Study-inspired)

**Inspiration:** medrxiv:2026.03.06.26347822 - COVID mortality prediction threshold analysis

**Key Insight:** "Models trained without SMOTE achieved highest AUROCs but assigned virtually no patients to mortality class at default 0.5 threshold."

**RSCT Application:**
Our κ threshold of 0.5 may be poorly calibrated for specific domains. Like the COVID study, we need domain-specific threshold calibration.

**Hypothesis H16:** Domain-calibrated thresholds improve overall accuracy by 8%

| Variable | Type | Range |
|----------|------|-------|
| domain | Independent | medical, legal, code, general |
| calibration_method | Independent | isotonic, platt, histogram |
| base_threshold | Independent | 0.4, 0.5, 0.6 |
| accuracy_improvement | Dependent | - |

**Implementation Sketch:**
```python
class DomainCalibrator:
    """Calibrate κ thresholds per domain using held-out data."""

    def __init__(self):
        self.calibrators = {}  # domain → sklearn calibrator

    def fit(self, domain: str, kappa_scores: np.ndarray, labels: np.ndarray):
        """Fit calibrator on validation set."""
        from sklearn.calibration import IsotonicRegression

        calibrator = IsotonicRegression(out_of_bounds='clip')
        calibrator.fit(kappa_scores, labels)
        self.calibrators[domain] = calibrator

    def calibrated_threshold(self, domain: str, target_precision: float = 0.95):
        """Find threshold that achieves target precision."""
        calibrator = self.calibrators.get(domain)
        if not calibrator:
            return 0.5  # Default

        # Binary search for threshold
        # ... implementation
```

---

### E5: Polar Mechanism for Embedding Perturbation

**Inspiration:** arxiv:2603.12237 - "Polar mechanism perturbs only direction on unit sphere while preserving magnitude"

**Key Insight:** "Unlike isotropic noise mechanisms, polar mechanism maintains semantic neighborhoods."

**RSCT Application:**
When testing robustness of κ calculations, use polar perturbation instead of Gaussian noise. This maintains the semantic structure while testing stability.

**Hypothesis H17:** Polar perturbation testing reveals 30% more edge cases than Gaussian

| Variable | Type | Range |
|----------|------|-------|
| perturbation_magnitude | Independent | 0.01, 0.05, 0.1 |
| perturbation_type | Independent | gaussian, polar, adversarial |
| edge_cases_found | Dependent | - |
| kappa_stability | Dependent | - |

**Implementation Sketch:**
```python
def polar_perturbation(embedding: np.ndarray, epsilon: float = 0.05):
    """Perturb embedding direction while preserving magnitude."""

    # Normalize to unit sphere
    norm = np.linalg.norm(embedding)
    unit = embedding / norm

    # Random direction perturbation
    noise = np.random.randn(*embedding.shape)
    noise = noise / np.linalg.norm(noise)

    # Project noise to be orthogonal to embedding (tangent to sphere)
    noise = noise - np.dot(noise, unit) * unit
    noise = noise / np.linalg.norm(noise)

    # Rotate on sphere by epsilon
    perturbed = np.cos(epsilon) * unit + np.sin(epsilon) * noise

    # Restore original magnitude
    return perturbed * norm
```

---

## Experiment Priority Matrix

| ID | Hypothesis | Effort | Impact | Priority |
|----|------------|--------|--------|----------|
| E1 | H13: Conflict propagation | HIGH | HIGH | P2 |
| E2 | H14: Token-level noise | MEDIUM | HIGH | P1 |
| E3 | H15: Iterative grounding | MEDIUM | MEDIUM | P3 |
| E4 | H16: Domain calibration | LOW | HIGH | P1 |
| E5 | H17: Polar perturbation | LOW | MEDIUM | P2 |

**Recommended Order:** E4 → E2 → E5 → E1 → E3

---

## Evidence Collection Template

```json
{
  "experiment": "SWARM-05",
  "hypothesis": "H1X",
  "timestamp": "2026-03-XX",
  "factors": {},
  "results": [],
  "theorems_validated": {},
  "discovery_source": {
    "paper_id": "arxiv:XXXX.XXXXX",
    "key_insight": "..."
  }
}
```

---

## Connection to Autoresearch

These experiments can be run in autoresearch mode:

```
LOOP FOREVER:
  1. Pick experiment from queue
  2. Modify policy.py with experiment parameters
  3. Run evaluation
  4. If metric improved → keep, advance to next variation
  5. If metric worse → discard, try different variation
  6. Log to results.tsv
```

---

## References

- arxiv:2603.12232 - Incremental Neural Network Verification
- arxiv:2603.12237 - STAMP: Selective Task-Aware Mechanism
- arxiv:2603.12252 - EndoCoT: Endogenous Chain-of-Thought
- medrxiv:2026.03.06.26347822 - COVID Threshold Calibration
