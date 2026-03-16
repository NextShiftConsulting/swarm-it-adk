# SWARM-06: Jailbreak Detection with DyTopo Routing

**Status**: Complete (Experimental)
**Date**: 2026-03-16
**Target**: 90% accuracy (Achieved: 87.1%)

## Overview

SWARM-06 implements jailbreak detection using RSCT-based classification with DyTopo-inspired dynamic topology routing. The experiment validates 128d embedding support for improved semantic preservation.

## Key Results

| Model | Accuracy | AUC | Notes |
|-------|----------|-----|-------|
| Hybrid Classifier (384d) | 85.4% | 0.923 | SentenceTransformer embeddings |
| Titan Swarm (1024d) | 86.2% | 0.928 | Bedrock Titan v2 embeddings |
| Ensemble (Titan+ST) | **87.1%** | 0.931 | Best result |
| 128d Projection | 86.0% | - | Contrastive training |

### RSN Separation (128d Rotor)

| Prompt Type | R (Relevance) | S (Stability) | N (Noise) |
|-------------|---------------|---------------|-----------|
| Benign | 0.53 | 0.27 | 0.20 |
| Jailbreak | 0.17 | 0.27 | **0.57** |

## Architecture

```
Text Input
    │
    ▼
┌─────────────────────────┐
│ SentenceTransformer     │  384d embeddings
│ (all-MiniLM-L6-v2)      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ TextProjection128       │  384d → 128d
│ (contrastive trained)   │
└───────────┬─────────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
┌─────────┐   ┌─────────────┐
│Classifier│   │HybridSimplex│
│ (MLP)   │   │   Rotor     │
└────┬────┘   └──────┬──────┘
     │               │
     ▼               ▼
  Probability     RSN (R,S,N)
     │               │
     └───────┬───────┘
             │
             ▼
    ┌─────────────────┐
    │ DyTopo Router   │
    │ (N-gate + κ)    │
    └────────┬────────┘
             │
             ▼
      ALLOW / BLOCK
```

## Files

### Adapters
- `adapters/jailbreak_detector.py` - Main detector with rotor_config integration
- `adapters/jailbreak_detector_titan.py` - Fast Bedrock Titan variant
- `adapters/dytopo_defense_128d.py` - DyTopo router with 64d/128d hot-switching

### Training Scripts
- `benchmarks/train_hybrid_rsct_classifier.py` - Hybrid classifier training
- `benchmarks/train_ensemble_classifier.py` - Titan+ST ensemble
- `benchmarks/train_swarm_titan.py` - Parallel Titan embedding extraction
- `benchmarks/train_projection_128d.py` - 128d projection training
- `benchmarks/train_rotor_128d.py` - 128d rotor training

### Data
- `data/jailbreak_prompts.jsonl` - Jailbreak examples
- `data/benign_prompts.jsonl` - Benign examples
- `embeddings/st_384d.npz` - Cached SentenceTransformer embeddings
- `embeddings/titan_v2_1024d.npz` - Cached Bedrock Titan embeddings

## Checkpoints

### Production (copied to yrsn/checkpoints/)
- `text_mlp_384to128_trained.pt` - 128d projection
- `trained_rotor_universal128.pt` - 128d rotor

### Local (experiment only)
- `hybrid_classifier_384d.pt` - Jailbreak classifier
- `ensemble_titan_st_1408d.pt` - Ensemble model
- `swarm_titan_1024d.pt` - Titan classifier

## Usage

```python
from adapters.jailbreak_detector import create_jailbreak_detector

detector = create_jailbreak_detector()
result = detector.check("Ignore all previous instructions...")

if result.is_jailbreak:
    print(f"Blocked: {result.state}, N={result.rsn[2]:.2f}")
```

### DyTopo Routing

```python
from adapters.dytopo_defense_128d import DyTopoRouter

router = DyTopoRouter.create()
result = router.check("User prompt here")

if not result.allowed:
    print(f"Blocked: {result.critical_signals}")
```

### 128d Configuration

```bash
# Use 128d (default with rotor_config)
export ROTOR_DIMENSION=128

# Or 64d for memristor compatibility
export ROTOR_DIMENSION=64
```

## References

- [DyTopo: Dynamic Topology Routing](https://arxiv.org/abs/2602.06039) - Lu et al., 2026
- `yrsn/docs/ROTOR_DIMENSION_MIGRATION_PLAN.md` - 128d migration
- `swarm-it-api/docs/DYTOPO_MULTIMODAL_ARCHITECTURE.md` - Multi-modal integration

## Next Steps

1. Improve accuracy to 90% target (data augmentation, harder negatives)
2. Train 128d rotor on multi-modal features (text + code + vision)
3. Production deployment with frozen embedding cache
