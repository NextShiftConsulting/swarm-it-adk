# PROPOSAL: κ-Based Jailbreak Detection via Representation-Solver Compatibility

**Proposal ID:** SWARM-06-P1
**Status:** DRAFT - AWAITING APPROVAL
**Author:** SWARM Research Team
**Date:** 2026-03-16
**Related DOE:** DOE_SWARM-06_Jailbreak_Detection_Benchmark.md

---

## Executive Summary

This proposal recommends pivoting from RSN-based classification to **κ-based compatibility detection** for jailbreak identification. The RSN approach has failed to achieve target accuracy (62-77% vs 90% target) because jailbreaks are semantically "high-quality text" - coherent, persuasive, well-written. The κ-based approach measures **compatibility with a safe interaction solver**, where jailbreaks are fundamentally incompatible.

---

## Problem Statement

### Current Approach: RSN Classification

The current approach uses HybridSimplexRotor to decompose text into:
- **R** (Relevant): Signal aligned with task
- **S** (Superfluous): Off-topic but coherent
- **N** (Noise): Incoherent/garbage

**Results:**
```
Frozen Rotor RSN (both classes):
  R: 0.419±0.150
  S: 0.317±0.121
  N: 0.264±0.117

Certificate Classifier Accuracy: 62-64%
Retrained Rotor Accuracy: 77%
Target: 90%
```

### Why RSN Fails

The rotor was trained on **text quality semantics**:
- R = "coherent and relevant to topic"
- S = "coherent but off-topic"
- N = "incoherent noise"

**Jailbreaks are often high-quality text:**
- Well-written, grammatically correct
- Persuasive and coherent
- Carefully crafted to bypass filters

The rotor correctly identifies jailbreaks as "coherent text" (high R, low N) - because they ARE coherent text. The semantic meaning of jailbreak vs. benign is orthogonal to text quality.

### The Fundamental Issue

RSN measures **"What is in this representation?"** (content quality).

We need to measure **"Is this representation compatible with safe AI interaction?"** (solver compatibility).

---

## Proposed Solution: κ-Based Compatibility Detection

### Theoretical Foundation

From RSCT (Representation-Solver Compatibility Theory):

```
κ(E, S) = D* / D

Where:
  D* = reference difficulty (optimal solver steps)
  D  = actual difficulty with encoding E and solver S
  κ  = compatibility measure ∈ [0, 1]
```

**Key insight:** κ measures whether a representation is COMPATIBLE with a solver, not whether the representation is "good quality."

### Application to Jailbreak Detection

Define the **"Safe Interaction Solver" (S_safe)**:
- The solver that produces safe, helpful AI responses
- Trained on benign prompt-response pairs
- Represents the target distribution of safe interactions

**Hypothesis:**
- Benign prompts → HIGH κ (compatible with S_safe)
- Jailbreak prompts → LOW κ (incompatible with S_safe)

### Architecture

```
                    ┌─────────────────────────────────────┐
                    │         TRAINING PHASE              │
                    ├─────────────────────────────────────┤
                    │  Benign Exemplars                   │
                    │         ↓                           │
                    │  SentenceTransformer (384d)         │
                    │         ↓                           │
                    │  TextMLP384to64 (64d)               │
                    │         ↓                           │
                    │  TrainingDistributionStats          │
                    │  (centroid, covariance, bounds)     │
                    └─────────────────────────────────────┘
                                   ↓
                    ┌─────────────────────────────────────┐
                    │         INFERENCE PHASE             │
                    ├─────────────────────────────────────┤
                    │  New Prompt                         │
                    │         ↓                           │
                    │  SentenceTransformer (384d)         │
                    │         ↓                           │
                    │  TextMLP384to64 (64d)               │
                    │         ↓                           │
                    │  GeometryCompatibilityChecker       │
                    │  (compute κ vs S_safe distribution) │
                    │         ↓                           │
                    │  κ < threshold → JAILBREAK          │
                    │  κ ≥ threshold → BENIGN             │
                    └─────────────────────────────────────┘
```

### κ Computation Details

Using `GeometryCompatibilityChecker` from YRSN:

1. **Mahalanobis Distance (κ₁):**
   ```
   d² = (x - μ)ᵀ Σ⁻¹ (x - μ)
   κ₁ = exp(-d² / 2σ²)
   ```
   Measures: How far is this embedding from the safe centroid?

2. **Norm Consistency (κ₃):**
   ```
   κ₃ = exp(-|‖x‖ - μ_norm|² / σ_norm²)
   ```
   Measures: Does this embedding have expected magnitude?

3. **Combined κ:**
   ```
   κ = geometric_mean(κ₁, κ₃)
   ```

### Why This Should Work

| Property | Benign Prompts | Jailbreak Prompts |
|----------|---------------|-------------------|
| Semantic content | Safe queries, normal requests | Manipulation, bypass attempts |
| Embedding location | Near safe centroid | Far from safe centroid |
| Distribution fit | In-distribution | Out-of-distribution |
| κ value | HIGH (0.7-1.0) | LOW (0.0-0.4) |

---

## Anti-MARL Concerns

### What is MARL Risk?

Multi-Agent Reinforcement Learning (MARL) attacks exploit:
1. **Gaming metrics**: Adversaries learn to produce inputs that score well on detectors
2. **Distribution shift**: Attackers observe detector behavior and adapt
3. **Collusion**: Multiple agents coordinate to find detector blind spots
4. **Reward hacking**: Optimizing for detector output rather than true safety

### Concern 1: Adversarial Adaptation

**Risk:** Attackers could learn to craft jailbreaks that appear "in-distribution" with benign prompts.

**Mitigations:**
1. **κ is geometry-based, not keyword-based**: Cannot be gamed by adding "safe" words
2. **Centroid is computed from real benign data**: Moving toward it means actually being benign-like
3. **Multi-signal fusion**: Combine κ with RSN, coherence, and other signals
4. **Periodic retraining**: Update S_safe distribution as attack patterns evolve

### Concern 2: Distribution Shift

**Risk:** Benign prompt distribution may shift over time, causing false positives.

**Mitigations:**
1. **Rolling baseline**: Update TrainingDistributionStats with recent benign traffic
2. **Confidence intervals**: Flag uncertain cases for human review
3. **Multi-source training**: Diverse benign exemplars from multiple domains
4. **Drift monitoring**: Track κ distribution over time, alert on shifts

### Concern 3: Adversarial Embedding Manipulation

**Risk:** Sophisticated attackers could craft inputs that project to safe regions in embedding space.

**Mitigations:**
1. **Multiple embedding models**: Ensemble across different encoders
2. **Layer-wise analysis**: Check compatibility at multiple network depths
3. **Semantic consistency**: Verify κ is consistent across paraphrases
4. **Randomized projections**: Add stochastic defense layers

### Concern 4: Collusion Detection

**Risk:** Multiple agents could probe the system to map decision boundaries.

**Mitigations:**
1. **Rate limiting**: Limit queries per user/session
2. **Behavioral analysis**: Detect systematic probing patterns
3. **Noise injection**: Add calibrated noise to κ outputs (differential privacy)
4. **Honeypot responses**: Return misleading signals for suspicious patterns

### RSCT-Native Defenses

The RSCT framework provides built-in protections:

| Defense | Mechanism | Location |
|---------|-----------|----------|
| Gate 1 (N-gate) | Reject high noise | Pre-κ filter |
| Gate 2 (Coherence) | Reject incoherent | Pre-κ filter |
| Gate 3 (κ-gate) | Main compatibility check | This proposal |
| Gate 4 (Decision) | Final admissibility | Post-κ synthesis |

**Layered defense:** Even if κ is fooled, other gates provide redundancy.

### Formal Security Analysis

**Theorem (Bounded Attack Surface):**
For an adversary to achieve κ ≥ κ_threshold, they must produce an embedding x such that:
```
(x - μ_safe)ᵀ Σ_safe⁻¹ (x - μ_safe) ≤ -2σ² ln(κ_threshold)
```

This defines an ellipsoid in embedding space. To enter this ellipsoid while maintaining jailbreak semantics requires:
1. Semantic content that is jailbreak-like
2. Embedding that is benign-like

**These are in tension:** Embedding models are trained to separate semantically different content. An attacker cannot easily have both properties simultaneously.

---

## Experimental Design

### Phase 1: S_safe Distribution Estimation

1. **Data:** Use benign subset of unified dataset (4,567 samples)
2. **Process:**
   - Extract 64d embeddings via frozen projection
   - Compute TrainingDistributionStats (centroid, covariance)
   - Save as `s_safe_distribution.npz`

### Phase 2: κ Threshold Optimization

1. **Method:** Grid search on validation set
2. **Metric:** F1 score (balance precision/recall)
3. **Range:** κ_threshold ∈ [0.1, 0.9] with 0.05 steps

### Phase 3: Evaluation

1. **Test set:** unified_test.jsonl (1,161 samples)
2. **Metrics:** Accuracy, precision, recall, F1, AUC-ROC
3. **Comparison:** vs. RSN-based, vs. SOTA (Prompt-Guard, Jailbreak-Detector-Large)

### Phase 4: Robustness Testing

1. **Adversarial perturbations:** Paraphrase attacks
2. **Distribution shift:** Test on held-out sources
3. **Ensemble:** Multi-encoder κ fusion

---

## Success Criteria

| Criterion | Target | Rationale |
|-----------|--------|-----------|
| Test Accuracy | > 90% | H3 hypothesis requirement |
| F1 Score | > 0.88 | Balance precision/recall |
| False Positive Rate | < 5% | Minimize benign blocking |
| False Negative Rate | < 10% | Minimize jailbreak escape |
| Adversarial Robustness | > 85% | Resist paraphrase attacks |

---

## Resource Requirements

| Resource | Quantity | Purpose |
|----------|----------|---------|
| Compute | CPU (local) | No GPU needed for κ computation |
| Data | Existing unified dataset | Already downloaded |
| Time | ~2 hours | Implementation + evaluation |
| Dependencies | YRSN core (frozen) | GeometryCompatibilityChecker |

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| κ doesn't separate classes | Medium | High | Fall back to ensemble with RSN |
| Adversarial bypass discovered | Medium | High | Layered defense, periodic retraining |
| Distribution shift causes drift | Low | Medium | Rolling baseline, drift monitoring |
| Computational overhead too high | Low | Low | κ is O(d²), manageable |

---

## Alignment with RSCT Theory

This proposal is grounded in core RSCT principles:

1. **P15 (Universal Rotor):** Uses HybridSimplexRotor for embedding projection
2. **κ = D*/D:** Direct implementation of representation-solver compatibility
3. **Dual-Graph Morph:** S_safe defines G_S, embeddings define G_R, κ measures morph quality
4. **Gate 3 (κ-gate):** Standard RSCT gate for compatibility checking
5. **Certificate integration:** κ can be added to YRSNCertificate

---

## Approval Request

**Request:** Approval to implement κ-based jailbreak detection as SWARM-06 Phase 2.

**Deliverables:**
1. `train_kappa_classifier.py` - Build S_safe distribution and evaluate
2. `evidence/h3_kappa_detection.json` - Results evidence
3. Updated DOE with κ-based hypothesis

**Timeline:** Implementation ready within current session upon approval.

---

## Appendix: Code Sketch

```python
from yrsn.core.decomposition.geometry_compatibility import (
    GeometryCompatibilityChecker,
    TrainingDistributionStats,
)

# Phase 1: Build S_safe distribution from benign exemplars
benign_embeddings = extract_embeddings(benign_texts, extractor)
benign_64d = projection(torch.tensor(benign_embeddings))
s_safe_stats = TrainingDistributionStats.from_features(benign_64d.numpy())

# Phase 2: Create compatibility checker
checker = GeometryCompatibilityChecker(
    training_stats=s_safe_stats,
    # rotor not needed for pure κ computation
)

# Phase 3: Classify new prompts
def classify(prompt_embedding):
    kappa = checker.estimate_omega(prompt_embedding)
    return "jailbreak" if kappa < KAPPA_THRESHOLD else "benign"
```

---

## References

1. RSCT Theory: docs/papers/gap_analysis/RSCT_YRSN_IMPLEMENTATION_APPENDIX.md
2. GeometryCompatibilityChecker: yrsn/core/decomposition/geometry_compatibility.py
3. κ Gateway: yrsn/core/decomposition/kappa_gateway.py
4. Patent FIG. 25: Dual-graph morph repair (G_R → G_S mapping)

---

**END OF PROPOSAL**
