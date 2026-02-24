# Swarm-It

**RSCT Certification for AI/LLM Execution Governance**

[![Patent Pending](https://img.shields.io/badge/Patent-Pending-blue)](PATENT_NOTICE.md)

---

## What Is This?

Swarm-It is a **sidecar service** that certifies AI/LLM calls before execution. Think of it as a safety gate that answers: "Should I run this prompt?"

```
┌─────────────────────────────────────┐
│     Your AI App (any language)      │
├─────────────────────────────────────┤
│         Swarm-It Sidecar            │
│   Certify → Execute → Validate      │
└─────────────────────────────────────┘
```

**Inspired by Tendermint:** Just as Tendermint separated consensus from application (ABCI), Swarm-It separates certification from AI execution.

---

## Quick Start (30 seconds)

```bash
# 1. Start sidecar
cd sidecar
docker-compose up -d

# 2. Test it
curl http://localhost:8080/health
# {"status": "healthy"}

# 3. Certify a prompt
curl -X POST http://localhost:8080/api/v1/certify \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?"}'
# {"id": "abc123", "decision": "EXECUTE", "allowed": true, ...}
```

---

## Integration (Python)

```bash
pip install httpx  # Thin client has no dependencies except HTTP
```

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

## Why Sidecar?

| Library (import) | Sidecar (service) |
|------------------|-------------------|
| Python only | Any language |
| Per-process state | Centralized |
| Redeploy all apps | Update one container |
| Scattered logs | Single audit point |

---

## SGCI: Three Methods

**Swarm Gate Certification Interface** (like Tendermint's ABCI):

| Method | When | Purpose |
|--------|------|---------|
| `Certify` | Pre-execution | Should I run this prompt? |
| `Validate` | Post-execution | How did the output perform? |
| `Audit` | Compliance | Export certificates for SR 11-7 |

---

## Gate Decisions

| Decision | Gate | Meaning |
|----------|------|---------|
| `EXECUTE` | 5 | All checks passed - safe to run |
| `REPAIR` | 4 | Low compatibility - re-encode first |
| `DELEGATE` | 3 | Unstable - route to specialist |
| `BLOCK` | 2 | Relevance too low |
| `REJECT` | 1 | Noise too high - do not run |

---

## Clients

| Language | Package |
|----------|---------|
| Python | `clients/python/` |
| TypeScript | `clients/typescript/` |
| Go | `clients/go/` |
| Rust | `clients/rust/` |

---

## Deployment

```bash
# Docker
docker run -p 8080:8080 swarmit/sidecar

# Kubernetes (sidecar pattern)
# See docs/sidecar_analysis/DEPLOYMENT.md
```

---

## Metrics

```
GET /metrics

swarm_it_certifications_total{decision="EXECUTE"} 1234
swarm_it_certification_latency_seconds{quantile="0.99"} 0.015
```

---

## Documentation

- [Requirements (I/O specs)](docs/sidecar_analysis/REQUIREMENTS.md)
- [Deployment Guide](docs/sidecar_analysis/DEPLOYMENT.md)
- [Integration Examples](docs/sidecar_analysis/INTEGRATION.md)
- [Operations](docs/sidecar_analysis/OPERATIONS.md)
- [Architecture](docs/architecture/SIDECAR_ARCHITECTURE.md)

---

## License

Patent Pending. See [PATENT_NOTICE.md](PATENT_NOTICE.md).

© 2026 Next Shift Consulting LLC
