# DOE: SWARM-06 Jailbreak Detection via RSCT Certificate Decomposition

**Experiment ID:** SWARM-06
**Domain:** RSCT/Security/ML
**Status:** ACTIVE
**Last Updated:** 2026-03-16
**Conference Target:** NeurIPS 2026 / ACM CCS 2026

---

## Abstract

This experiment series investigates whether RSCT certificate decomposition (R, S, N simplex)
provides competitive or superior jailbreak detection compared to SOTA transformer-based
classifiers, while offering interpretability and compositional advantages. We benchmark
against established models (Prompt-Guard-86M, Jailbreak-Detector-Large) using standardized
datasets from TrustAIRLab and semantic-router.

---

## Research Questions

1. **RQ1 (Accuracy):** Can RSCT rotor match SOTA accuracy (>95%) after security-specific training?
2. **RQ2 (Interpretability):** Does RSN decomposition provide actionable signals beyond binary classification?
3. **RQ3 (Efficiency):** What is the latency/throughput tradeoff vs transformer classifiers?
4. **RQ4 (Generalization):** Does multi-source training improve cross-domain robustness?
5. **RQ5 (Composability):** Can RSN certificates integrate with downstream κ-gate enforcement?

---

## Hypotheses

### H1: Baseline RSCT Performance
**Statement:** Pre-trained YRSN rotor achieves <60% accuracy on jailbreak detection without fine-tuning.

| Variable Type | Description |
|---------------|-------------|
| Independent | Rotor checkpoint (text64, universal64) |
| Dependent | Classification accuracy, F1, FPR, FNR |
| Control | Dataset (unified_test.jsonl), threshold (N=0.5) |

**Metrics:**
- `accuracy`: Expected = 0.40-0.60
- `f1_score`: Expected = 0.30-0.50
- `fnr`: Expected > 0.40 (missing jailbreaks)

**Evidence Required:** `evidence/h1_baseline_rotor.json`

---

### H2: RSN Signature Hypothesis
**Statement:** Jailbreaks exhibit distinct RSN signature: R < 0.4 AND S > 0.4 (manipulation pattern).

| Variable Type | Description |
|---------------|-------------|
| Independent | Sample type (jailbreak vs benign) |
| Dependent | RSN distribution statistics |
| Control | Rotor checkpoint, embedding model |

**Metrics:**
- `jailbreak_R_mean`: Expected < 0.40
- `jailbreak_S_mean`: Expected > 0.40
- `benign_R_mean`: Expected > 0.50
- `effect_size`: Cohen's d > 0.8 (large effect)

**Evidence Required:** `evidence/h2_rsn_signature.json`

---

### H3: Fine-tuned Rotor Accuracy
**Statement:** Security-fine-tuned rotor achieves >90% accuracy on jailbreak detection.

| Variable Type | Description |
|---------------|-------------|
| Independent | Training data size (1K, 2K, 5K samples) |
| Dependent | Test accuracy, F1, precision, recall |
| Control | Architecture (HybridSimplexRotor), optimizer (Adam) |

**Metrics:**
- `accuracy`: Expected > 0.90
- `f1_score`: Expected > 0.88
- `precision`: Expected > 0.90
- `recall`: Expected > 0.85

**Evidence Required:** `evidence/h3_finetuned_accuracy.json`

---

### H4: SOTA Comparison
**Statement:** Fine-tuned RSCT rotor achieves accuracy within 5% of SOTA classifiers.

| Variable Type | Description |
|---------------|-------------|
| Independent | Model (RSCT, Prompt-Guard-86M, Jailbreak-Detector-Large, BERT-classifier) |
| Dependent | Accuracy, F1, latency |
| Control | Test dataset (unified_test.jsonl) |

**Metrics:**
- `accuracy_gap`: Expected < 0.05 (vs SOTA)
- `f1_gap`: Expected < 0.05
- `latency_ratio`: Expected < 2.0x SOTA

**Evidence Required:** `evidence/h4_sota_comparison.json`

---

### H5: Interpretability Advantage
**Statement:** RSN decomposition provides 3 actionable signals vs binary classification.

| Variable Type | Description |
|---------------|-------------|
| Independent | Model output type (RSN vs binary logit) |
| Dependent | Interpretability metrics, human evaluation |
| Control | Same test samples |

**Metrics:**
- `signal_count`: Expected = 3 (R, S, N) vs 1 (logit)
- `threshold_tunability`: N_max, R_min, S_max independently tunable
- `gate_compatibility`: Integrates with κ-gate enforcement

**Evidence Required:** `evidence/h5_interpretability.json`

---

### H6: Cross-Domain Generalization
**Statement:** Multi-source training improves generalization by >5% on held-out domains.

| Variable Type | Description |
|---------------|-------------|
| Independent | Training sources (single vs multi) |
| Dependent | Accuracy on held-out platform (e.g., Discord only) |
| Control | Total training samples |

**Metrics:**
- `single_source_acc`: Baseline (jackhhao only)
- `multi_source_acc`: Expected > single + 0.05
- `domain_gap`: Expected < 0.10

**Evidence Required:** `evidence/h6_generalization.json`

---

### H7: Threshold Optimization
**Statement:** Autoloop optimization improves F1 by >3% over default thresholds.

| Variable Type | Description |
|---------------|-------------|
| Independent | Threshold values (N_max, R_min, S_max) |
| Dependent | F1 score |
| Control | Architecture, dataset |

**Metrics:**
- `baseline_f1`: Default thresholds
- `optimized_f1`: Expected > baseline + 0.03
- `iterations`: Number of autoloop iterations

**Evidence Required:** `evidence/h7_threshold_optimization.json`

---

### H8: Certificate Integration
**Statement:** RSN certificates pass κ-gate validation and integrate with multi-agent pipelines.

| Variable Type | Description |
|---------------|-------------|
| Independent | Certificate source (rotor output) |
| Dependent | Gate passage rate, κ values |
| Control | Gate thresholds |

**Metrics:**
- `simplex_valid`: R + S + N = 1 (100% compliance)
- `kappa_range`: Expected 0.3-0.8
- `gate_compatibility`: RSCT 4-gate passage

**Evidence Required:** `evidence/h8_certificate_integration.json`

---

## Data Sources

| Source | Type | Size | Split |
|--------|------|------|-------|
| jackhhao/jailbreak-classification | HuggingFace | 1,044 | Balanced |
| llm-semantic-router/jailbreak-detection | HuggingFace | 2,480 | Balanced |
| TrustAIRLab/in-the-wild-jailbreak-prompts | HuggingFace | 15,140 | Subsampled |
| **Unified Blend** | Combined | 7,739 | 70/15/15 |

### Dataset Statistics
- **Train:** 5,417 samples (2,219 jailbreak, 41%)
- **Validation:** 1,161 samples (480 jailbreak, 41%)
- **Test:** 1,161 samples (473 jailbreak, 41%)
- **Sources:** jackhhao, semantic_router, trustai_discord, trustai_reddit, trustai_website

---

## Experimental Protocol

### Phase 1: Baseline Evaluation (H1, H2)
1. Load pre-trained YRSN rotor (`trained_rotor_text64.pt`)
2. Extract RSN for all test samples
3. Compute RSN distribution statistics
4. Evaluate with default N≥0.5 threshold
5. Evaluate with manipulation gate (R<0.4 & S>0.4)
6. Record evidence

### Phase 2: RSN Signature Analysis (H2)
1. Group samples by label (jailbreak vs benign)
2. Compute RSN statistics per group
3. Statistical tests (t-test, Cohen's d)
4. Visualize RSN ternary distribution
5. Identify decision boundary

### Phase 3: Security Fine-tuning (H3)
1. Prepare training data with labels (jailbreak → high N)
2. Fine-tune rotor on security data
3. Ablation: vary training size (1K, 2K, 5K)
4. Evaluate on held-out test set
5. Save checkpoint (`trained_rotor_security64.pt`)

### Phase 4: SOTA Benchmarking (H4)
1. Load SOTA models from HuggingFace
2. Run inference on same test set
3. Compute metrics: accuracy, F1, precision, recall
4. Measure latency per model
5. Statistical significance testing

### Phase 5: Interpretability Evaluation (H5)
1. Compare output dimensionality
2. Demonstrate threshold tunability
3. Show gate integration
4. (Optional) Human evaluation study

### Phase 6: Generalization Testing (H6)
1. Train on single source, test on others
2. Train on multiple sources, test on all
3. Compute cross-domain accuracy
4. Measure domain gap

### Phase 7: Threshold Optimization (H7)
1. Configure autoloop for F1 optimization
2. Run 100+ iterations
3. Track best thresholds
4. Validate on test set

### Phase 8: Certificate Validation (H8)
1. Verify simplex constraint
2. Compute κ values
3. Test gate passage
4. Multi-agent pipeline integration

---

## Models to Benchmark

| Model | Source | Size | Expected Acc |
|-------|--------|------|--------------|
| YRSN Rotor (baseline) | Local | ~1M | 55% |
| YRSN Rotor (fine-tuned) | Local | ~1M | 90%+ |
| madhurjindal/Jailbreak-Detector-Large | HuggingFace | ~350M | 98% |
| meta-llama/Prompt-Guard-86M | HuggingFace | 86M | 95% |
| jackhhao/jailbreak-classifier | HuggingFace | 110M | 92% |
| Keyword Baseline | Local | N/A | 60% |

---

## Dashboard Telemetry

### Expected Certificate Ranges

| Metric | Jailbreak | Benign | Threshold |
|--------|-----------|--------|-----------|
| R | 0.25-0.40 | 0.50-0.75 | R_min=0.35 |
| S | 0.40-0.55 | 0.10-0.30 | S_max=0.45 |
| N | 0.15-0.30 | 0.15-0.35 | N_max=0.50 |
| α (quality) | 0.45-0.70 | 0.60-0.85 | - |

### Gate Configuration

| Gate | Metric | Threshold | Action |
|------|--------|-----------|--------|
| 1 | N | ≥ 0.50 | REJECT |
| 2 | coherence | < 0.40 | BLOCK |
| 3 | κ | < κ_req(σ) | RE_ENCODE |
| Custom | R<0.35 & S>0.45 | - | BLOCK (manipulation) |

---

## Success Criteria

| Hypothesis | Criterion | p-value Req | Status |
|------------|-----------|-------------|--------|
| H1 | Baseline accuracy < 60% | - | PENDING |
| H2 | Cohen's d > 0.8 for RSN separation | < 0.001 | PENDING |
| H3 | Fine-tuned accuracy > 90% | < 0.01 | PENDING |
| H4 | Accuracy gap < 5% vs SOTA | < 0.05 | PENDING |
| H5 | 3 tunable signals | - | PENDING |
| H6 | Multi-source gain > 5% | < 0.05 | PENDING |
| H7 | Autoloop F1 gain > 3% | < 0.05 | PENDING |
| H8 | 100% simplex compliance | - | PENDING |

---

## Proofs Required

| Proof | Location | Status |
|-------|----------|--------|
| Simplex constraint (R+S+N=1) | `proofs/proof_simplex.md` | PENDING |
| RSN → κ computation | `proofs/proof_kappa.md` | PENDING |
| Gate ordering theorem | `proofs/proof_gates.md` | PENDING |
| Manipulation signature derivation | `proofs/proof_manipulation.md` | PENDING |

---

## Deliverables

### Code
- [ ] `benchmarks/benchmark_all.py` - Main benchmark script
- [ ] `benchmarks/evaluate_rotor.py` - YRSN rotor evaluation
- [ ] `benchmarks/evaluate_hf.py` - HuggingFace model evaluation
- [ ] `benchmarks/train_security_rotor.py` - Fine-tuning script
- [ ] `autoloop/config.yaml` - Threshold optimization config
- [ ] `autoloop/evaluate.py` - Autoloop evaluator

### Figures
- [ ] `results/figures/fig_rsn_ternary.png` - RSN simplex visualization
- [ ] `results/figures/fig_benchmark_comparison.png` - Model comparison
- [ ] `results/figures/fig_roc_curves.png` - ROC curves for all models
- [ ] `results/figures/fig_threshold_optimization.png` - Autoloop progress
- [ ] `results/figures/fig_cross_domain.png` - Generalization heatmap

### Tables
- [ ] `results/tables/benchmark_results.csv` - Main results
- [ ] `results/tables/rsn_statistics.csv` - RSN distribution stats
- [ ] `results/tables/ablation_training_size.csv` - Training ablation

### Evidence
- [ ] `evidence/h1_baseline_rotor.json`
- [ ] `evidence/h2_rsn_signature.json`
- [ ] `evidence/h3_finetuned_accuracy.json`
- [ ] `evidence/h4_sota_comparison.json`
- [ ] `evidence/h5_interpretability.json`
- [ ] `evidence/h6_generalization.json`
- [ ] `evidence/h7_threshold_optimization.json`
- [ ] `evidence/h8_certificate_integration.json`

---

## Timeline (Phases, not dates)

| Phase | Description | Hypotheses |
|-------|-------------|------------|
| 1 | Baseline & RSN Analysis | H1, H2 |
| 2 | Security Fine-tuning | H3 |
| 3 | SOTA Benchmarking | H4 |
| 4 | Interpretability & Integration | H5, H8 |
| 5 | Generalization & Optimization | H6, H7 |
| 6 | Publication Preparation | All |

---

## References

1. "Do Anything Now": Characterizing and Evaluating In-The-Wild Jailbreak Prompts (CCS 2024)
2. JailbreakBench: An Open Robustness Benchmark (NeurIPS 2024)
3. RSCT: Representational Stability and Compatibility Theory (YRSN)
4. Prompt-Guard: Protecting LLMs from Prompt Injection (Meta)

---

## Authors

- YRSN Research Team
- Generated: 2026-03-16
