# Deep Dive: A2A RAG Swarm Certificate Analysis

## Overview

This document provides a **diagnostic guide** for understanding and debugging RAG pipelines using Swarm-IT A2A certificates. Every field in the certificate tells a story about what's happening in your pipeline.

---

## Certificate Structure

A complete certificate contains **18 fields** across 5 categories:

```python
{
    # IDENTITY
    "id": "02fcb16cd5f65196",           # Unique certificate hash
    "timestamp": "2026-02-25T02:14:10Z", # When certified

    # CORE RSN (R + S + N = 1.0)
    "R": 0.3221,                         # Relevance (task-relevant content)
    "S": 0.3703,                         # Support (contextual content)
    "N": 0.3076,                         # Noise (irrelevant/harmful)

    # QUALITY METRICS
    "kappa_gate": 0.5115,                # κ = R/(R+N) - quality score
    "sigma": 0.0536,                     # Stability/volatility

    # DECISION
    "decision": "REPAIR",                # EXECUTE/REPAIR/BLOCK/REJECT
    "gate_reached": 4,                   # Which gate (0-5)
    "allowed": True,                     # Can proceed?
    "reason": "Low compatibility...",    # Explanation

    # SECURITY
    "pattern_flags": [],                 # Detected attack patterns
    "pre_screen_rejection": False,       # Sidecar rejected (vs yrsn)

    # MULTIMODAL (for future)
    "is_multimodal": False,
    "kappa_H": None,                     # High-level kappa
    "kappa_L": None,                     # Low-level kappa
    "kappa_interface": None,             # Interface compatibility
    "weak_modality": None,               # Weakest modality
}
```

---

## Diagnostic Insights

### 1. RSN Triangle Analysis

The R, S, N values form a **simplex** (they sum to 1.0). The triangle position tells you the content character:

```
                    N (Noise)
                    /\
                   /  \
                  /    \
                 /      \
                /   ❌   \     N > 0.5: Attack/Garbage
               /          \
              /____________\
             R              S
         (Relevance)    (Support)

High R = Task-focused question
High S = Context-heavy content (good for RAG)
High N = Noise/Attack (block it!)
```

**RAG Pipeline Insights:**

| Stage | Expected RSN Profile | Warning Signs |
|-------|---------------------|---------------|
| **Query** | R=0.5-0.7, S=0.1-0.3, N<0.3 | S too high = vague query |
| **Retrieved Docs** | R=0.3-0.5, S=0.4-0.6, N<0.2 | N high = irrelevant docs |
| **Synthesized Answer** | R=0.5-0.7, S=0.2-0.4, N<0.2 | S too high = rambling |
| **Validated Output** | R>0.5, N<0.2 | Any N>0.3 = quality issue |

### 2. Kappa (κ) Interpretation

`κ = R / (R + N)` measures **signal-to-noise ratio**:

```
κ ≥ 0.8   │ EXCELLENT │ Clear, focused content
0.7 ≤ κ   │ GOOD      │ Gate: EXECUTE
0.5 ≤ κ   │ MARGINAL  │ Gate: REPAIR - monitor this!
0.3 ≤ κ   │ POOR      │ Gate: BLOCK
κ < 0.3   │ CRITICAL  │ Gate: REJECT
```

**Developer Action Table:**

| κ Range | Pipeline Stage | Diagnosis | Action |
|---------|----------------|-----------|--------|
| κ < 0.3 | Query | Garbage/attack input | Block, log for review |
| κ < 0.3 | Retriever | Wrong documents | Check vector DB, embeddings |
| κ < 0.3 | Synthesizer | LLM hallucinating | Adjust prompt, reduce temp |
| κ < 0.3 | Validator | Output quality failed | Retry or escalate |
| 0.3-0.5 | Any | Borderline quality | Add to monitoring queue |
| 0.5-0.7 | Synthesizer | Acceptable but verbose | Consider summarization |
| > 0.7 | All | Healthy pipeline | No action needed |

### 3. Sigma (σ) - Stability Indicator

`σ` measures **volatility/uncertainty** in the RSN decomposition:

```
σ < 0.1   │ STABLE    │ Confident decomposition
0.1-0.3   │ NORMAL    │ Typical variance
0.3-0.5   │ UNSTABLE  │ High uncertainty - investigate
σ > 0.5   │ VOLATILE  │ Unreliable - don't trust RSN values
```

**What high σ means in RAG:**

| High σ At | Likely Cause | Fix |
|-----------|--------------|-----|
| Query | Ambiguous question | Ask for clarification |
| Retriever output | Mixed-quality documents | Improve chunking |
| Synthesizer output | LLM uncertainty | Lower temperature, better prompt |

### 4. Gate Levels

The `gate_reached` field shows **how far the certificate progressed**:

```
Gate 0: Pre-screen REJECT (sidecar blocked it)
Gate 1: N ≥ 0.5 → REJECT (too noisy)
Gate 2: R < 0.3 → BLOCK (not relevant)
Gate 3: (reserved)
Gate 4: κ < 0.7 → REPAIR (allowed but flagged)
Gate 5: EXECUTE (fully approved)
```

**Debugging by Gate:**

| Gate | What Failed | RAG Diagnosis |
|------|-------------|---------------|
| 0 | Pattern detection | Injection/jailbreak attempt |
| 1 | Noise threshold | Retrieved garbage documents |
| 2 | Relevance minimum | Query doesn't match docs |
| 4 | Quality threshold | Synthesis needs improvement |
| 5 | Nothing! | Pipeline healthy |

### 5. Pattern Flags

The `pattern_flags` array reveals **what triggered detection**:

```python
pattern_flags: ["injection", "semantic:jailbreak"]
#               ↑ regex      ↑ embedding-based
```

**Common Patterns:**

| Pattern | Description | RAG Impact |
|---------|-------------|------------|
| `injection` | "Ignore instructions..." | User attack |
| `jailbreak` | DAN, roleplay attacks | User attack |
| `xss` | Script tags | User attack |
| `semantic:injection` | Paraphrased attack | Sophisticated attack |
| `semantic:jailbreak` | Novel jailbreak | Zero-day attempt |
| `spam` | Marketing/spam content | Low-quality input |

---

## RAG Pipeline Certificate Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG PIPELINE CERTIFICATES                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  USER QUERY                                                          │
│  ┌─────────────────────────────────────────┐                        │
│  │ "What is the capital of France?"        │                        │
│  │ ─────────────────────────────────────── │                        │
│  │ R=0.75  S=0.15  N=0.10  κ=0.88  ✓       │ ← High R = focused    │
│  │ gate=5 (EXECUTE)                        │                        │
│  └─────────────────────────────────────────┘                        │
│                         │                                            │
│                         ▼                                            │
│  RETRIEVER OUTPUT (docs)                                            │
│  ┌─────────────────────────────────────────┐                        │
│  │ "Paris is the capital of France..."     │                        │
│  │ ─────────────────────────────────────── │                        │
│  │ R=0.45  S=0.48  N=0.07  κ=0.87  ✓       │ ← High S = context    │
│  │ gate=5 (EXECUTE)                        │                        │
│  └─────────────────────────────────────────┘                        │
│                         │                                            │
│                         ▼                                            │
│  SYNTHESIZER OUTPUT                                                  │
│  ┌─────────────────────────────────────────┐                        │
│  │ "The capital of France is Paris..."     │                        │
│  │ ─────────────────────────────────────── │                        │
│  │ R=0.64  S=0.22  N=0.14  κ=0.82  ✓       │ ← Balanced answer     │
│  │ gate=5 (EXECUTE)                        │                        │
│  └─────────────────────────────────────────┘                        │
│                         │                                            │
│                         ▼                                            │
│  VALIDATOR OUTPUT                                                    │
│  ┌─────────────────────────────────────────┐                        │
│  │ quality_ok=True, validation=PASS        │                        │
│  │ ─────────────────────────────────────── │                        │
│  │ R=0.64  S=0.22  N=0.14  κ=0.82  ✓       │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Swarm-Level Diagnostics

### Link Health Analysis

Each agent-to-agent link has a running `kappa_interface`:

```python
cert = certifier.get_swarm_certificate(swarm)

# Per-link breakdown
for link_id, kappa in cert.link_kappas.items():
    print(f"{link_id}: κ={kappa:.2f}")

# Output:
# user->retriever: κ=0.75       ← Queries are good
# retriever->synthesizer: κ=0.62 ← Docs quality varies
# synthesizer->validator: κ=0.80 ← Answers are solid
```

**Diagnostic Matrix:**

| Link | Low κ Cause | Fix |
|------|-------------|-----|
| user→retriever | Bad queries | Input validation, examples |
| retriever→synthesizer | Poor doc quality | Better embeddings, rerank |
| synthesizer→validator | LLM issues | Prompt engineering, model switch |
| validator→user | Output formatting | Post-processing |

### Weakest Link Detection

```python
if cert.weakest_link_id:
    print(f"Bottleneck: {cert.weakest_link_id}")
    # Focus optimization here!
```

**The weakest link determines swarm health:**

```
kappa_swarm = min(kappa_interface across all links)
```

If `kappa_swarm` is low, the `weakest_link_id` tells you exactly where to look.

---

## Advanced Diagnostics

### 1. RSN Drift Detection

Track RSN over time to detect drift:

```python
# Store certificates in time series
cert_history = []

for query in queries:
    msg = certifier.certify_message(swarm, "user", "retriever", query)
    cert_history.append({
        "timestamp": msg.timestamp,
        "R": msg.R,
        "S": msg.S,
        "N": msg.N,
        "kappa": msg.kappa,
    })

# Detect drift
recent_N = [c["N"] for c in cert_history[-100:]]
if np.mean(recent_N) > 0.3:
    alert("Noise increasing - possible attack campaign or data quality issue")
```

### 2. Cross-Stage Correlation

Compare RSN across stages to find issues:

```python
# Ideal: R increases as we go deeper
query_R = 0.65
docs_R = 0.45   # ← Lower R in docs = retrieval issue
answer_R = 0.55

if docs_R < query_R - 0.2:
    alert("Retriever finding irrelevant documents")
```

### 3. Pattern Frequency Analysis

Track which patterns appear most:

```python
from collections import Counter

pattern_counts = Counter()
for cert in all_certs:
    for flag in cert.get("pattern_flags", []):
        pattern_counts[flag] += 1

# Find attack trends
print(pattern_counts.most_common(5))
# [('semantic:jailbreak', 42), ('injection', 28), ...]
```

### 4. Kappa Distribution Analysis

Plot kappa distribution to understand quality:

```python
import matplotlib.pyplot as plt

kappas = [cert["kappa_gate"] for cert in all_certs]

plt.hist(kappas, bins=20)
plt.axvline(x=0.7, color='g', label='EXECUTE threshold')
plt.axvline(x=0.3, color='r', label='BLOCK threshold')
plt.xlabel("Kappa")
plt.ylabel("Frequency")
plt.title("Certificate Quality Distribution")
```

**Healthy distribution:** Peak around 0.7-0.8, few below 0.3
**Unhealthy:** Bimodal (attacks + good), or shifted left

---

## Troubleshooting Guide

### Problem: High N (Noise) in Retrieved Documents

**Symptoms:**
- `retriever→synthesizer` link has low κ
- Retrieved docs have N > 0.3

**Diagnosis:**
```python
msg = certifier.certify_message(swarm, "retriever", "synthesizer", docs)
print(f"Docs N={msg.N:.2f}")  # If > 0.3, problem!
```

**Fixes:**
1. Improve document chunking strategy
2. Add metadata filtering
3. Use hybrid search (semantic + keyword)
4. Re-embed documents with better model

---

### Problem: Low R (Relevance) in Synthesized Answers

**Symptoms:**
- `synthesizer→validator` has lower R than `retriever→synthesizer`
- Answers are vague or off-topic

**Diagnosis:**
```python
docs_cert = get_cert(swarm, "retriever", "synthesizer", docs)
answer_cert = get_cert(swarm, "synthesizer", "validator", answer)

if answer_cert.R < docs_cert.R - 0.1:
    print("LLM not using provided context well")
```

**Fixes:**
1. Improve system prompt (be more specific)
2. Use explicit "Answer based ONLY on the context" instruction
3. Lower temperature
4. Try different model

---

### Problem: Attacks Getting Through

**Symptoms:**
- `pattern_flags` empty but N is high
- `pre_screen_rejection` is False but content is bad

**Diagnosis:**
```python
# Check if semantic analyzer caught it
if msg.N > 0.5 and not msg.pattern_flags:
    print("Attack bypassed both regex and semantic detection!")
    # Add this pattern to training
```

**Fixes:**
1. Add pattern to `patterns.py`
2. Fine-tune semantic analyzer thresholds
3. Add to attack embedding corpus

---

### Problem: False Positives (Good Content Blocked)

**Symptoms:**
- Legitimate queries getting `decision=REJECT`
- `pattern_flags` contains false matches

**Diagnosis:**
```python
# Check what triggered rejection
print(f"Blocked: {msg.content[:50]}")
print(f"Flags: {msg.pattern_flags}")
print(f"N={msg.N:.2f}, R={msg.R:.2f}")
```

**Fixes:**
1. Adjust pattern regex to be more specific
2. Increase semantic threshold
3. Add to benign embedding corpus

---

## Certificate Export for Analysis

### JSON Export

```python
import json

cert = certifier.get_swarm_certificate(swarm)
with open("swarm_cert.json", "w") as f:
    json.dump(cert.to_dict(), f, indent=2)
```

### Pandas DataFrame

```python
import pandas as pd

# Message-level analysis
messages = []
for msg in all_messages:
    messages.append({
        "source": msg.source_id,
        "target": msg.target_id,
        "R": msg.R,
        "S": msg.S,
        "N": msg.N,
        "kappa": msg.kappa,
        "decision": msg.decision,
    })

df = pd.DataFrame(messages)
print(df.groupby(["source", "target"])["kappa"].mean())
```

---

## Summary: Key Diagnostic Questions

| Question | Certificate Field(s) | Good Value |
|----------|---------------------|------------|
| Is content relevant? | R | > 0.4 |
| Is it an attack? | N, pattern_flags | N < 0.3, flags=[] |
| Overall quality? | kappa_gate | > 0.7 |
| Which gate failed? | gate_reached, decision | gate=5, EXECUTE |
| Pre-screened? | pre_screen_rejection | False (passed check) |
| Pipeline bottleneck? | weakest_link_id | Should be None |
| Swarm healthy? | kappa_swarm | > 0.6 |
| Stable results? | sigma | < 0.3 |

---

## Next Steps

1. **Set up monitoring** - Track kappa_swarm over time
2. **Alert on drift** - Notify when avg N increases
3. **Review blocked** - Audit pre_screen_rejection=True
4. **Optimize weakest** - Focus on weakest_link_id
5. **Export for ML** - Use certificates to train better models
