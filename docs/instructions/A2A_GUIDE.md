# Swarm-IT A2A (Agent-to-Agent) Guide

## Overview

Swarm-IT provides **certified multi-agent communication** using RSN (Relevance, Support, Noise) decomposition. Every message between agents is certified before delivery, ensuring:

- **Injection attacks blocked** at any point in the swarm
- **Weak links identified** (bottleneck detection)
- **Swarm health monitored** continuously via `kappa_swarm`

```
┌─────────────────────────────────────────────────────────────┐
│                    SWARM CERTIFICATION                       │
│                                                              │
│   Agent A ──[certified]──► Agent B ──[certified]──► Agent C │
│                                                              │
│   kappa_swarm = min(kappa_interface) across all links       │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/swarm-it.git
cd swarm-it

# Set up Python path (requires yrsn)
export PYTHONPATH="/path/to/yrsn/src:/path/to/yrsn/keys:."

# Run with Python 3.11+
python examples/a2a_swarm.py
```

### Basic Usage

```python
from sidecar.a2a import SwarmCertifier, Agent, AgentRole

# 1. Create certifier
certifier = SwarmCertifier()

# 2. Define agents
coordinator = Agent(
    id="coord",
    name="Coordinator",
    role=AgentRole.COORDINATOR,
    model="claude-3-sonnet",
)

worker = Agent(
    id="worker",
    name="Worker Agent",
    role=AgentRole.WORKER,
    model="claude-3-haiku",
)

# 3. Create swarm
swarm = certifier.create_swarm("my-swarm", [coordinator, worker])

# 4. Define communication links
certifier.add_link(swarm, "coord", "worker")
certifier.add_link(swarm, "worker", "coord")

# 5. Certify messages
msg = certifier.certify_message(
    swarm,
    source_id="coord",
    target_id="worker",
    content="Analyze the Q4 sales data and identify trends.",
)

print(f"R={msg.R:.2f} S={msg.S:.2f} N={msg.N:.2f}")
print(f"Allowed: {msg.allowed}")

# 6. Check swarm health
cert = certifier.get_swarm_certificate(swarm)
print(f"kappa_swarm: {cert.kappa_swarm:.2f}")
print(f"Swarm healthy: {cert.swarm_healthy}")
```

---

## Core Concepts

### RSN Decomposition

Every message is decomposed into three components that sum to 1.0:

| Component | Meaning | Good Range |
|-----------|---------|------------|
| **R** (Relevance) | Task-relevant content | > 0.4 |
| **S** (Support) | Supporting/contextual content | 0.2 - 0.4 |
| **N** (Noise) | Irrelevant or harmful content | < 0.3 |

### Kappa (κ) Score

Quality score computed as: `κ = R / (R + N)`

| κ Range | Meaning |
|---------|---------|
| κ ≥ 0.7 | EXECUTE - High quality |
| 0.4 ≤ κ < 0.7 | REPAIR - Allowed but flagged |
| κ < 0.4 | BLOCK/REJECT - Not allowed |

### Agent Roles

```python
from sidecar.a2a import AgentRole

AgentRole.COORDINATOR  # Orchestrates other agents
AgentRole.WORKER       # Executes tasks
AgentRole.VALIDATOR    # Validates outputs
AgentRole.ROUTER       # Routes messages
AgentRole.SPECIALIST   # Domain-specific agent
```

---

## Swarm Topologies

### 1. Linear Pipeline

```
user → retriever → synthesizer → validator
```

```python
certifier.add_link(swarm, "user", "retriever")
certifier.add_link(swarm, "retriever", "synthesizer")
certifier.add_link(swarm, "synthesizer", "validator")
```

### 2. Hierarchical (Manager/Workers)

```
         ┌─── worker_1 ───┐
  manager ├─── worker_2 ───┼─── aggregator
         └─── worker_3 ───┘
```

```python
# Manager → Workers
for worker_id in ["worker_1", "worker_2", "worker_3"]:
    certifier.add_link(swarm, "manager", worker_id)
    certifier.add_link(swarm, worker_id, "aggregator")
```

### 3. Circular (Feedback Loop)

```
coordinator → researcher → reviewer → coordinator
```

```python
certifier.add_link(swarm, "coordinator", "researcher")
certifier.add_link(swarm, "researcher", "reviewer")
certifier.add_link(swarm, "reviewer", "coordinator")
```

---

## API Reference

### Agent

```python
@dataclass
class Agent:
    id: str                          # Unique identifier
    name: str                        # Display name
    role: AgentRole = WORKER         # Agent role
    model: str = "claude-3-sonnet"   # LLM model
    provider: str = "bedrock"        # Provider (bedrock, openai, etc.)

    # RSN baseline for this agent's outputs
    baseline_R: float = 0.5
    baseline_S: float = 0.3
    baseline_N: float = 0.2
```

### Swarm

```python
@dataclass
class Swarm:
    id: str
    name: str
    agents: List[Agent]
    links: List[AgentLink]

    @property
    def kappa_swarm(self) -> float:
        """Swarm-level kappa = min across all links."""

    @property
    def weakest_link(self) -> Optional[AgentLink]:
        """Link with lowest kappa_interface."""
```

### Message

```python
@dataclass
class Message:
    id: str
    source_id: str
    target_id: str
    content: str

    # Filled after certification
    R: Optional[float]
    S: Optional[float]
    N: Optional[float]
    kappa: Optional[float]
    decision: Optional[str]  # EXECUTE, REPAIR, BLOCK, REJECT
    allowed: bool
```

### SwarmCertificate

```python
@dataclass
class SwarmCertificate:
    swarm_id: str
    timestamp: datetime

    kappa_swarm: float           # min(kappa_interface)
    total_messages: int
    blocked_messages: int

    link_kappas: Dict[str, float]  # Per-link κ
    weakest_link_id: Optional[str]

    swarm_healthy: bool          # kappa_swarm >= 0.6
    issues: List[str]            # Warnings/errors
```

### SwarmCertifier

```python
class SwarmCertifier:
    def __init__(self, engine=None):
        """Initialize with RSCTEngine (auto-created if None)."""

    def create_swarm(self, name: str, agents: List[Agent]) -> Swarm:
        """Create a new swarm with agents."""

    def add_link(self, swarm: Swarm, source_id: str, target_id: str) -> AgentLink:
        """Add communication link between agents."""

    def certify_message(
        self, swarm: Swarm, source_id: str, target_id: str, content: str
    ) -> Message:
        """Certify a message between agents."""

    def get_swarm_certificate(self, swarm: Swarm) -> SwarmCertificate:
        """Generate swarm-level certificate."""
```

---

## Integration Patterns

### Pattern 1: Pre-flight Certification

Certify before calling external LLM:

```python
def call_llm_certified(prompt: str, swarm, agent_id: str):
    # Certify first
    msg = certifier.certify_message(swarm, "user", agent_id, prompt)

    if not msg.allowed:
        raise BlockedError(f"Prompt blocked: {msg.decision}")

    # Safe to call LLM
    response = llm.invoke(prompt)
    return response
```

### Pattern 2: Request + Response Certification

Certify both directions:

```python
def certified_roundtrip(prompt: str, swarm, agent):
    # Certify request
    req = certifier.certify_message(swarm, "user", agent.id, prompt)
    if not req.allowed:
        return {"blocked": True, "reason": req.decision}

    # Call LLM
    response = llm.invoke(prompt)

    # Certify response
    resp = certifier.certify_message(swarm, agent.id, "user", response)

    return {
        "response": response,
        "request_kappa": req.kappa,
        "response_kappa": resp.kappa,
        "quality_verified": resp.allowed,
    }
```

### Pattern 3: Pipeline with Early Exit

Stop pipeline if any stage fails:

```python
def rag_pipeline(query: str, swarm):
    # Stage 1: Retrieve
    msg1 = certifier.certify_message(swarm, "user", "retriever", query)
    if not msg1.allowed:
        return {"stage": "retriever", "blocked": True}

    docs = retriever.search(query)

    # Stage 2: Synthesize
    context = f"Query: {query}\nDocs: {docs}"
    msg2 = certifier.certify_message(swarm, "retriever", "synthesizer", context)
    if not msg2.allowed:
        return {"stage": "synthesizer", "blocked": True}

    answer = synthesizer.generate(context)

    # Stage 3: Validate
    msg3 = certifier.certify_message(swarm, "synthesizer", "validator", answer)

    return {
        "answer": answer,
        "validated": msg3.allowed,
        "pipeline_kappa": min(msg1.kappa, msg2.kappa, msg3.kappa),
    }
```

---

## AWS Bedrock Integration

### Setup

```bash
pip install boto3
aws configure  # Set up credentials
```

### Usage

```python
import boto3
import json
from sidecar.a2a import SwarmCertifier, Agent, AgentRole

certifier = SwarmCertifier()

agent = Agent(
    id="analyst",
    name="Analyst",
    role=AgentRole.SPECIALIST,
    model="claude-3-sonnet",
    provider="bedrock",
)

swarm = certifier.create_swarm("bedrock-demo", [agent])
certifier.add_link(swarm, "user", "analyst")

# Certify before calling Bedrock
prompt = "Analyze market trends..."
msg = certifier.certify_message(swarm, "user", "analyst", prompt)

if msg.allowed:
    client = boto3.client('bedrock-runtime', region_name='us-east-1')

    response = client.invoke_model(
        modelId='anthropic.claude-3-sonnet-20240229-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }),
    )

    result = json.loads(response['body'].read())
    print(result['content'][0]['text'])
else:
    print(f"Blocked: {msg.decision}")
```

---

## LangChain Integration

```python
from langchain_openai import ChatOpenAI
from sidecar.a2a import SwarmCertifier, Agent, AgentRole

certifier = SwarmCertifier()

# Create agent for LangChain
lc_agent = Agent(id="langchain", name="LangChain Agent", role=AgentRole.WORKER)
swarm = certifier.create_swarm("langchain-demo", [lc_agent])
certifier.add_link(swarm, "user", "langchain")

llm = ChatOpenAI(model="gpt-4")

def certified_invoke(prompt: str):
    msg = certifier.certify_message(swarm, "user", "langchain", prompt)

    if not msg.allowed:
        raise ValueError(f"Blocked: {msg.decision}")

    return llm.invoke(prompt)

# Use it
try:
    response = certified_invoke("What is the capital of France?")
    print(response.content)
except ValueError as e:
    print(f"Request blocked: {e}")
```

---

## Monitoring & Observability

### Health Check

```python
cert = certifier.get_swarm_certificate(swarm)

print(f"Swarm: {cert.swarm_id}")
print(f"kappa_swarm: {cert.kappa_swarm:.2f}")
print(f"Healthy: {cert.swarm_healthy}")
print(f"Total messages: {cert.total_messages}")

# Check individual links
for link_id, kappa in cert.link_kappas.items():
    status = "OK" if kappa >= 0.5 else "WARN"
    print(f"  [{status}] {link_id}: κ={kappa:.2f}")

# Identify bottleneck
if cert.weakest_link_id:
    print(f"Weakest link: {cert.weakest_link_id}")

# Issues
for issue in cert.issues:
    print(f"Issue: {issue}")
```

### Export Certificate

```python
cert_dict = cert.to_dict()

# Save to JSON
import json
with open("swarm_cert.json", "w") as f:
    json.dump(cert_dict, f, indent=2)

# Send to monitoring system
import requests
requests.post("https://monitoring.example.com/certs", json=cert_dict)
```

---

## Security Considerations

### Attack Detection

The A2A system automatically detects and blocks:

| Attack Type | Detection Method |
|-------------|------------------|
| Prompt injection | Pattern matching + semantic analysis |
| Jailbreak attempts | Pattern + high N score |
| XSS/Script injection | Pattern detection |
| Data exfiltration | Semantic similarity to attack patterns |

### Best Practices

1. **Always certify before LLM calls** - Never send uncertified prompts to LLMs
2. **Monitor kappa_swarm** - Set alerts for κ < 0.5
3. **Review blocked messages** - Log and audit all blocked content
4. **Define strict topologies** - Only allow necessary agent-to-agent links
5. **Use role-based agents** - Assign appropriate roles for access control

---

## Examples

| Example | Description | File |
|---------|-------------|------|
| Basic Swarm | Simple agent-to-agent certification | `examples/a2a_swarm.py` |
| Bedrock Integration | AWS Bedrock with certification | `examples/a2a_bedrock.py` |
| RAG Pipeline | Retriever → Synthesizer → Validator | `examples/a2a_rag_swarm.py` |
| Hierarchical | Manager → Workers → Aggregator | `examples/a2a_hierarchical.py` |

Run examples:

```bash
PYTHONPATH="/path/to/yrsn/src:/path/to/yrsn/keys:." \
  python examples/a2a_swarm.py
```

---

## Troubleshooting

### Common Issues

**1. Import Error: `No module named 'yrsn'`**
```bash
export PYTHONPATH="/path/to/yrsn/src:$PYTHONPATH"
```

**2. API Key Error**
```bash
# Ensure yrsn/keys has OPENAI_API_KEY.txt
cat /path/to/yrsn/keys/OPENAI_API_KEY.txt
```

**3. Low kappa_swarm**
- Check which link has lowest κ: `cert.weakest_link_id`
- Review messages on that link for quality issues
- Consider adjusting prompts or adding validation

**4. False positives (good messages blocked)**
- Review the semantic analyzer thresholds
- Check pattern detection rules in `engine/patterns.py`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      sidecar/a2a/                           │
├─────────────────────────────────────────────────────────────┤
│  models.py       │ Agent, Swarm, Message, SwarmCertificate │
│  certifier.py    │ SwarmCertifier (orchestrates RSN)       │
├─────────────────────────────────────────────────────────────┤
│                      sidecar/engine/                        │
├─────────────────────────────────────────────────────────────┤
│  core.py         │ RSCTEngine (RSN computation)            │
│  patterns.py     │ Pattern detection (regex)               │
│  semantic.py     │ Semantic analysis (embedding similarity)│
├─────────────────────────────────────────────────────────────┤
│                      sidecar/adapters.py                    │
├─────────────────────────────────────────────────────────────┤
│  OpenAIEmbeddingAdapter  │ 384-dim embeddings              │
│  YRSNRotorAdapter        │ Trained 384→64→RSN pipeline     │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

- [ ] Add WebSocket support for real-time swarm monitoring
- [ ] Implement certificate persistence (S3/DynamoDB)
- [ ] Add OpenTelemetry instrumentation
- [ ] Support for dynamic swarm topology changes
- [ ] Dashboard integration for visualization
