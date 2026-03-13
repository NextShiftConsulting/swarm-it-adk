# SWARM-03: Real-World Embedding Certification via Capacity Expansion

**Experiment ID:** SWARM-03
**Date:** 2026-03-13
**Status:** DESIGN
**Objective:** Validate that capacity expansion enables rotor certification on real-world embeddings

---

## 1. Motivation

SWARM-02 validated κ scaling on synthetic embeddings. SWARM-03 tests on **real embeddings** from production models to demonstrate practical value.

### Key Question
> Can we take embeddings from BERT, GPT-2, and fine-tuned models that currently FAIL rotor certification (κ < 50) and make them certifiable through optimal expansion?

### Unique Value Proposition
- **Adila et al.:** Expansion prevents forgetting (they never measured κ)
- **Sudjianto:** κ ≥ 50 needed for rotors (no expansion solution)
- **SWARM-03:** Combines both → certifiable real-world models

---

## 2. Hypotheses

| ID | Statement | Success Metric |
|----|-----------|----------------|
| H1 | Real embeddings have κ < 50 (are "rank-choked") | ≥60% of tested models have κ < 50 |
| H2 | Our formula correctly predicts required k | Predicted k achieves κ ≥ 50 in ≥90% of cases |
| H3 | Rotor accuracy improves after expansion | Δacc ≥ 5% on quality classification |
| H4 | k=2 (Adila default) is insufficient for some cases | ≥30% of cases need k > 2 |
| H5 | Optimal k outperforms fixed k strategies | Our formula beats k=2, k=3, k=4 on avg |
| H6 | Expansion preserves embedding semantics | Cosine similarity ≥ 0.95 before/after |

---

## 3. Embedding Sources

### 3.1 Pre-trained Models (HuggingFace)

| Model | Dimension | Expected κ | Notes |
|-------|-----------|------------|-------|
| bert-base-uncased | 768 | ~15-25 | High stable_rank |
| bert-large-uncased | 1024 | ~20-30 | Larger but similar ratio |
| gpt2 | 768 | ~20-35 | Autoregressive |
| gpt2-medium | 1024 | ~25-40 | Larger context |
| distilbert-base | 768 | ~15-25 | Distilled, may be more rank-choked |
| roberta-base | 768 | ~20-30 | Similar to BERT |
| all-MiniLM-L6-v2 | 384 | ~10-20 | Small, likely very choked |
| sentence-transformers/all-mpnet-base-v2 | 768 | ~25-40 | Sentence embeddings |

### 3.2 Fine-tuned Models (Simulated)

| Scenario | Base Model | Fine-tuning | Expected Effect |
|----------|------------|-------------|-----------------|
| Sentiment | BERT | SST-2 | κ may decrease |
| NER | BERT | CoNLL-2003 | κ may decrease |
| QA | BERT | SQuAD | κ may decrease |

### 3.3 Datasets for Embedding Extraction

| Dataset | Samples | Task |
|---------|---------|------|
| AG News | 1000 | News classification (4 classes) |
| IMDB | 1000 | Sentiment (2 classes) |
| 20 Newsgroups | 1000 | Topic classification (20 classes) |

---

## 4. Experimental Design

### 4.1 Phase 1: κ Measurement

```python
for model in MODELS:
    for dataset in DATASETS:
        embeddings = extract_embeddings(model, dataset)
        kappa = compute_kappa(embeddings)
        stable_rank = compute_stable_rank(embeddings)
        record(model, dataset, kappa, stable_rank)
```

### 4.2 Phase 2: Expansion & Certification

```python
for (model, dataset, kappa) in rank_choked_cases:  # κ < 50
    # Our formula
    k_optimal = min(ceil(65 / kappa), 5)

    # Expand embeddings
    expanded = expand_embeddings(embeddings, k_optimal)
    kappa_new = compute_kappa(expanded)

    # Test rotor
    acc_before = test_rotor(embeddings)
    acc_after = test_rotor(expanded)

    record(model, k_optimal, kappa, kappa_new, acc_before, acc_after)
```

### 4.3 Phase 3: Formula Comparison

```python
for (model, dataset, kappa) in rank_choked_cases:
    results = {}
    for k in [2, 3, 4, 5, k_optimal]:
        expanded = expand_embeddings(embeddings, k)
        acc = test_rotor(expanded)
        compute_cost = k * k  # Quadratic cost
        results[k] = (acc, compute_cost)

    # Compare: Does k_optimal achieve best acc/cost ratio?
```

### 4.4 Phase 4: Semantic Preservation

```python
for (embeddings, expanded) in expansion_pairs:
    # Check that expansion doesn't destroy meaning
    cosine_sim = cosine_similarity(
        embeddings.mean(dim=0),
        expanded.mean(dim=0)[:embeddings.shape[1]]  # First d dims
    )

    # Check classification still works
    acc_original = classify(embeddings)
    acc_expanded = classify(expanded[:, :d])  # Project back
```

---

## 5. Rotor Certification Test

### 5.1 Quality Classification Task

Given embeddings, classify into quality tiers using rotor-based decomposition:

```python
class RotorCertificationTest:
    def __init__(self, embed_dim):
        self.rotor = HybridSimplexRotor(embed_dim)

    def certify(self, embeddings, labels):
        # Apply rotor transformation
        rotated = self.rotor(embeddings)

        # Extract quality scores from simplex projection
        quality_scores = rotated[:, :3]  # First 3 dims = simplex

        # Classify based on quality
        predictions = self.classify_quality(quality_scores)

        return accuracy(predictions, labels)
```

### 5.2 Success Criteria

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| κ_after | ≥ 50 | Crossed viability threshold |
| Accuracy improvement | ≥ 5% | Rotor actually helps |
| Certification rate | ≥ 80% | Most cases become certifiable |

---

## 6. DOE Factors

### 6.1 Primary Factors

| Factor | Levels | Type |
|--------|--------|------|
| Model | 8 models | Categorical |
| Dataset | 3 datasets | Categorical |
| Expansion k | 1, 2, 3, 4, 5, optimal | Ordinal |

### 6.2 Response Variables

| Variable | Type | Range |
|----------|------|-------|
| κ_before | Continuous | [1, 100] |
| κ_after | Continuous | [1, 500] |
| rotor_accuracy | Continuous | [0, 1] |
| compute_cost | Continuous | [1, 25] |
| semantic_similarity | Continuous | [0, 1] |

### 6.3 Blocking

Block by dataset to control for data-specific effects.

---

## 7. Expected Results

### 7.1 κ Distribution (H1)

```
Expected: Most models have κ < 50 on real data

Model Distribution:
├── κ < 25:  40% (severely choked - need k≥3)
├── κ 25-50: 35% (moderately choked - k=2 may work)
└── κ > 50:  25% (already viable - no expansion needed)
```

### 7.2 Formula Accuracy (H2)

```
Expected: Our formula achieves κ ≥ 50 in 95% of cases

Cases where k=2 fails but k_optimal succeeds: ~35%
Cases where k_optimal < k=2 (saves compute): ~20%
```

### 7.3 Accuracy Improvement (H3)

```
Expected: 8-15% accuracy improvement when κ crosses 50

Before expansion: 75-82% (rotor struggling)
After expansion:  88-94% (rotor working)
```

---

## 8. Deliverables

1. **Evidence files:** `evidence/h1_real_kappa_distribution.json`, etc.
2. **Figures:**
   - `fig1_kappa_by_model.png` - Bar chart of κ per model
   - `fig2_certification_rate.png` - % certifiable before/after
   - `fig3_formula_comparison.png` - Our k vs fixed k
   - `fig4_accuracy_improvement.png` - Before/after rotor accuracy
3. **Summary:** `SWARM03_RESULTS_SUMMARY.md`

---

## 9. Success Criteria

| Hypothesis | Pass Condition |
|------------|----------------|
| H1 | ≥60% of model/dataset pairs have κ < 50 |
| H2 | Formula achieves target κ in ≥90% of cases |
| H3 | Mean accuracy improvement ≥ 5% |
| H4 | ≥30% of cases require k > 2 |
| H5 | Formula outperforms fixed k on ≥70% of cases |
| H6 | Mean semantic similarity ≥ 0.95 |

**Overall Pass:** ≥5/6 hypotheses supported

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Real embeddings have κ > 50 already | Include fine-tuned models, smaller models |
| Expansion destroys semantics | Monitor cosine similarity, test classification |
| Compute constraints | Start with subset, use GPU batching |
| Model download issues | Use cached HuggingFace models |

---

## Appendix: Code Structure

```
SWARM-03/
├── DOE_SWARM03_REAL_EMBEDDINGS.md  (this file)
├── run_experiment.py
├── evidence/
│   ├── h1_real_kappa_distribution.json
│   ├── h2_formula_accuracy.json
│   ├── h3_accuracy_improvement.json
│   ├── h4_k2_insufficient.json
│   ├── h5_formula_comparison.json
│   ├── h6_semantic_preservation.json
│   └── swarm_evidence_SWARM-03.json
└── results/
    └── figures/
        ├── fig1_kappa_by_model.png
        ├── fig2_certification_rate.png
        ├── fig3_formula_comparison.png
        └── fig4_accuracy_improvement.png
```
