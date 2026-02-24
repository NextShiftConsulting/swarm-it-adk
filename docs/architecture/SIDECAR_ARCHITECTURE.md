# Swarm-It Sidecar Architecture

**Date:** 2026-02-24
**Status:** Proposal
**Inspiration:** Tendermint ABCI model

---

## The Tendermint Insight

Tendermint succeeded because it separated **consensus** from **application**:

```
┌─────────────────┐
│   Your App      │  ← Any language, any framework
├─────────────────┤
│     ABCI        │  ← 3 methods: CheckTx, DeliverTx, Commit
├─────────────────┤
│   Tendermint    │  ← Runs as separate process
└─────────────────┘
```

**Key properties:**
1. Language agnostic (gRPC/socket)
2. One job done well (BFT consensus)
3. Batteries included (networking, persistence)
4. Simple mental model

---

## Swarm-It Sidecar Model

Apply same pattern to RSCT certification:

```
┌─────────────────────────────────────────────┐
│              Your AI Application            │
│  (LangChain, CrewAI, AutoGen, custom, etc.) │
├─────────────────────────────────────────────┤
│              Swarm-It Client                │
│        (thin SDK - any language)            │
├─────────────────────────────────────────────┤
│                   SGCI                      │
│    (Swarm Gate Certification Interface)    │
│         gRPC / REST / WebSocket             │
├─────────────────────────────────────────────┤
│            Swarm-It Sidecar                 │
│     Docker container / binary / k8s pod    │
│                                             │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ RSCT Engine │  │ Certificate Store    │  │
│  │ (yrsn core) │  │ (SQLite/Postgres)    │  │
│  └─────────────┘  └──────────────────────┘  │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ Audit Log   │  │ Feedback Loop        │  │
│  │ (SR 11-7)   │  │ (threshold tuning)   │  │
│  └─────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## SGCI: Swarm Gate Certification Interface

Analogous to Tendermint's ABCI. Three core methods:

### 1. Certify (pre-execution)

```protobuf
rpc Certify(CertifyRequest) returns (Certificate);

message CertifyRequest {
  string prompt = 1;
  string model_id = 2;
  optional string context = 3;
  optional SwarmTopology swarm = 4;
}

message Certificate {
  string id = 1;
  float R = 2;
  float S = 3;
  float N = 4;
  float kappa_gate = 5;
  GateDecision decision = 6;
  string reason = 7;

  // Hierarchy block (multimodal)
  optional float kappa_H = 8;
  optional float kappa_L = 9;
  optional float kappa_interface = 10;
}

enum GateDecision {
  EXECUTE = 0;
  REPAIR = 1;
  DELEGATE = 2;
  BLOCK = 3;
  REJECT = 4;
}
```

### 2. Validate (post-execution feedback)

```protobuf
rpc Validate(ValidateRequest) returns (ValidateResponse);

message ValidateRequest {
  string certificate_id = 1;
  ValidationType type = 2;  // TYPE_I through TYPE_VI
  float score = 3;
  bool failed = 4;
}

message ValidateResponse {
  bool recorded = 1;
  optional ThresholdAdjustment adjustment = 2;
}
```

### 3. Audit (compliance export)

```protobuf
rpc Audit(AuditRequest) returns (AuditResponse);

message AuditRequest {
  string start_time = 1;
  string end_time = 2;
  string format = 3;  // "SR11-7", "JSON", "CSV"
}

message AuditResponse {
  bytes report = 1;
  int32 certificate_count = 2;
}
```

---

## Deployment Modes

### 1. Sidecar (recommended)

```yaml
# docker-compose.yml
services:
  my-ai-app:
    image: my-ai-app:latest
    environment:
      SWARM_IT_URL: http://swarm-it:8080
    depends_on:
      - swarm-it

  swarm-it:
    image: swarmit/sidecar:latest
    ports:
      - "8080:8080"   # REST
      - "9090:9090"   # gRPC
    volumes:
      - ./data:/data  # Certificate store
    environment:
      SWARM_IT_MODE: sidecar
      KAPPA_THRESHOLD: 0.7
```

### 2. Kubernetes Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ai-workload
spec:
  containers:
  - name: ai-app
    image: my-ai-app:latest
    env:
    - name: SWARM_IT_URL
      value: "http://localhost:8080"

  - name: swarm-it
    image: swarmit/sidecar:latest
    ports:
    - containerPort: 8080
```

### 3. Embedded (single process)

For simple cases, SDK can run engine in-process:

```python
from swarm_it import LocalEngine

engine = LocalEngine()  # No sidecar needed
cert = engine.certify(prompt)
```

---

## Thin Client SDKs

With sidecar handling the work, SDKs become trivial:

### Python

```python
from swarm_it import SwarmIt

swarm = SwarmIt(url="http://localhost:8080")
cert = swarm.certify(prompt)

if cert.allowed:
    response = my_llm(prompt)
    swarm.validate(cert.id, type="TYPE_I", score=0.9, failed=False)
```

### TypeScript

```typescript
import { SwarmIt } from '@swarmit/client';

const swarm = new SwarmIt({ url: 'http://localhost:8080' });
const cert = await swarm.certify(prompt);

if (cert.allowed) {
  const response = await myLLM(prompt);
  await swarm.validate(cert.id, { type: 'TYPE_I', score: 0.9 });
}
```

### Go

```go
client := swarmit.NewClient("http://localhost:8080")
cert, _ := client.Certify(ctx, prompt)

if cert.Allowed {
    response := myLLM(prompt)
    client.Validate(ctx, cert.ID, swarmit.TypeI, 0.9, false)
}
```

### Rust

```rust
let client = SwarmIt::new("http://localhost:8080");
let cert = client.certify(&prompt).await?;

if cert.allowed {
    let response = my_llm(&prompt).await?;
    client.validate(&cert.id, ValidationType::TypeI, 0.9, false).await?;
}
```

---

## Why This Wins

| Property | Library Model | Sidecar Model |
|----------|---------------|---------------|
| Language support | Python only | Any language |
| Deployment | Import in each service | One container |
| State management | Per-process | Centralized |
| Upgrades | Redeploy all apps | Update sidecar only |
| Observability | Scattered | Single point |
| Resource isolation | Shared with app | Dedicated |

---

## Implementation Phases

### Phase 1: Core Sidecar (MVP)

- [ ] REST API (Certify, Validate, Audit)
- [ ] Docker image
- [ ] Python thin client
- [ ] SQLite persistence

### Phase 2: Production Ready

- [ ] gRPC API
- [ ] Postgres support
- [ ] Health checks / readiness probes
- [ ] Prometheus metrics
- [ ] TypeScript client

### Phase 3: Enterprise

- [ ] Multi-tenant
- [ ] RBAC
- [ ] Distributed tracing
- [ ] Go / Rust clients
- [ ] Helm chart

---

## File Structure

```
swarm-it/
├── sidecar/
│   ├── Dockerfile
│   ├── main.py              # FastAPI/gRPC server
│   ├── api/
│   │   ├── rest.py          # REST endpoints
│   │   ├── grpc_server.py   # gRPC server
│   │   └── proto/
│   │       └── sgci.proto   # SGCI definitions
│   ├── engine/
│   │   └── rsct.py          # RSCT computation (wraps yrsn)
│   └── store/
│       └── certificates.py  # Persistence
│
├── clients/
│   ├── python/
│   │   └── swarm_it/
│   │       └── client.py    # Thin client
│   ├── typescript/
│   │   └── src/
│   │       └── client.ts
│   ├── go/
│   │   └── client.go
│   └── rust/
│       └── src/
│           └── lib.rs
│
└── sdk/                      # Current SDK (becomes embedded mode)
    └── swarm_it/
        └── local/
            └── engine.py
```

---

## Next Steps

1. Create `sidecar/` directory structure
2. Implement REST API with FastAPI
3. Create Dockerfile
4. Refactor Python SDK to be thin client
5. Test with docker-compose
