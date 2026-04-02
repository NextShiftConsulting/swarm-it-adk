# Certificate Layering Architecture

## The Rule

**yrsn owns the certificate.**

- **rsct** exposes a curated subset for external integration
- **Internal consumers** (ADK, SERG, orchestration) use yrsn's certificate directly

No merging. No composition wrappers. No inheritance hierarchies. Just two views of the same source at different levels of detail.

## The Two Views

```
┌─────────────────────────────────────────────────────┐
│  yrsn.YRSNCertificate (full, internal)              │
│  - R, S, N, kappa_gate, sigma                       │
│  - kappa_H, kappa_L, kappa_interface                │
│  - alpha, omega, tau                                │
│  - admissibility, quality_envelope, lyapunov        │
│  - gate results, routing, stability metrics         │
└─────────────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌───────────────────┐         ┌─────────────────────┐
│ rsct (external)   │         │ Internal consumers  │
│                   │         │                     │
│ Curated subset:   │         │ ADK, SERG, swarm-it │
│ - R, S, N         │         │ orchestration, etc. │
│ - kappa_gate      │         │                     │
│ - gates           │         │ Use YRSNCertificate │
│ - routing         │         │ directly            │
└───────────────────┘         └─────────────────────┘
```

## Who Uses What

| Consumer | Certificate | Why |
|----------|-------------|-----|
| External partners | rsct.RSCTCertificate | Curated API, stable contract |
| ADK | yrsn.YRSNCertificate | Full access, internal |
| SERG | yrsn.YRSNCertificate | Needs stability metrics |
| swarm-it-api | yrsn.YRSNCertificate | Production service |
| Orchestration | yrsn.YRSNCertificate | Needs all signals |

## What rsct Exposes

rsct is the **external SDK**. It exposes:
- Core simplex (R, S, N)
- Compatibility gate (kappa_gate)
- Gate evaluation logic
- Routing decisions

It does **not** expose internal signals (admissibility, lyapunov, kappa decomposition) that external consumers don't need.

## What This Means for ADK

The ADK is an internal consumer. It should:

```python
# CORRECT: Use yrsn directly
from yrsn.certificate import YRSNCertificate

def certify(context: str) -> YRSNCertificate:
    ...
```

Not:

```python
# WRONG: Wrapper around wrapper
from rsct import RSCTCertificate

class ADKCertificate:
    core: RSCTCertificate  # unnecessary indirection
```

## Summary

| Package | Role | Certificate |
|---------|------|-------------|
| yrsn | Owns it | YRSNCertificate (canonical) |
| rsct | External SDK | RSCTCertificate (curated subset) |
| ADK | Internal client | Uses YRSNCertificate directly |
