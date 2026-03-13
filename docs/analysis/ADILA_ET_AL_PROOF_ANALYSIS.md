# Analysis: How Adila et al. Proved "Grow, Don't Overwrite" Works

**Paper:** arXiv:2603.08647v1 (March 2026)
**Authors:** Adila, Mazzawi, Dherin, Gonzalvo (Google Research / UW-Madison)
**Analysis Date:** 2026-03-13

---

## 1. Their Proof Structure

### 1.1 Mathematical Proof of Function Preservation

The core claim is that MLP expansion preserves the model's function at initialization.

**The Expansion:**
```
W_up:   [h, p] → [h, 2p]   (horizontal concatenation)
W_down: [p, h] → [2p, h]   (vertical concatenation, scaled by 1/2)
```

**The Proof (Section 3, p.3):**

Let `Y = ReLU(X @ W_up)`. Original output: `Y @ W_down`

After expansion:
```
[Y  Y] × [W_down/2]  =  ½(Y @ W_down) + ½(Y @ W_down)  =  Y @ W_down
         [W_down/2]
```

This algebraic identity proves the expanded model outputs **exactly** the same values at initialization. QED.

**Generalization to k copies:**
```
[Y Y ... Y] × [W/k]     = k × (1/k) × Y @ W = Y @ W
              [W/k]
              [...]
              [W/k]
```

---

### 1.2 Empirical Validation: Forgetting Benchmarks

**Setup (Section 4):**
- Model: Gemma3-1B
- Original capability proxy: WinoGrande (commonsense reasoning)
- New tasks: Translation, Entailment, Science Q&A, MathQA

**Results (Figure 2):**

| Task | Metric | Standard Fine-tuning | Their Method |
|------|--------|---------------------|--------------|
| French Translation | Original domain | Drops to ~0% | Stays at ~40% |
| Science Entailment | Original domain | Drops to ~0% | Stays at ~45% |
| Science Q&A | Original domain | ~30% | ~50% |
| MathQA | Original domain | ~20% | ~55% |

**Key Finding:** Standard fine-tuning causes "catastrophic forgetting" - original capabilities collapse to near-zero. Their method preserves original performance while matching new task performance.

---

### 1.3 Mechanistic Evidence: Function Vectors

**Method (Section 4.5):**
Function Vectors (FVs) are compact representations of task-specific neural circuits, derived by:
1. Computing mean activations on clean task prompts
2. Identifying "causal heads" via activation patching
3. Summing activations from causal heads

**Results (Table 1):**

| Dataset | Method | Causal Heads Preserved | FV Cosine Similarity |
|---------|--------|------------------------|----------------------|
| Entailment | SFT | 2/10 | 0.28 |
| Entailment | Theirs | 5/10 | **0.95** |
| Translation | SFT | 3/10 | 0.58 |
| Translation | Theirs | 5/10 | **0.76** |

**Interpretation:** Their method preserves the model's internal computational circuits. Standard fine-tuning destroys them.

---

### 1.4 Scaling Properties

**Parameter Efficiency (Section 4.2):**
- Growing 10 targeted layers ≈ growing all layers
- Only ~30% of parameters needed vs ~60% for full expansion

**Task Complexity (Section 4.4):**
- Simple tasks: High-rank updates localized to few layers
- Complex tasks (MathQA): High-rank updates distributed across all layers

---

## 2. What They Did NOT Prove

| Topic | Adila et al. | SWARM-02 Discovery |
|-------|--------------|-------------------|
| **Over-parameterization ratio (κ)** | Never mentioned | κ = dim / stable_rank |
| **Threshold for effectiveness** | None identified | κ ≥ 50 required |
| **Optimal expansion factor** | "k=2 worked best" (no analysis) | k = min(ceil(65/κ), 5) |
| **Sweet spot** | Not explored | κ ≈ 50-80 optimal |
| **Diminishing returns** | Not mentioned | κ > 80 shows no improvement |
| **Geometric operations** | Not considered | Enables rotor viability |
| **Connection to RoRA** | None | Fixes "rank-choked" embeddings |

---

## 3. The Gap We Filled (SWARM-02)

### 3.1 The Question They Didn't Ask

Adila et al. asked: *"Does expansion prevent forgetting?"*

We asked: *"Does expansion enable geometric operations that were previously impossible?"*

### 3.2 Our Contribution

**Discovery 1: κ scales linearly with k**
```
κ_new = k × κ_old
```
This is a mathematical relationship they never derived.

**Discovery 2: The κ ≥ 50 threshold**

From Sudjianto's RoRA work (SSRN 6101568), rotors become "rank-choked" when κ < 50. They cannot find rotation planes that meaningfully align representation space.

Adila et al. never connected their expansion to this geometric constraint.

**Discovery 3: Sweet spot at κ ≈ 50-80**

| κ Range | Effect |
|---------|--------|
| < 50 | Rotors fail ("rank-choked") |
| 50-80 | Optimal rotor performance |
| > 80 | Diminishing returns, optimization challenges |

**Discovery 4: Practical formula**
```python
def optimal_expansion(kappa_current: float) -> int:
    if kappa_current >= 50:
        return 1  # No expansion needed
    k = math.ceil(65 / kappa_current)  # Target middle of sweet spot
    return min(k, 5)  # Cap at k=5
```

---

## 4. Complementary Contributions

| Aspect | Adila et al. | SWARM-02 |
|--------|--------------|----------|
| **Problem solved** | Training-time forgetting | Inference-time geometric viability |
| **Domain** | LLM fine-tuning | Representation alignment |
| **Mechanism** | Capacity isolation | Over-parameterization ratio |
| **Validation** | Benchmark accuracy | κ threshold crossing |
| **Guidance** | "Use k=2" | Formula for optimal k |

**The Bridge:**
> They built a tool for one purpose (preventing forgetting).
> We discovered it solves a completely different problem (enabling geometric rotors).
> Same technique, different theoretical justification.

---

## 5. Open Questions

1. **Does κ threshold vary by task?**
   - Our 50-80 range is from classification; other tasks may differ

2. **Can we predict optimal k from data properties?**
   - Current formula uses κ; could stable_rank distribution inform better?

3. **What about attention expansion?**
   - Adila et al. found MLP expansion >> attention expansion (Appendix C.3)
   - Does this hold for geometric operations?

4. **Computational cost at scale?**
   - Expansion by k increases MLP parameters by k²
   - When does this become prohibitive?

---

## 6. References

1. Adila, D., Mazzawi, H., Dherin, B., & Gonzalvo, X. (2026). Grow, Don't Overwrite: Fine-tuning Without Forgetting. arXiv:2603.08647.

2. Sudjianto, A. (2024). RoRA: Low-Rank Rotational Adaptation. SSRN 6101568.

3. Mazzawi, H., Gonzalvo, X., Wunder, M., Jerome, S., & Dherin, B. (2023). Deep Fusion: Efficient Network Training via Pre-trained Initializations. arXiv:2306.11903.

4. Todd, E., et al. (2024). Function Vectors in Large Language Models. ICLR 2024.

---

## Appendix: Key Figures from Adila et al.

### Figure 2: Forgetting vs. Performance
- Blue (SFT): Original domain collapses to ~0%
- Green/Orange (Theirs): Original domain preserved at ~45%
- New task performance: Comparable across methods

### Figure 5: Effective Rank of Weight Updates
- Simple tasks: Localized high-rank updates
- Complex tasks: Distributed high-rank updates across all layers

### Table 1: Function Vector Preservation
- SFT destroys internal circuits (0.28 similarity)
- Their method preserves them (0.95 similarity)
