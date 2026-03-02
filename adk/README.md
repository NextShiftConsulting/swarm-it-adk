# Swarm It SDK

**Execution governance for AI systems.**

Swarm It provides RSCT (Representation-Space Compatibility Theory) certification for AI/LLM calls. Instead of hoping your AI behaves well, verify it's safe to execute *before* you call.

## Installation

```bash
pip install swarm-it

# With LangChain integration
pip install swarm-it[langchain]

# With FastAPI integration
pip install swarm-it[fastapi]

# All integrations
pip install swarm-it[all]
```

## Quick Start

### Simple Certification

```python
from swarm_it import SwarmIt

swarm = SwarmIt(api_key="your-api-key")

# Certify before calling your LLM
cert = swarm.certify("What is the capital of France?")

if cert.allowed:
    response = my_llm(prompt)
else:
    print(f"Blocked: {cert.reason}")
```

### Decorator Pattern

```python
from swarm_it import SwarmIt

swarm = SwarmIt()

@swarm.gate
def ask_llm(prompt: str) -> str:
    return openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content

# Automatically certified - raises GateBlockedError if rejected
result = ask_llm("Explain quantum computing")
```

### Custom Block Handler

```python
@swarm.gate(on_block=lambda cert: "I can't help with that.")
def ask_llm(prompt: str) -> str:
    return call_my_llm(prompt)

# Returns fallback message instead of raising
result = ask_llm("risky prompt")
```

## Understanding Certificates

Each certification returns a `Certificate` with:

```python
cert = swarm.certify("Your prompt here")

# RSN decomposition (sums to 1.0)
cert.R      # Relevance: how on-topic the prompt is
cert.S      # Support: grounding in known information
cert.N      # Novelty: how unusual/risky the prompt is

# Quality metrics
cert.alpha  # Purity: R/(R+N) - higher is better
cert.kappa  # Compatibility: execution readiness score
cert.sigma  # Turbulence: volatility estimate

# Gate decision
cert.decision   # EXECUTE, REJECT, BLOCK, RE_ENCODE, REPAIR
cert.allowed    # True if safe to execute
cert.reason     # Human-readable explanation
cert.margin     # Safety buffer (higher = more confident)
```

## Framework Integrations

### LangChain

```python
from swarm_it import SwarmIt
from swarm_it.integrations import SwarmItRunnable
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

swarm = SwarmIt()

# Create gated chain
prompt = ChatPromptTemplate.from_template("Answer: {question}")
llm = ChatOpenAI()

chain = SwarmItRunnable(swarm) | prompt | llm

# Certified before execution
result = chain.invoke({"question": "What is AI?"})
```

### FastAPI

```python
from fastapi import FastAPI
from swarm_it import SwarmIt
from swarm_it.integrations import SwarmItMiddleware, require_certificate

app = FastAPI()
swarm = SwarmIt()

# Option 1: Middleware (all routes)
app.add_middleware(SwarmItMiddleware, client=swarm, paths=["/api/"])

# Option 2: Per-route decorator
@app.post("/chat")
@require_certificate(swarm, context_param="prompt")
async def chat(prompt: str):
    return {"response": call_llm(prompt)}
```

## Configuration

### Environment Variables

```bash
SWARM_IT_API_KEY=your-api-key
SWARM_IT_BASE_URL=https://api.swarm-it.dev/v1  # Optional
```

### Client Options

```python
swarm = SwarmIt(
    api_key="...",           # Or use SWARM_IT_API_KEY env var
    base_url="...",          # Custom API endpoint
    timeout=30.0,            # Request timeout (seconds)
    policy="default",        # Default certification policy
)
```

## Policies

Policies control certification thresholds:

- `default` - Balanced safety/permissiveness
- `strict` - Tighter thresholds, more rejections
- `permissive` - Looser thresholds, fewer rejections
- Custom policies available via dashboard

```python
cert = swarm.certify(prompt, policy="strict")
```

## Local Mode

When the API is unavailable, the SDK falls back to local hash-based certification:

```python
swarm = SwarmIt()  # No API key

# Uses local fallback (deterministic but not RSCT-compliant)
cert = swarm.certify("test prompt")
print(cert.raw["_local_mode"])  # True
```

**Note:** Local mode is for testing only. Production should use the API.

## Error Handling

```python
from swarm_it import SwarmIt, GateBlockedError, CertificationError

swarm = SwarmIt()

try:
    cert = swarm.certify(prompt)
    if cert.allowed:
        result = call_llm(prompt)
except GateBlockedError as e:
    print(f"Blocked: {e.certificate.reason}")
except CertificationError as e:
    print(f"Certification failed: {e}")
```

## License

Apache License 2.0 (see `LICENSE` at repo root).
