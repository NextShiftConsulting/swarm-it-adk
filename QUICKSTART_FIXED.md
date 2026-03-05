# Quickstart Guide (Updated for Fixed API)

Get your first RSCT certificate in **under 5 minutes**.

---

## What is RSCT?

**RSCT (Relevance, Stability, Compatibility Testing)** is a quality certification framework for LLM outputs using RSN decomposition:
- **R** (Relevance): How relevant is the output to the prompt?
- **S** (Stability/Support): How stable/consistent is the output?
- **N** (Noise): How much noise/irrelevance is present?
- **Kappa (κ)**: Compatibility score = min(R, S)

---

## Installation

### Step 1: Install swarm-it-adk (30 seconds)

```bash
# Minimal install (core functionality only)
pip install -r requirements/base.txt

# Recommended install (with validation, monitoring)
pip install -r requirements/recommended.txt
```

---

## Your First Certificate (3 minutes)

### Step 2: Basic Certification

**Option A: Quick one-liner (recommended)**

```python
from swarm_it import certify

# Certify text and get RSCTCertificate object
cert = certify("Hello world, this is a test of RSCT certification.")

# View results
print(f"Decision: {cert.decision.value}")
print(f"Allowed: {cert.decision.allowed}")
print(f"Kappa (κ): {cert.kappa_gate:.3f}")
print(f"R (Relevance): {cert.R:.3f}")
print(f"S (Stability): {cert.S:.3f}")
print(f"N (Noise): {cert.N:.3f}")
```

**Option B: Using LocalEngine directly**

```python
from swarm_it import LocalEngine

# Initialize engine
engine = LocalEngine(policy="default")

# Certify text
cert = engine.certify("Hello world, this is a test of RSCT certification.")

# View results
print(f"Decision: {cert.decision.value}")
print(f"Kappa (κ): {cert.kappa_gate:.3f}")
```

**Option C: Fluent builder pattern**

```python
from swarm_it import FluentCertifier

# Use builder pattern for configuration
cert = (
    FluentCertifier()
    .with_prompt("Hello world, this is a test of RSCT certification.")
    .for_research()  # Preset for research domain
    .certify()
)

# View results
print(f"Decision: {cert.decision.value}")
print(f"Policy: {cert.policy}")
```

---

## Understanding the Certificate

The returned `RSCTCertificate` object contains:

```python
from swarm_it import certify

cert = certify("Test prompt")

# Core simplex (R + S + N = 1)
print(f"R = {cert.R:.3f}")  # Relevance
print(f"S = {cert.S:.3f}")  # Stability
print(f"N = {cert.N:.3f}")  # Noise

# Quality metrics
print(f"Kappa = {cert.kappa_gate:.3f}")  # Compatibility
print(f"Sigma = {cert.sigma:.3f}")       # Turbulence
print(f"Alpha = {cert.alpha:.3f}")       # Purity (R/(R+N))

# Gate decision
print(f"Decision = {cert.decision.value}")  # EXECUTE, REJECT, etc.
print(f"Allowed = {cert.decision.allowed}") # True/False
print(f"Gate reached = {cert.gate_reached}")  # 1-5
print(f"Reason = {cert.reason}")
```

---

## Batch Processing

Process multiple prompts efficiently:

```python
from swarm_it import certify_batch

prompts = [
    "Translate this to Spanish",
    "Summarize the quarterly report",
    "Generate authentication code"
]

certs = certify_batch(prompts)

# Process results
for i, cert in enumerate(certs, 1):
    status = "✓ PASS" if cert.decision.allowed else "✗ FAIL"
    print(f"[{i}] {status} kappa={cert.kappa_gate:.3f}")
```

---

## Domain Presets

Use domain-specific configurations:

```python
from swarm_it import FluentCertifier

# Medical domain (strict)
cert = (
    FluentCertifier()
    .with_prompt("Patient diagnosis: fever, cough")
    .for_medical()
    .certify()
)

# Legal domain (strict)
cert = (
    FluentCertifier()
    .with_prompt("Legal analysis of contract")
    .for_legal()
    .certify()
)

# Development domain (permissive)
cert = (
    FluentCertifier()
    .with_prompt("Generate Python function")
    .for_development()
    .certify()
)
```

---

## Gating Logic

Use certificates to gate execution:

```python
from swarm_it import certify

def call_llm_with_gating(prompt: str):
    """Call LLM only if prompt passes certification."""
    cert = certify(prompt)

    if cert.decision.allowed:
        # Execute - prompt is safe and relevant
        print(f"✓ Executing (kappa={cert.kappa_gate:.3f})")
        response = your_llm_call(prompt)
        return response
    else:
        # Block - prompt failed quality gates
        print(f"✗ Blocked: {cert.reason}")
        print(f"  Gate reached: {cert.gate_reached}/5")
        print(f"  R={cert.R:.3f}, S={cert.S:.3f}, N={cert.N:.3f}")
        return None

# Use it
result = call_llm_with_gating("Calculate fibonacci sequence")
```

---

## Error Handling

Handle certification errors properly:

```python
from swarm_it import certify, CertificationError, ErrorCode

try:
    cert = certify("Your prompt here")

    if cert.decision.allowed:
        # Proceed with execution
        pass
    else:
        # Handle rejection
        print(f"Rejected: {cert.reason}")

except CertificationError as e:
    print(f"Error: [{e.code.value}] {e.message}")
    print(f"Guidance: {e.guidance}")

    # Check specific error codes
    if e.code == ErrorCode.PROMPT_TOO_SHORT:
        print("Prompt is too short, please provide more detail")
```

---

## Circuit Breakers

Protect against cascading failures:

```python
from swarm_it import certify, CircuitBreaker, CircuitBreakerConfig

# Configure circuit breaker
config = CircuitBreakerConfig(
    failure_threshold=5,
    timeout_duration=60.0
)
breaker = CircuitBreaker("certification", config)

# Use with protection
try:
    with breaker:
        cert = certify("Your prompt")
        print(f"State: {breaker.state.value}")

except Exception as e:
    print(f"Circuit breaker error: {e}")
```

---

## Next Steps

- **Production Setup**: See `requirements/README.md` for tiered installation
- **API Examples**: See `examples/api_showcase.py` for comprehensive examples
- **Full Features**: See `FEATURES.md` for all Phase 1-6 features
- **Development**: See `requirements/dev.txt` for testing/linting tools

---

## API Reference

### Core Functions

```python
from swarm_it import (
    # Quick entry points
    certify,              # One-liner certification
    certify_local,        # Module-level function
    certify_batch,        # Batch processing

    # Classes
    LocalEngine,          # Direct engine access
    FluentCertifier,      # Builder pattern
    RSCTCertificate,      # Certificate object

    # Errors
    CertificationError,   # Structured errors
    ErrorCode,            # Error code enum

    # Reliability
    CircuitBreaker,       # Circuit breaker pattern
    ChaosManager,         # Chaos engineering
)
```

### Return Type

All certification methods return `RSCTCertificate`:
- `certify(prompt)` → `RSCTCertificate`
- `certify_local(prompt)` → `RSCTCertificate`
- `LocalEngine().certify(prompt)` → `RSCTCertificate`
- `FluentCertifier().certify()` → `RSCTCertificate`
- `certify_batch(prompts)` → `List[RSCTCertificate]`

---

## Troubleshooting

**Import Error: No module named 'pydantic'**
```bash
pip install -r requirements/recommended.txt
```

**Import Error: No module named 'redis'**
```bash
pip install -r requirements/performance.txt
```

**See `requirements/README.md` for full dependency guide.**
