# GitHub Copilot SDK Ideas for swarm-it-adk

**Date**: 2026-03-03
**Purpose**: Analyze GitHub Copilot SDK for patterns/features to adopt in swarm-it-adk
**Status**: PROPOSAL

---

## Executive Summary

GitHub Copilot SDK (released January 2026) provides a production-tested agentic engine with multi-platform support. This analysis identifies **5 high-value patterns** that can be directly adapted for swarm-it-adk with minimal effort.

**Quick Wins** (Easiest to implement):
1. JSON-RPC communication protocol (replace REST-only)
2. BYOK (Bring Your Own Key) credential pattern
3. Lifecycle management API (sidecar process control)
4. Multi-turn conversation state management
5. Runtime model selection interface

---

## 1. JSON-RPC Communication Protocol

### What Copilot Does

Copilot SDK uses **JSON-RPC 2.0** for client-server communication:

```
Client → JSON-RPC request → Copilot CLI (server mode)
```

**Benefits**:
- Language-agnostic (no REST-specific knowledge needed)
- Bi-directional communication (server can push notifications)
- Streaming support for long-running operations
- Standard error codes

### Current swarm-it-adk State

From `docs/architecture/SIDECAR_ARCHITECTURE.md`:
- REST API (implemented)
- gRPC API (planned)
- No JSON-RPC support

### Proposed Implementation

**Add JSON-RPC transport alongside REST/gRPC:**

```python
# sidecar/api/jsonrpc_server.py
from jsonrpc import JSONRPCResponseManager, dispatcher
from werkzeug.wrappers import Request, Response

@dispatcher.add_method
def certify(prompt: str, model_id: str = None, context: str = None):
    """JSON-RPC method: swarm.certify"""
    from sidecar.engine.rsct import certify_prompt
    cert = certify_prompt(prompt, model_id, context)
    return cert.to_dict()

@dispatcher.add_method
def validate(certificate_id: str, validation_type: str, score: float, failed: bool):
    """JSON-RPC method: swarm.validate"""
    from sidecar.engine.rsct import record_validation
    result = record_validation(certificate_id, validation_type, score, failed)
    return {"recorded": result}

@Request.application
def application(request):
    response = JSONRPCResponseManager.handle(
        request.data, dispatcher)
    return Response(response.json, mimetype='application/json')

# Run on port 8081 (alongside REST on 8080)
if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('localhost', 8081, application)
```

**Client Example (Python):**

```python
# clients/python/swarm_it/jsonrpc_client.py
import requests
import json

class JSONRPCClient:
    def __init__(self, url="http://localhost:8081"):
        self.url = url
        self.id = 0

    def _call(self, method: str, **params):
        self.id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.id
        }
        response = requests.post(self.url, json=payload)
        result = response.json()
        if "error" in result:
            raise Exception(result["error"])
        return result["result"]

    def certify(self, prompt: str, model_id: str = None):
        return self._call("certify", prompt=prompt, model_id=model_id)

    def validate(self, certificate_id: str, validation_type: str, score: float, failed: bool):
        return self._call("validate",
            certificate_id=certificate_id,
            validation_type=validation_type,
            score=score,
            failed=failed)

# Usage
client = JSONRPCClient()
cert = client.certify("What is 2+2?")
print(cert["decision"])  # EXECUTE
```

**Effort**: LOW (1-2 days)
- Existing Python libraries: `python-jsonrpc`, `werkzeug`
- Protocol is simple (just wrap existing functions)
- No changes to core RSCT logic needed

**Benefits**:
- Matches Copilot SDK architecture
- Better for streaming (certificates with partial results)
- Easier to version methods independently
- Standard error handling

---

## 2. BYOK (Bring Your Own Key) Pattern

### What Copilot Does

Copilot SDK supports **BYOK** for direct LLM provider integration:

```python
# Option 1: GitHub authentication (default)
client = CopilotClient()

# Option 2: BYOK (direct OpenAI/Anthropic/Azure)
client = CopilotClient(
    provider="openai",
    api_key="sk-..."
)
```

**Key insight**: Users can run Copilot engine WITHOUT GitHub subscription if they bring their own LLM keys.

### Current swarm-it-adk State

From `adk/README.md`:
- Requires `api_key` (implies centralized API)
- Local mode exists (hash-based fallback)
- No BYOK pattern

### Proposed Implementation

**Add credential passthrough to sidecar:**

```python
# adk/swarm_it/client.py
from typing import Optional, Dict

class SwarmIt:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        byok: Optional[Dict[str, str]] = None,  # NEW
        mode: str = "api",  # api | local | byok
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.byok_credentials = byok
        self.mode = mode

        # Determine runtime mode
        if byok:
            self.mode = "byok"
            self.engine = self._init_byok_engine(byok)
        elif mode == "local":
            self.engine = LocalEngine()
        else:
            self.engine = APIClient(api_key, base_url)

    def _init_byok_engine(self, byok_config: Dict[str, str]):
        """Initialize local RSCT engine with user's LLM credentials."""
        from yrsn.core.decomposition import HybridSimplexRotor
        from swarm_it.local.byok_engine import BYOKEngine

        # User brings their own embedding provider
        return BYOKEngine(
            rotor=HybridSimplexRotor.from_checkpoint("trained_rotor_universal64.pt"),
            llm_provider=byok_config.get("provider"),  # openai | anthropic | mimo
            llm_api_key=byok_config.get("api_key"),
            embedding_model=byok_config.get("embedding_model", "text-embedding-3-small")
        )

# Usage Example 1: Standard API mode
swarm = SwarmIt(api_key="swarm-it-key")

# Usage Example 2: BYOK mode (no swarm-it subscription needed)
swarm = SwarmIt(byok={
    "provider": "openai",
    "api_key": "sk-...",
    "embedding_model": "text-embedding-3-small"
})

# Usage Example 3: BYOK with MIMO
swarm = SwarmIt(byok={
    "provider": "mimo",
    "api_key": os.environ["MIMO_API_KEY"],
    "embedding_model": "mimo-embed-v1"
})
```

**BYOK Engine Implementation:**

```python
# adk/swarm_it/local/byok_engine.py
import torch
from typing import Dict, Any
from yrsn.core.decomposition import HybridSimplexRotor

class BYOKEngine:
    """Local RSCT engine using customer's LLM credentials."""

    def __init__(self, rotor: HybridSimplexRotor, llm_provider: str, llm_api_key: str, embedding_model: str):
        self.rotor = rotor
        self.llm_provider = llm_provider
        self.llm_api_key = llm_api_key
        self.embedding_model = embedding_model

        # Initialize embedding client
        if llm_provider == "openai":
            from openai import OpenAI
            self.embed_client = OpenAI(api_key=llm_api_key)
        elif llm_provider == "mimo":
            from openai import OpenAI
            self.embed_client = OpenAI(
                base_url="https://api.mimo.ai/v1",
                api_key=llm_api_key
            )
        else:
            raise ValueError(f"Unsupported provider: {llm_provider}")

    def certify(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate certificate using user's embedding provider."""
        # 1. Get embedding using customer's API key
        response = self.embed_client.embeddings.create(
            input=prompt,
            model=self.embedding_model
        )
        embedding = torch.tensor(response.data[0].embedding)

        # 2. Decompose using yrsn rotor (local, no API call)
        R, S, N = self.rotor.decompose(embedding)

        # 3. Compute metrics
        alpha = R / (R + N) if (R + N) > 0 else 0.0
        kappa = min(R, S)  # Simplified
        sigma = N / (R + S + N)

        # 4. Apply gate logic
        decision = "EXECUTE" if kappa >= 0.7 else "REJECT"

        # 5. Return certificate
        return {
            "id": f"cert-{hash(prompt)}",
            "R": float(R),
            "S": float(S),
            "N": float(N),
            "alpha": float(alpha),
            "kappa": float(kappa),
            "sigma": float(sigma),
            "decision": decision,
            "allowed": decision == "EXECUTE",
            "reason": "kappa gate passed" if decision == "EXECUTE" else "kappa below threshold",
            "raw": {
                "_byok_mode": True,
                "_provider": self.llm_provider,
                "_embedding_model": self.embedding_model,
                "_cost_usd": 0.00002  # Approximate embedding cost
            }
        }
```

**Effort**: MEDIUM (3-5 days)
- Requires embedding provider integrations (OpenAI, MIMO)
- RSCT math already exists in yrsn (HybridSimplexRotor)
- Need to handle different embedding dimensions

**Benefits**:
- Users can use swarm-it WITHOUT subscription (lower barrier to entry)
- Proves RSCT math works (not black-box API)
- Better for enterprise customers with existing LLM contracts
- Reduces swarm-it API costs (customer pays their LLM provider)

**Trade-offs**:
- Embedding quality varies by provider
- No centralized audit trail (unless user stores locally)
- Support burden (customer LLM API issues)

---

## 3. Lifecycle Management API

### What Copilot Does

Copilot SDK automatically manages the CLI process lifecycle:

```typescript
// SDK handles starting/stopping CLI server
const client = new CopilotClient({
  mode: "managed"  // SDK launches copilot CLI in server mode
});

// On client.close(), SDK stops CLI process
await client.close();
```

**Alternative**: External CLI server mode (user manages process).

### Current swarm-it-adk State

From `sidecar/README.md`:
- User must run `docker-compose up` manually
- No programmatic lifecycle control
- SDK assumes sidecar is already running

### Proposed Implementation

**Add sidecar lifecycle management to SDK:**

```python
# adk/swarm_it/sidecar_manager.py
import subprocess
import time
import requests
from typing import Optional

class SidecarManager:
    """Manages swarm-it sidecar process lifecycle."""

    def __init__(self, mode: str = "docker", port: int = 8080):
        self.mode = mode  # docker | binary | external
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.container_id: Optional[str] = None

    def start(self, timeout: int = 30):
        """Start sidecar process."""
        if self.mode == "docker":
            self._start_docker()
        elif self.mode == "binary":
            self._start_binary()
        else:
            raise ValueError(f"Unsupported mode: {self.mode}")

        # Wait for health check
        self._wait_for_ready(timeout)

    def _start_docker(self):
        """Start sidecar via docker run."""
        cmd = [
            "docker", "run", "-d",
            "-p", f"{self.port}:8080",
            "--name", "swarm-it-sidecar",
            "swarmit/sidecar:latest"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start docker: {result.stderr}")
        self.container_id = result.stdout.strip()

    def _start_binary(self):
        """Start sidecar as subprocess."""
        cmd = ["swarm-it-sidecar", "--port", str(self.port)]
        self.process = subprocess.Popen(cmd)

    def _wait_for_ready(self, timeout: int):
        """Poll health endpoint until ready."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = requests.get(f"http://localhost:{self.port}/health")
                if response.status_code == 200:
                    return
            except requests.ConnectionError:
                pass
            time.sleep(0.5)
        raise TimeoutError("Sidecar failed to start within timeout")

    def stop(self):
        """Stop sidecar process."""
        if self.container_id:
            subprocess.run(["docker", "stop", self.container_id])
            subprocess.run(["docker", "rm", self.container_id])
        elif self.process:
            self.process.terminate()
            self.process.wait()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

# Usage Example 1: Managed mode (SDK controls sidecar)
from swarm_it import SwarmIt
from swarm_it.sidecar_manager import SidecarManager

with SidecarManager(mode="docker") as sidecar:
    client = SwarmIt(base_url="http://localhost:8080")
    cert = client.certify("test prompt")
    print(cert.decision)
# Sidecar automatically stopped

# Usage Example 2: External mode (user manages sidecar)
client = SwarmIt(base_url="http://my-sidecar:8080")
cert = client.certify("test prompt")
```

**Effort**: LOW (2-3 days)
- Simple subprocess/docker management
- Health check polling already common pattern
- Context manager for cleanup

**Benefits**:
- Better developer experience (no manual docker commands)
- Enables testing without external dependencies
- Matches Copilot SDK UX

---

## 4. Multi-Turn Conversation State Management

### What Copilot Does

Copilot SDK maintains conversation state across turns:

```typescript
const conversation = client.createConversation();

// Turn 1
await conversation.send("What is quantum computing?");

// Turn 2 (has context from turn 1)
await conversation.send("Can you give an example?");

// Turn 3
await conversation.send("Explain the math.");

// Get full history
const history = conversation.getHistory();
```

**Key insight**: State is managed CLIENT-SIDE, not server-side (stateless server).

### Current swarm-it-adk State

From `adk/README.md`:
- `swarm.certify(prompt)` is stateless
- No conversation threading
- No context accumulation

### Proposed Implementation

**Add conversation context to SDK:**

```python
# adk/swarm_it/conversation.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ConversationTurn:
    """Single turn in conversation."""
    turn_id: int
    prompt: str
    certificate: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

class Conversation:
    """Multi-turn conversation with certificate history."""

    def __init__(self, client, conversation_id: Optional[str] = None):
        self.client = client
        self.conversation_id = conversation_id or f"conv-{hash(datetime.utcnow())}"
        self.turns: List[ConversationTurn] = []

    def send(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Send prompt and track in conversation history."""
        # Add conversation context to certification
        context = self._build_context()
        cert = self.client.certify(
            prompt=prompt,
            context=context,
            **kwargs
        )

        # Record turn
        turn = ConversationTurn(
            turn_id=len(self.turns) + 1,
            prompt=prompt,
            certificate=cert
        )
        self.turns.append(turn)

        return cert

    def _build_context(self) -> str:
        """Build conversation context from previous turns."""
        if not self.turns:
            return ""

        # Include last 3 turns for context
        recent_turns = self.turns[-3:]
        context_parts = []
        for turn in recent_turns:
            context_parts.append(f"Turn {turn.turn_id}: {turn.prompt}")
            context_parts.append(f"  -> Decision: {turn.certificate['decision']}")

        return "\n".join(context_parts)

    def get_history(self) -> List[ConversationTurn]:
        """Get full conversation history."""
        return self.turns

    def get_quality_trend(self) -> Dict[str, List[float]]:
        """Analyze quality metrics over conversation."""
        return {
            "kappa": [turn.certificate.get("kappa", 0.0) for turn in self.turns],
            "alpha": [turn.certificate.get("alpha", 0.0) for turn in self.turns],
            "sigma": [turn.certificate.get("sigma", 0.0) for turn in self.turns],
        }

    def summary(self) -> Dict[str, Any]:
        """Get conversation summary."""
        total_turns = len(self.turns)
        blocked = sum(1 for t in self.turns if not t.certificate.get("allowed", True))

        return {
            "conversation_id": self.conversation_id,
            "total_turns": total_turns,
            "blocked_turns": blocked,
            "success_rate": (total_turns - blocked) / total_turns if total_turns > 0 else 0,
            "quality_trend": self.get_quality_trend(),
        }

# Usage
from swarm_it import SwarmIt

client = SwarmIt()
conv = client.create_conversation()

# Multi-turn conversation
cert1 = conv.send("What is quantum computing?")
cert2 = conv.send("Can you give an example?")  # Has context from cert1
cert3 = conv.send("Explain the math.")  # Has context from cert1 + cert2

# Analyze conversation
summary = conv.summary()
print(f"Success rate: {summary['success_rate']:.1%}")
print(f"Quality trend: {summary['quality_trend']['kappa']}")
```

**Integration with SwarmIt client:**

```python
# adk/swarm_it/client.py
class SwarmIt:
    # ... existing code ...

    def create_conversation(self, conversation_id: str = None):
        """Create a new conversation context."""
        from swarm_it.conversation import Conversation
        return Conversation(client=self, conversation_id=conversation_id)
```

**Effort**: LOW (1-2 days)
- Pure client-side state management
- No server changes needed
- Builds on existing `certify()` method

**Benefits**:
- Better for multi-agent swarms (track agent-to-agent handoffs)
- Quality trends show degradation over conversation
- Matches Copilot SDK UX

---

## 5. Runtime Model Selection Interface

### What Copilot Does

Copilot SDK exposes **available models at runtime**:

```typescript
// Get available models
const models = await client.getModels();
// ["gpt-4", "gpt-4-turbo", "claude-3-opus", ...]

// Use specific model for request
await client.chat({
  model: "gpt-4-turbo",
  messages: [...]
});
```

**Key insight**: Model selection is dynamic (not hardcoded in SDK).

### Current swarm-it-adk State

From `adk/README.md`:
- No model selection interface
- Implies single backend model
- Policy-based thresholds, but not model-based

### Proposed Implementation

**Add model/policy registry to sidecar:**

```python
# sidecar/api/models.py
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class CertificationModel:
    """Available certification model configuration."""
    id: str
    name: str
    description: str
    rotor_checkpoint: str
    thresholds: Dict[str, float]
    cost_per_cert: float  # USD

# Registry of available models
CERTIFICATION_MODELS = [
    CertificationModel(
        id="universal64",
        name="Universal Rotor (64-dim)",
        description="Multi-architecture rotor for general use",
        rotor_checkpoint="trained_rotor_universal64.pt",
        thresholds={"kappa": 0.7, "R": 0.3, "S": 0.4, "N": 0.5},
        cost_per_cert=0.001
    ),
    CertificationModel(
        id="strict",
        name="Strict Policy",
        description="Tighter thresholds for safety-critical applications",
        rotor_checkpoint="trained_rotor_universal64.pt",
        thresholds={"kappa": 0.85, "R": 0.5, "S": 0.6, "N": 0.3},
        cost_per_cert=0.001
    ),
    CertificationModel(
        id="permissive",
        name="Permissive Policy",
        description="Looser thresholds for experimentation",
        rotor_checkpoint="trained_rotor_universal64.pt",
        thresholds={"kappa": 0.5, "R": 0.2, "S": 0.3, "N": 0.7},
        cost_per_cert=0.001
    ),
]

def get_models() -> List[Dict[str, Any]]:
    """Return available certification models."""
    return [
        {
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "thresholds": m.thresholds,
            "cost_per_cert": m.cost_per_cert,
        }
        for m in CERTIFICATION_MODELS
    ]

def get_model(model_id: str) -> CertificationModel:
    """Get specific model configuration."""
    for model in CERTIFICATION_MODELS:
        if model.id == model_id:
            return model
    raise ValueError(f"Unknown model: {model_id}")
```

**REST Endpoint:**

```python
# sidecar/api/rest.py
from fastapi import FastAPI
from sidecar.api.models import get_models, get_model

app = FastAPI()

@app.get("/v1/models")
async def list_models():
    """List available certification models."""
    return {"models": get_models()}

@app.post("/v1/certify")
async def certify(
    prompt: str,
    model: str = "universal64",  # Default model
    context: str = None
):
    """Certify with specific model."""
    from sidecar.engine.rsct import certify_with_model

    model_config = get_model(model)
    cert = certify_with_model(prompt, model_config, context)

    return {
        "certificate": cert.to_dict(),
        "model_used": model,
        "cost_usd": model_config.cost_per_cert,
    }
```

**Client Integration:**

```python
# clients/python/swarm_it/client.py
class SwarmIt:
    def __init__(self, base_url: str = "http://localhost:8080", **kwargs):
        self.base_url = base_url
        self._models_cache = None

    def get_models(self) -> List[Dict[str, Any]]:
        """Get available certification models."""
        if not self._models_cache:
            response = requests.get(f"{self.base_url}/v1/models")
            self._models_cache = response.json()["models"]
        return self._models_cache

    def certify(self, prompt: str, model: str = "universal64", **kwargs):
        """Certify with specific model."""
        response = requests.post(
            f"{self.base_url}/v1/certify",
            json={"prompt": prompt, "model": model, **kwargs}
        )
        return response.json()

# Usage
client = SwarmIt()

# Discover models
models = client.get_models()
for model in models:
    print(f"{model['id']}: {model['name']} (κ >= {model['thresholds']['kappa']})")

# Use specific model
cert = client.certify("risky prompt", model="strict")  # Tighter thresholds
```

**Effort**: LOW (1-2 days)
- Mostly configuration management
- RSCT engine already exists
- Simple JSON endpoint

**Benefits**:
- Users can choose policy (strict vs permissive)
- Easier A/B testing of threshold tuning
- Future: support multiple rotor checkpoints (vision vs text)

---

## Summary: Implementation Priority

| Feature | Effort | Value | Priority |
|---------|--------|-------|----------|
| **Runtime Model Selection** | LOW (1-2d) | HIGH | **1** (Quick win) |
| **Lifecycle Management** | LOW (2-3d) | MEDIUM | **2** (UX improvement) |
| **Multi-Turn Conversations** | LOW (1-2d) | MEDIUM | **3** (Agent coordination) |
| **JSON-RPC Protocol** | LOW (1-2d) | MEDIUM | **4** (Architecture alignment) |
| **BYOK Pattern** | MEDIUM (3-5d) | HIGH | **5** (Strategic, requires design) |

---

## Recommended Next Steps

### Week 1: Quick Wins (Priority 1-3)

**Day 1-2**: Runtime Model Selection
- [ ] Create model registry (`sidecar/api/models.py`)
- [ ] Add `/v1/models` endpoint
- [ ] Update client with `get_models()` method
- [ ] Document model selection in README

**Day 3-4**: Lifecycle Management
- [ ] Create `SidecarManager` class
- [ ] Implement docker mode
- [ ] Add health check polling
- [ ] Write examples for managed vs external mode

**Day 5**: Multi-Turn Conversations
- [ ] Create `Conversation` class
- [ ] Add `client.create_conversation()` method
- [ ] Implement quality trend tracking
- [ ] Add conversation summary

### Week 2: Architecture Alignment (Priority 4-5)

**Day 1-2**: JSON-RPC Protocol
- [ ] Add JSON-RPC server (`sidecar/api/jsonrpc_server.py`)
- [ ] Create JSON-RPC client
- [ ] Document protocol in architecture docs
- [ ] Add to docker-compose (port 8081)

**Day 3-5**: BYOK Pattern (Design & Prototype)
- [ ] Design BYOK credential flow
- [ ] Implement `BYOKEngine` class
- [ ] Add OpenAI embedding integration
- [ ] Add MIMO embedding integration
- [ ] Document trade-offs and limitations

---

## References

- **GitHub Copilot SDK Announcement**: https://github.blog/news-insights/company-news/build-an-agent-into-any-app-with-the-github-copilot-sdk/
- **Copilot SDK Technical Preview**: https://github.blog/changelog/2026-01-14-copilot-sdk-in-technical-preview/
- **swarm-it-adk Sidecar Architecture**: `docs/architecture/SIDECAR_ARCHITECTURE.md`
- **swarm-it-adk Roadmap**: `docs/analysis/PROPOSAL_SDK_ROADMAP.md`
- **Tendermint ABCI Lessons**: `docs/sidecar_analysis/LESSONS_FROM_TENDERMINT.md`

---

**CONCLUSION**: GitHub Copilot SDK validates the sidecar + thin-client architecture we're already building. The 5 features identified above are **direct adoptions** (not just inspiration) that can be implemented with minimal effort (1-2 weeks total). Priority 1-3 (model selection, lifecycle, conversations) are the quickest wins.
