# Quickstart Guide

Get your first RSCT certificate in **under 5 minutes**.

---

## What is RSCT?

**RSCT (Relevance, Stability, Compatibility Testing)** is a quality certification framework for LLM outputs using RSN decomposition:
- **R** (Relevance): How relevant is the output to the prompt?
- **S** (Stability): How stable/consistent is the output?
- **N** (Noise): How much noise/irrelevance is present?
- **Kappa (κ)**: Compatibility score = min(R, S)

---

## Installation

### Step 1: Install swarm-it-adk (30 seconds)

```bash
pip install swarm-it-adk
```

---

## Your First Certificate (3 minutes)

### Step 2: Basic Certification

```python
from swarm_it_adk import RSCTCertifier

# Initialize certifier
certifier = RSCTCertifier()

# Certify text
result = certifier.certify("Hello world, this is a test of RSCT certification.")

# View results
print(f"Decision: {result.decision}")
print(f"Kappa (κ): {result.kappa:.3f}")
print(f"R (Relevance): {result.R:.3f}")
print(f"S (Stability): {result.S:.3f}")
print(f"N (Noise): {result.N:.3f}")
```

**Output:**
```
Decision: EXECUTE
Kappa (κ): 0.742
R (Relevance): 0.742
S (Stability): 0.758
N (Noise): 0.500
```

---

## Understanding the Results

### Decision Types

| Decision | Meaning | Next Steps |
|----------|---------|------------|
| **EXECUTE** | All quality gates passed | Use the output |
| **REPAIR** | Low stability, needs refinement | Refine prompt and retry |
| **BLOCK** | Failed quality gates | Revise approach |
| **REJECT** | High noise/low integrity | Start over with clearer input |

### Quality Metrics

- **Kappa (κ)**: Overall compatibility score (target: ≥0.7)
  - κ = min(R, S) - represents the "weakest link" in quality
- **R (Relevance)**: How relevant the output is (target: ≥0.3)
- **S (Stability)**: How stable/consistent the output is (target: ≥0.4)
- **N (Noise)**: How much noise is present (target: ≤0.5)

**Simplex Constraint**: R + S + N = 1.0 (always)

---

## Advanced Usage

### Custom Thresholds

Adjust quality thresholds based on your domain:

```python
# Medical domain (strict)
certifier = RSCTCertifier(
    kappa=0.9,
    R=0.5,
    S=0.6,
    N=0.3
)

# Research domain (moderate) - default
certifier = RSCTCertifier()  # Uses research defaults

# Development domain (permissive)
certifier = RSCTCertifier(
    kappa=0.5,
    R=0.2,
    S=0.2,
    N=0.7
)
```

### One-Shot Certification (with Evidence)

```python
from swarm_it_adk.one_shot import OneShotCertifier, OneShotRequest

certifier = OneShotCertifier(auto_export=True, evidence_dir="evidence")

result = certifier.certify(OneShotRequest(
    prompt="Analyze this medical diagnosis...",
    domain="medical",
    user_id="doc_123",
    auto_export_evidence=True
))

if result.decision == "EXECUTE":
    print(f"Certificate approved: kappa={result.kappa:.3f}")
    print(f"Evidence saved to: {result.evidence_file}")
```

**Evidence file** (SR 11-7 compliant audit trail):
```json
{
  "request": {
    "prompt": "Analyze this medical diagnosis...",
    "domain": "medical",
    "user_id": "doc_123"
  },
  "result": {
    "decision": "EXECUTE",
    "R": 0.842,
    "S": 0.758,
    "N": 0.400,
    "kappa": 0.758
  },
  "execution": {
    "iterations": 1,
    "timestamp": "2026-03-04T19:45:12.345678"
  }
}
```

---

## Common Use Cases

### 1. Validate LLM Output Quality

```python
from openai import OpenAI
from swarm_it_adk import RSCTCertifier

# Generate LLM output
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Explain quantum computing"}]
)

llm_output = response.choices[0].message.content

# Certify quality
certifier = RSCTCertifier(kappa=0.7)
result = certifier.certify(llm_output)

if result.decision == "EXECUTE":
    print("✓ LLM output passed quality gates")
else:
    print(f"✗ Quality issue: {result.reason}")
```

### 2. Batch Certification

```python
from swarm_it_adk import RSCTCertifier

certifier = RSCTCertifier()

texts = [
    "First text to certify",
    "Second text to certify",
    "Third text to certify"
]

results = [certifier.certify(text) for text in texts]

# Summary
passed = sum(1 for r in results if r.decision == "EXECUTE")
print(f"Passed: {passed}/{len(results)}")
```

### 3. Quality Gates Only

```python
from swarm_it_adk.mcp_tools import QualityGateTool

# Apply quality gates to existing RSN values
gate = QualityGateTool(thresholds={
    "kappa": 0.7,
    "R": 0.3,
    "S": 0.4,
    "N": 0.5
})

result = gate.execute(R=0.742, S=0.758, N=0.500)

print(f"Decision: {result['decision']}")
print(f"Gate reached: {result['gate_reached']}/5")
print(f"Reason: {result['reason']}")
```

---

## Feedback Loops (Shift Left)

Use multi-layer feedback to catch issues early:

```python
from swarm_it_adk.feedback_loops import FeedbackLoopOrchestrator

orchestrator = FeedbackLoopOrchestrator(
    enable_autofix=True,
    max_iterations=2
)

# Validate with automatic retry on REPAIR
result = orchestrator.certify_with_feedback(
    prompt="Your text here",
    certify_func=lambda p: certifier.certify(p)
)

print(f"Decision: {result['decision']}")
print(f"Iterations: {result['iterations']}")
```

**Feedback Layers:**
- **L1 (Local)**: Fast heuristic checks (~50ms)
- **L2 (Agent)**: LLM analysis (~2s) - optional
- **L3 (Rotor)**: RSN decomposition (~200ms)
- **L4 (Gates)**: Quality gate enforcement (~10ms)

---

## Domain-Specific Thresholds

| Domain | Kappa | R | S | N | Use Case |
|--------|-------|---|---|---|----------|
| **Medical** | 0.9 | 0.5 | 0.6 | 0.3 | Clinical decisions, diagnoses |
| **Legal** | 0.85 | 0.5 | 0.5 | 0.4 | Legal opinions, contracts |
| **Financial** | 0.85 | 0.5 | 0.5 | 0.4 | Financial analysis, trading |
| **Research** | 0.7 | 0.3 | 0.4 | 0.5 | Research papers, analysis |
| **Dev** | 0.5 | 0.2 | 0.2 | 0.7 | Code generation, experiments |

---

## Error Handling

Structured errors with actionable guidance:

```python
from swarm_it_adk.errors import CertificationError, ErrorCode

try:
    result = certifier.certify("hi")  # Too short
except CertificationError as e:
    print(f"Error Code: {e.code.value}")
    print(f"Message: {e.message}")
    print(f"Guidance: {e.guidance}")
```

**Output:**
```
Error Code: E101
Message: Prompt too short: 2 characters (minimum: 10)
Guidance: Provide a more detailed prompt with at least 10 characters
```

---

## What's Next?

### Explore Advanced Features

1. **Plugin Architecture**: Extend with custom rotors, quality gates, embeddings
   - See `adk/swarm_it/mcp_tools.py` for plugin system

2. **BYOK (Bring Your Own Key)**: Use your own LLM credentials
   - See `adk/swarm_it/byok_engine.py` for local certification

3. **API Integration**: Deploy as REST API
   - See swarm-it-api repository for production deployment

### Read the Docs

- **API Reference**: Complete function documentation
- **Tutorials**: Step-by-step guides for common scenarios
- **Architecture**: Deep dive into RSCT framework

### Get Help

- **GitHub Issues**: Report bugs or request features
- **Discussions**: Ask questions and share use cases
- **Documentation**: Full reference at [docs link]

---

## Summary

You've learned how to:
- ✓ Install swarm-it-adk
- ✓ Get your first certificate in <5 minutes
- ✓ Understand decision types (EXECUTE, REPAIR, BLOCK, REJECT)
- ✓ Interpret quality metrics (R, S, N, kappa)
- ✓ Use domain-specific thresholds
- ✓ Handle errors with structured exceptions
- ✓ Export evidence for audit compliance

**Next steps**: Try certifying your own LLM outputs and experiment with different domains and thresholds!

---

**Need help?** Open an issue on GitHub or check the full documentation.
