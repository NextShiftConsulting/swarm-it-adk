# Sidecar Requirements

## Input/Output Specifications

---

## 1. Certify (Pre-Execution Gate)

### Input

```json
POST /api/v1/certify
Content-Type: application/json

{
  "prompt": "string (required)",
  "model_id": "string (optional)",
  "context": "string (optional)",
  "swarm_id": "string (optional)",
  "policy": "string (optional, default: 'default')"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | ✅ | The prompt to certify |
| `model_id` | string | ❌ | Model identifier (e.g., "gpt-4", "claude-3") |
| `context` | string | ❌ | System prompt or context |
| `swarm_id` | string | ❌ | Multi-agent swarm identifier |
| `policy` | string | ❌ | Certification policy name |

### Output

```json
{
  "id": "a1b2c3d4e5f6g7h8",
  "timestamp": "2026-02-24T12:00:00Z",
  "R": 0.65,
  "S": 0.25,
  "N": 0.10,
  "kappa_gate": 0.72,
  "sigma": 0.35,
  "decision": "EXECUTE",
  "gate_reached": 5,
  "reason": "All gates passed",
  "allowed": true,
  "kappa_H": 0.80,
  "kappa_L": 0.72,
  "kappa_interface": 0.75,
  "weak_modality": "vision",
  "is_multimodal": true
}
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `id` | string | - | Unique certificate ID |
| `timestamp` | ISO8601 | - | When certified |
| `R` | float | [0, 1] | Relevance score |
| `S` | float | [0, 1] | Support score |
| `N` | float | [0, 1] | Noise score |
| `kappa_gate` | float | [0, 1] | Enforcement scalar (min of modalities) |
| `sigma` | float | [0, 1] | Stability score |
| `decision` | enum | see below | Gate decision |
| `gate_reached` | int | [1, 5] | Which gate was reached |
| `reason` | string | - | Human-readable explanation |
| `allowed` | bool | - | Can proceed with execution |
| `kappa_H` | float? | [0, 1] | High-level (text) compatibility |
| `kappa_L` | float? | [0, 1] | Low-level (vision) compatibility |
| `kappa_interface` | float? | [0, 1] | Cross-modal fusion quality |
| `weak_modality` | string? | - | Which modality is bottleneck |
| `is_multimodal` | bool | - | Has multimodal hierarchy |

### Decision Values

| Decision | Gate | Meaning | Action |
|----------|------|---------|--------|
| `REJECT` | 1 | Noise too high | Do not execute |
| `BLOCK` | 2 | Relevance too low | Do not execute |
| `DELEGATE` | 3 | Unstable | Route to specialist |
| `REPAIR` | 4 | Low compatibility | Re-encode or repair |
| `EXECUTE` | 5 | All gates passed | Safe to execute |

### Allowed Logic

```python
allowed = decision in ("EXECUTE", "REPAIR", "DELEGATE")
```

---

## 2. Validate (Post-Execution Feedback)

### Input

```json
POST /api/v1/validate
Content-Type: application/json

{
  "certificate_id": "a1b2c3d4e5f6g7h8",
  "validation_type": "TYPE_I",
  "score": 0.85,
  "failed": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `certificate_id` | string | ✅ | ID from certify response |
| `validation_type` | enum | ✅ | Type I-VI validation |
| `score` | float | ✅ | Validation score [0, 1] |
| `failed` | bool | ✅ | Whether validation failed |

### Validation Types

| Type | Name | Detects | Threshold Adjustment |
|------|------|---------|---------------------|
| `TYPE_I` | Groundedness | Unsupported claims | Tighten N_threshold |
| `TYPE_II` | Contradiction | Self-contradictions | Tighten kappa_L_threshold |
| `TYPE_III` | Inversion | Opposite meanings | Tighten c_threshold |
| `TYPE_IV` | Drift | Topic drift | Tighten sigma_thr |
| `TYPE_V` | Reasoning | Logic errors | Tighten sigma_thr |
| `TYPE_VI` | Domain | Out-of-domain | Tighten omega_threshold |

### Output

```json
{
  "recorded": true,
  "adjustment": {
    "type": "TYPE_I",
    "failure_rate": 0.15,
    "threshold": 0.10,
    "recommendation": "tighten"
  }
}
```

---

## 3. Audit (Compliance Export)

### Input

```json
POST /api/v1/audit
Content-Type: application/json

{
  "start_time": "2026-02-01T00:00:00Z",
  "end_time": "2026-02-24T23:59:59Z",
  "format": "SR11-7",
  "limit": 100
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_time` | ISO8601 | ❌ | Filter start |
| `end_time` | ISO8601 | ❌ | Filter end |
| `format` | string | ❌ | JSON, SR11-7, CSV |
| `limit` | int | ❌ | Max records |

### Output (SR 11-7 Format)

```json
{
  "certificate_count": 100,
  "format": "SR11-7",
  "records": [
    {
      "record_type": "MODEL_VALIDATION",
      "certificate_id": "a1b2c3d4e5f6g7h8",
      "timestamp": "2026-02-24T12:00:00Z",
      "quantitative_metrics": {
        "R": 0.65,
        "S": 0.25,
        "N": 0.10,
        "kappa_gate": 0.72,
        "sigma": 0.35
      },
      "gate_outcome": "EXECUTE",
      "gate_reached": 5,
      "risk_indicators": {
        "noise_level": "NORMAL",
        "stability": "STABLE"
      }
    }
  ]
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | HTTP port |
| `SWARM_IT_DB_PATH` | (memory) | SQLite path for persistence |
| `KAPPA_THRESHOLD` | 0.7 | Default kappa gate threshold |
| `N_THRESHOLD` | 0.5 | Noise rejection threshold |
| `SIGMA_THRESHOLD` | 0.7 | Stability threshold |

---

## Health Endpoints

```
GET /health    → {"status": "healthy"}
GET /ready     → {"status": "ready"}
```

---

## Error Responses

```json
{
  "detail": "Certificate not found"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request (validation error) |
| 404 | Certificate not found |
| 500 | Internal server error |

---

## Rate Limits

Default: None (add via reverse proxy)

Recommended production limits:
- `/certify`: 100 req/s per client
- `/validate`: 200 req/s per client
- `/audit`: 10 req/min per client
