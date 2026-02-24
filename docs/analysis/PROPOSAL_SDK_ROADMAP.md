# Swarm It SDK Roadmap Proposal

**Date:** 2026-02-24
**Author:** Claude Code / Rudy Martin
**Status:** DRAFT — Pending Dell Team Review
**Reference:** `swarm-it-gaps.md`, RSCT SOTA Paper v3

---

## 1. Problem Statement

The Swarm It SDK prototype demonstrates a functional certification client but has critical gaps between the theoretical foundation (RSCT) and productized implementation:

1. **No multi-agent support** — SDK gates single LLM calls; no swarm topology concept
2. **No local mode** — Cannot prove RSCT math without API infrastructure
3. **No compliance tooling** — Enterprise customers cannot use without audit trails
4. **No tests** — Cannot ship without verification

**Core issue:** We're marketing swarm governance but shipping single-call gating.

---

## 2. Proposed Architecture

### 2.1 SDK Layers

```
┌─────────────────────────────────────────────────────────┐
│                    User Application                      │
├─────────────────────────────────────────────────────────┤
│                    Swarm It SDK                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Decorators  │  │ Integrations│  │ Swarm Client    │  │
│  │ @gate       │  │ LangChain   │  │ certify_swarm() │  │
│  │ @certified  │  │ FastAPI     │  │ topology_view() │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
│         │                │                   │           │
│  ┌──────▼────────────────▼───────────────────▼────────┐ │
│  │                  Core Client                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │ │
│  │  │ API Mode    │  │ Local Mode  │  │ Hybrid     │  │ │
│  │  │ (Remote)    │  │ (Embedded)  │  │ (Fallback) │  │ │
│  │  └─────────────┘  └─────────────┘  └────────────┘  │ │
│  └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                  Persistence Layer                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Memory      │  │ SQLite      │  │ S3/DynamoDB     │  │
│  │ (Dev)       │  │ (Local)     │  │ (Production)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Multi-Agent Data Model

```python
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

class SolverType(Enum):
    TRANSFORMER = "transformer"
    SYMBOLIC = "symbolic"
    HYBRID = "hybrid"
    QUANTUM = "quantum"
    NEUROMORPHIC = "neuromorphic"

@dataclass
class Agent:
    """Single agent in a swarm."""
    id: str
    name: str
    role: str
    solver_type: SolverType

    # Per-modality health scores
    kappa_H: float  # High-level (text/symbolic)
    kappa_L: float  # Low-level (vision/signal)
    kappa_interface: float  # Cross-modal

    @property
    def kappa_gate(self) -> float:
        """Enforced score: min of all modalities."""
        return min(self.kappa_H, self.kappa_L, self.kappa_interface)

@dataclass
class AgentLink:
    """Communication channel between agents."""
    source_id: str
    target_id: str
    interface_type: str  # message, tool_call, memory_share, delegation
    kappa_interface: float  # Cross-agent compatibility
    latency_ms: Optional[float] = None

@dataclass
class Swarm:
    """Multi-agent swarm topology."""
    id: str
    name: str
    agents: List[Agent]
    links: List[AgentLink]

    @property
    def consensus(self) -> float:
        """Phasor coherence across swarm (c in RSCT)."""
        if not self.agents:
            return 0.0
        kappas = [a.kappa_gate for a in self.agents]
        # Simplified: use variance as proxy for coherence
        mean_k = sum(kappas) / len(kappas)
        variance = sum((k - mean_k)**2 for k in kappas) / len(kappas)
        return max(0.0, 1.0 - variance)

    @property
    def weakest_link(self) -> Optional[AgentLink]:
        """Identify lowest kappa_interface link."""
        if not self.links:
            return None
        return min(self.links, key=lambda l: l.kappa_interface)

@dataclass
class SwarmCertificate:
    """Certificate for entire swarm execution."""
    id: str
    timestamp: str
    swarm_id: str

    # Aggregate RSN
    R: float
    S: float
    N: float

    # Swarm-level metrics
    consensus: float
    kappa_gate_min: float  # Weakest agent
    kappa_interface_min: float  # Weakest link
    sigma_max: float  # Most turbulent agent

    # Gate result
    decision: str
    gate_reached: int
    reason: str

    # Per-agent breakdown
    agent_certificates: Dict[str, dict]

    # Topology snapshot
    topology_hash: str
```

---

## 3. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal:** Prove the math works, establish credibility.

| Task | Deliverable | Owner |
|------|-------------|-------|
| Local certification mode | `SwarmIt(mode="local")` with embedded rotor | TBD |
| Basic test suite | pytest for Certificate, client, decorators | TBD |
| 16-mode taxonomy | Port `classify_rsct()` from yrsn | TBD |
| Async decorator fix | `@gate` works with async functions | TBD |

**Success Criteria:**
- `pip install swarm-it && python -c "from swarm_it import SwarmIt; s = SwarmIt(mode='local'); print(s.certify('test').decision)"` works offline
- 80%+ test coverage on core modules
- Certificate includes `rsct.mode` field with 1-16 classification

---

### Phase 2: Multi-Agent (Week 3-4)

**Goal:** Implement the swarm differentiation.

| Task | Deliverable | Owner |
|------|-------------|-------|
| Agent/Swarm data model | `Agent`, `AgentLink`, `Swarm` classes | TBD |
| Swarm certification | `certify_swarm(swarm, task)` method | TBD |
| Topology serialization | JSON schema for swarm topology | TBD |
| Consensus computation | Phasor coherence algorithm | TBD |

**Success Criteria:**
- Can define a 3-agent swarm with links
- `certify_swarm()` returns `SwarmCertificate` with per-agent breakdown
- Weakest link identification works

---

### Phase 3: Persistence & Compliance (Week 5-6)

**Goal:** Enterprise-ready audit trail.

| Task | Deliverable | Owner |
|------|-------------|-------|
| Persistence interface | Abstract `CertificateStore` class | TBD |
| SQLite adapter | Local development storage | TBD |
| S3 adapter | Port from yrsn SERG | TBD |
| Certificate retrieval | `get_certificate(id)`, `list_certificates(filter)` | TBD |
| Audit log format | SR 11-7 compliant tuple structure | TBD |

**Success Criteria:**
- Certificates persist across SDK restarts
- Can retrieve certificate by ID
- Audit log matches RSCT paper format: $(\alpha, \omega, \alpha_\omega, \kappa_{\text{gate}}, \sigma, \texttt{gate\_reached}, \texttt{outcome}, t_{\text{stamp}})$

---

### Phase 4: Dashboard Integration (Week 7-8)

**Goal:** Connect SDK to swarm-it dashboard.

| Task | Deliverable | Owner |
|------|-------------|-------|
| Event schema | Certificate event JSON format | TBD |
| Webhook publisher | SDK pushes events to configured endpoint | TBD |
| WebSocket stream | Real-time certificate feed | TBD |
| Topology sync | Dashboard receives swarm topology updates | TBD |

**Success Criteria:**
- Dashboard shows live certificate stream from SDK
- Swarm topology visualization populates from SDK data
- Latency < 100ms from certification to dashboard update

---

### Phase 5: Observability & Cost (Week 9-10)

**Goal:** Production operational readiness.

| Task | Deliverable | Owner |
|------|-------------|-------|
| OpenTelemetry spans | Tracing for all certification calls | TBD |
| Prometheus metrics | `swarmit_*` metric family | TBD |
| Cost tracking | Token/cost telemetry per certificate | TBD |
| Savings calculator | Blocked request cost estimation | TBD |

**Success Criteria:**
- Grafana dashboard with SDK metrics
- Cost attribution by policy/user/session
- "Saved $X by blocking Y requests" metric available

---

## 4. Technical Decisions

### 4.1 Local Mode Implementation

**Option A:** Embed full HybridSimplexRotor (recommended)
- Pros: Real RSCT math, P15 compliant, consistent with API
- Cons: Larger package size (~50MB with PyTorch), slower import

**Option B:** Lightweight hash-based approximation
- Pros: Tiny package, fast import, no dependencies
- Cons: Not P15 compliant, divergent behavior from API

**Recommendation:** Ship both. Default to lightweight, allow `mode="local_full"` for embedded rotor.

### 4.2 Persistence Backend

**Option A:** SQLite default, S3 optional
- Pros: Works offline, simple setup
- Cons: Not cloud-native

**Option B:** S3/DynamoDB default, SQLite fallback
- Pros: Production-ready, scalable
- Cons: Requires AWS credentials

**Recommendation:** SQLite default for development, environment-based backend selection for production.

### 4.3 Multi-Agent Topology Format

**Proposed Schema (JSON):**
```json
{
  "swarm_id": "swarm-001",
  "agents": [
    {
      "id": "agent-planner",
      "role": "planner",
      "solver_type": "transformer",
      "kappa_H": 0.85,
      "kappa_L": 0.70,
      "kappa_interface": 0.90
    },
    {
      "id": "agent-executor",
      "role": "executor",
      "solver_type": "symbolic",
      "kappa_H": 0.60,
      "kappa_L": 0.95,
      "kappa_interface": 0.80
    }
  ],
  "links": [
    {
      "source": "agent-planner",
      "target": "agent-executor",
      "interface_type": "delegation",
      "kappa_interface": 0.75
    }
  ]
}
```

---

## 5. Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| httpx | ≥0.24 | HTTP client (already included) |
| torch | ≥2.0 | Local mode rotor (optional) |
| opentelemetry-api | ≥1.20 | Observability (optional) |
| prometheus-client | ≥0.17 | Metrics (optional) |
| boto3 | ≥1.28 | S3 persistence (optional) |

All new dependencies should be optional extras:
```bash
pip install swarm-it[local]       # torch
pip install swarm-it[observability]  # otel + prometheus
pip install swarm-it[aws]         # boto3
pip install swarm-it[all]         # everything
```

---

## 6. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test coverage | ≥80% | pytest-cov |
| Local mode latency | <10ms | Benchmark suite |
| API mode latency | <100ms | Benchmark suite |
| Swarm certification | <50ms for 10 agents | Benchmark suite |
| Package size (core) | <1MB | pip download |
| Package size (full) | <100MB | pip download |

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PyTorch size bloats package | High | Medium | Make local_full optional |
| Multi-agent model too complex | Medium | High | Start with 2-agent case, iterate |
| Dashboard schema drift | Medium | Medium | Define shared schema early |
| SR 11-7 compliance unclear | Low | High | Engage compliance consultant |

---

## 8. Open Questions for Dell Team

1. **Priority:** Should we prioritize local mode (proves math) or multi-agent (proves positioning)?

2. **Dashboard integration:** Is the dashboard team ready to receive webhook/WebSocket events? What's their schema expectation?

3. **Compliance:** Do we have access to SR 11-7 / EU AI Act compliance expertise for audit format validation?

4. **Deployment:** Target deployment model — PyPI public, private registry, or both?

5. **Timeline:** Is the 10-week phased approach acceptable, or do we need to compress?

---

## 9. Next Steps

1. **Immediate:** Dell team review this proposal
2. **This week:** Decide Phase 1 ownership and start
3. **Week 2:** Phase 1 deliverables complete, demo to stakeholders
4. **Ongoing:** Weekly sync on progress and blockers

---

## Appendix A: File Structure After Implementation

```
sdk/
├── swarm_it/
│   ├── __init__.py
│   ├── client.py              # Core client (exists)
│   ├── certificate.py         # Certificate classes (extract from client)
│   ├── decorators.py          # Gate decorators (exists)
│   ├── exceptions.py          # Exceptions (exists)
│   │
│   ├── swarm/                  # NEW: Multi-agent
│   │   ├── __init__.py
│   │   ├── agent.py           # Agent, AgentLink classes
│   │   ├── topology.py        # Swarm class, serialization
│   │   └── certification.py   # certify_swarm()
│   │
│   ├── local/                  # NEW: Local mode
│   │   ├── __init__.py
│   │   ├── rotor.py           # Embedded HybridSimplexRotor
│   │   └── fallback.py        # Hash-based fallback
│   │
│   ├── persistence/            # NEW: Storage
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract CertificateStore
│   │   ├── memory.py          # In-memory (default)
│   │   ├── sqlite.py          # SQLite adapter
│   │   └── s3.py              # S3 adapter
│   │
│   ├── compliance/             # NEW: Audit/compliance
│   │   ├── __init__.py
│   │   ├── audit_log.py       # SR 11-7 format
│   │   └── reports.py         # Report generation
│   │
│   ├── observability/          # NEW: Telemetry
│   │   ├── __init__.py
│   │   ├── tracing.py         # OpenTelemetry
│   │   └── metrics.py         # Prometheus
│   │
│   └── integrations/           # Exists
│       ├── __init__.py
│       ├── langchain.py
│       └── fastapi.py
│
├── tests/                      # NEW
│   ├── __init__.py
│   ├── test_client.py
│   ├── test_certificate.py
│   ├── test_decorators.py
│   ├── test_swarm.py
│   ├── test_local.py
│   └── test_persistence.py
│
├── examples/                   # Exists
├── pyproject.toml              # Exists
└── README.md                   # Exists
```

---

## Appendix B: References

- RSCT SOTA Paper: `/Users/rudy/GitHub/yrsn/docs/primary/SOTA_Intelligence as Representation-Solver Compatibility.tex`
- Gap Analysis: `/Users/rudy/GitHub/swarm-it/docs/analysis/swarm-it-gaps.md`
- SERG Handlers: `/Users/rudy/GitHub/yrsn/src/yrsn/api/serg/`
- Product Outline: `/Users/rudy/GitHub/swarm-it/OUTLINE.md`
