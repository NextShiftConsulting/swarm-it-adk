# Swarm‑It Sidecar

**RSCT certification as a deployable HTTP sidecar.**

Swarm‑It runs as a **sidecar service** that certifies AI/LLM calls before execution.

```
┌─────────────────────────────────────┐
│     Your AI App (any language)      │
├─────────────────────────────────────┤
│         Swarm‑It Sidecar            │
│   Certify → Execute → Validate      │
└─────────────────────────────────────┘
```

> **Compute boundary:** the sidecar depends on `yrsn` for RSN decomposition / rotor / κ metrics.

## Quick start

```bash
docker-compose up -d

curl http://localhost:8080/health
# {"status": "healthy"}

curl -X POST http://localhost:8080/api/v1/certify \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?"}'
```

## API surface (stable)

Swarm Gate Certification Interface (SGCI):

| Method | When | Purpose |
|---|---|---|
| `POST /api/v1/certify` | Pre‑execution | Should I run this prompt? |
| `POST /api/v1/validate` | Post‑execution | Feedback loop / evaluation |
| `POST /api/v1/audit` | Compliance | Export certificates |

Other helpful endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Healthcheck |
| `GET /metrics` | Prometheus metrics |
| `GET /api/v1/statistics` | Basic stats |
| `GET /api/v1/certificates/{id}` | Fetch certificate |

## Gate decisions

| Decision | Gate | Meaning |
|---|---:|---|
| `EXECUTE` | 5 | All checks passed |
| `REPAIR` | 4 | Low compatibility — re‑encode first |
| `DELEGATE` | 3 | Unstable — route to specialist |
| `BLOCK` | 2 | Relevance too low |
| `REJECT` | 1 | Noise too high |

## Deployment

- Local: `docker-compose.yml` in this folder
- Docs: `docs/sidecar_analysis/DEPLOYMENT.md`
