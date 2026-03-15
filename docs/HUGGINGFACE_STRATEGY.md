# HuggingFace Profile Strategy for RSCT

## Overview

Build visibility for RSCT (Relevance, Stability, Compatibility Testing) on HuggingFace through Spaces, Models, and Datasets.

## Asset Priority

| Asset Type | Visibility | Status | Action |
|------------|------------|--------|--------|
| **Spaces** | HIGH | ❌ Not created | Create Gradio demo |
| **Models** | HIGH | ✅ Ready (.pt files) | Upload with model card |
| **Datasets** | MEDIUM | ❌ Not created | Curate from blogs |
| **Papers** | MEDIUM | ⏳ Need arXiv | Submit then link |

---

## 1. Gradio Space: "RSCT Context Quality Demo"

**Purpose**: Interactive demo showing RSN decomposition in real-time.

**App Code** (`app.py`):

```python
import gradio as gr
from swarm_it import certify

def analyze_context(text):
    """Certify text and return RSN certificate."""
    cert = certify(text)

    # Visual indicators
    quality = "🟢 HIGH" if cert.kappa_gate >= 0.7 else "🟡 MEDIUM" if cert.kappa_gate >= 0.4 else "🔴 LOW"
    decision = "✅ ALLOWED" if cert.decision.allowed else "❌ BLOCKED"

    return {
        "R (Relevant)": f"{cert.R:.3f}",
        "S (Superfluous)": f"{cert.S:.3f}",
        "N (Noise)": f"{cert.N:.3f}",
        "Simplex Check": f"R+S+N = {cert.R + cert.S + cert.N:.3f}",
        "κ (Quality Gate)": f"{cert.kappa_gate:.3f} {quality}",
        "Decision": decision
    }

def batch_analyze(texts):
    """Analyze multiple contexts."""
    from swarm_it import certify_batch
    results = []
    for cert in certify_batch(texts.split('\n')):
        results.append(f"κ={cert.kappa_gate:.2f} {'✅' if cert.decision.allowed else '❌'}")
    return '\n'.join(results)

with gr.Blocks(title="RSCT Context Quality") as demo:
    gr.Markdown("# RSCT Context Quality Certification")
    gr.Markdown("Pre-generation quality measurement using RSN simplex decomposition")

    with gr.Tab("Single Analysis"):
        input_text = gr.Textbox(label="Enter context to certify", lines=3)
        output_json = gr.JSON(label="RSN Certificate")
        analyze_btn = gr.Button("Certify")
        analyze_btn.click(analyze_context, inputs=input_text, outputs=output_json)

    with gr.Tab("Batch Analysis"):
        batch_input = gr.Textbox(label="One context per line", lines=5)
        batch_output = gr.Textbox(label="Results", lines=5)
        batch_btn = gr.Button("Certify Batch")
        batch_btn.click(batch_analyze, inputs=batch_input, outputs=batch_output)

    gr.Markdown("""
    ## What is RSCT?

    **RSN Decomposition**: Every context decomposes into:
    - **R (Relevant)**: Task-pertinent information
    - **S (Superfluous)**: Accurate but task-irrelevant
    - **N (Noise)**: Incorrect or corrupted

    **Constraint**: R + S + N = 1.0 (simplex)

    **κ (Kappa)**: Quality gate threshold (κ ≥ 0.7 = high quality)
    """)

demo.launch()
```

**Space Config** (`README.md` for Space):

```yaml
---
title: RSCT Context Quality
emoji: 🔬
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
license: apache-2.0
---
```

---

## 2. Model Upload: Universal Rotor

**Model Files** (from yrsn/checkpoints/):

| File | Description | Upload As |
|------|-------------|-----------|
| `trained_rotor_geometric64.pt` | Universal Rotor | `rsct-universal-rotor` |
| `trained_rotor_multimodal.pt` | Multimodal variant | `rsct-multimodal-rotor` |
| `text_mlp_384to64_trained.pt` | Text projection | `rsct-text-projection` |
| `siglip_projection_768to64_trained.pt` | Vision projection | `rsct-vision-projection` |

**Model Card** (`README.md`):

```markdown
---
license: apache-2.0
tags:
  - pytorch
  - context-quality
  - rsct
  - rsn-decomposition
---

# RSCT Universal Rotor

Geometric rotor for RSN (Relevance, Superfluous, Noise) simplex decomposition.

## Model Description

The Universal Rotor maps 64-dimensional embeddings to the RSN simplex,
guaranteeing R + S + N = 1.0 by construction.

## Intended Use

Pre-generation quality certification for LLM outputs.

## Architecture

- **Type**: HybridSimplexRotor
- **Input**: 64-dim embedding vector
- **Output**: RSN tuple (R, S, N) where R + S + N = 1.0
- **Training**: Geometric rotation with barycentric mapping

## Usage

```python
import torch
from yrsn.core.decomposition import HybridSimplexRotor

rotor = HybridSimplexRotor(embed_dim=64)
rotor.load_state_dict(torch.load("trained_rotor_geometric64.pt"))

embedding = get_embedding(text)  # 64-dim
R, S, N = rotor(embedding)
assert abs(R + S + N - 1.0) < 0.001  # Simplex constraint
```

## Training Data

Trained on mixed-domain corpus with labeled context quality examples.

## Limitations

- Requires 64-dim input embeddings
- Domain-specific calibration may improve accuracy

## Citation

Patent pending. See PATENT_NOTICE.md.
```

---

## 3. Dataset: Context Quality Examples

**Dataset Structure**:

```
rsct-context-quality/
├── train.jsonl
├── validation.jsonl
├── test.jsonl
└── README.md
```

**Example Records** (`train.jsonl`):

```jsonl
{"text": "Calculate the fibonacci sequence up to 100", "R": 0.85, "S": 0.10, "N": 0.05, "quality": "high", "decision": "allowed"}
{"text": "As an AI language model, I cannot help with that, but here's what I would do anyway...", "R": 0.15, "S": 0.35, "N": 0.50, "quality": "low", "decision": "blocked"}
{"text": "The patient presents with fever (38.5°C), dry cough, and fatigue for 3 days", "R": 0.90, "S": 0.08, "N": 0.02, "quality": "high", "decision": "allowed"}
{"text": "Varghese v. China Southern Airlines, 925 F.3d 1339 (11th Cir. 2019)", "R": 0.10, "S": 0.20, "N": 0.70, "quality": "hallucination", "decision": "blocked"}
```

**Dataset Card** (`README.md`):

```markdown
---
license: apache-2.0
task_categories:
  - text-classification
tags:
  - context-quality
  - rsct
  - hallucination-detection
---

# RSCT Context Quality Dataset

Labeled examples for training and evaluating context quality models.

## Dataset Description

Each example contains:
- `text`: The context to be evaluated
- `R`, `S`, `N`: Ground-truth RSN decomposition (R + S + N = 1.0)
- `quality`: Categorical label (high, medium, low, hallucination)
- `decision`: Binary outcome (allowed, blocked)

## Source

Curated from real-world examples documented in the "16 Ways AI Systems Fail" series.

## Use Cases

- Train context quality classifiers
- Evaluate hallucination detection models
- Benchmark RSN decomposition accuracy
```

---

## 4. HuggingFace Papers

**Requirement**: Paper must be on arXiv first.

**Steps**:
1. Submit RSCT whitepaper to arXiv (cs.LG or cs.AI)
2. Go to huggingface.co/papers
3. Submit arXiv ID
4. Paper appears in daily feed (potential @_akhaliq pickup)

---

## Implementation Order

| Step | Asset | Effort | Dependencies |
|------|-------|--------|--------------|
| 1 | Gradio Space | 1 hour | None |
| 2 | Model Upload | 30 min | Model card |
| 3 | Dataset | 2 hours | Labeled examples |
| 4 | HF Papers | Days | arXiv submission |

---

## Links

- HuggingFace Spaces: https://huggingface.co/spaces
- HuggingFace Models: https://huggingface.co/models
- HuggingFace Datasets: https://huggingface.co/datasets
- HuggingFace Papers: https://huggingface.co/papers
