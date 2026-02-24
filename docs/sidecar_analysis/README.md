# Swarm-It Sidecar Analysis

**For:** Teams integrating RSCT certification into their AI systems
**Status:** Production-ready MVP
**Last Updated:** 2026-02-24

---

## Quick Links

| Document | Purpose |
|----------|---------|
| [REQUIREMENTS.md](./REQUIREMENTS.md) | Input/output specs, API contracts |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Docker, K8s, MCP, standalone |
| [INTEGRATION.md](./INTEGRATION.md) | LangChain, CrewAI, custom frameworks |
| [OPERATIONS.md](./OPERATIONS.md) | Monitoring, scaling, troubleshooting |

---

## What Is This?

Swarm-It Sidecar is a **standalone certification service** for AI/LLM execution governance.

**The Tendermint Insight:** Just as Tendermint separated consensus from application logic (ABCI), Swarm-It separates **certification** from **AI execution**.

```
┌─────────────────────────────────────┐
│     Your AI App (any language)      │
│  LangChain, CrewAI, AutoGen, etc.   │
├─────────────────────────────────────┤
│           Thin Client               │
│   Python, TypeScript, Go, Rust      │
├─────────────────────────────────────┤
│         SGCI (REST/gRPC)            │
│   Certify, Validate, Audit          │
├─────────────────────────────────────┤
│       Swarm-It Sidecar              │
│   Docker / K8s / MCP Server         │
└─────────────────────────────────────┘
```

---

## Why Sidecar vs Library?

| Property | Library (import) | Sidecar (service) |
|----------|------------------|-------------------|
| Language | Python only | Any |
| State | Per-process | Centralized |
| Upgrades | Redeploy all apps | Update one container |
| Observability | Scattered logs | Single point |
| Compliance | Hard to audit | One audit endpoint |

---

## Core Concept: SGCI

**Swarm Gate Certification Interface** - three methods:

1. **Certify** - Pre-execution: "Should I run this prompt?"
2. **Validate** - Post-execution: "How did the output perform?"
3. **Audit** - Compliance: "Export all certificates for SR 11-7"

This mirrors Tendermint's ABCI (CheckTx, DeliverTx, Commit).

---

## 30-Second Integration

```python
from swarm_it import SwarmIt

swarm = SwarmIt(url="http://localhost:8080")

# Before LLM call
cert = swarm.certify("Summarize this document")

if cert.allowed:
    response = my_llm(prompt)

    # After LLM call (feedback loop)
    swarm.validate(cert.id, "TYPE_I", score=0.9)
else:
    print(f"Blocked: {cert.reason}")
```

---

## Next Steps

1. **Read [REQUIREMENTS.md](./REQUIREMENTS.md)** - understand I/O
2. **Read [DEPLOYMENT.md](./DEPLOYMENT.md)** - pick your deployment model
3. **Read [INTEGRATION.md](./INTEGRATION.md)** - connect your framework
