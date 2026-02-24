# Security Guide

## Credential Management

### P17 Principle: Config Manager as Single Gateway

**ALL credential access MUST flow through `config_manager.py`.**

```python
# ✅ CORRECT
from config.config_manager import get_config
config = get_config()
api_key = config.openai_api_key

# ❌ WRONG - Bypasses config_manager
import os
api_key = os.getenv('OPENAI_API_KEY')
```

### Credential Priority (3-Tier)

Config manager checks sources in order:

1. **Environment variables** (highest priority)
   - `SWARM_IT_OPENAI_API_KEY`
   - `OPENAI_API_KEY` (fallback)

2. **Config file** (medium priority)
   - `swarm_it_config.yaml`

3. **Defaults** (lowest priority)
   - Built-in defaults

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `SWARM_IT_OPENAI_API_KEY` | OpenAI API key |
| `SWARM_IT_ANTHROPIC_API_KEY` | Anthropic API key |
| `SWARM_IT_API_KEY_REQUIRED` | Enable API key auth |
| `SWARM_IT_API_KEYS` | Comma-separated valid keys |
| `SWARM_IT_DB_PATH` | SQLite database path |
| `SWARM_IT_DB_URL` | Postgres connection URL |

---

## Config File Template

Create `swarm_it_config.yaml`:

```yaml
# DO NOT COMMIT THIS FILE WITH REAL CREDENTIALS

environment: dev

server:
  host: 0.0.0.0
  port: 8080
  grpc_port: 9090

database:
  # path: ./certificates.db  # SQLite
  # url: postgres://user:pass@host:5432/swarmit  # Postgres

thresholds:
  kappa: 0.7
  N: 0.5
  sigma: 0.7

llm:
  provider: openai
  model: text-embedding-3-small
  # openai_api_key: sk-...  # Better: use env var

auth:
  api_key_required: false
  # api_keys:
  #   - key1
  #   - key2
```

---

## Deployment Security

### Docker

```yaml
# docker-compose.yml
services:
  swarm-it:
    image: swarmit/sidecar
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}  # From host env
      - SWARM_IT_API_KEY_REQUIRED=true
      - SWARM_IT_API_KEYS=${SWARM_IT_API_KEYS}
    # Don't mount secrets as files
```

### Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: swarm-it-secrets
type: Opaque
stringData:
  openai-api-key: sk-...
  api-keys: key1,key2
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: swarm-it
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: swarm-it-secrets
              key: openai-api-key
        - name: SWARM_IT_API_KEY_REQUIRED
          value: "true"
        - name: SWARM_IT_API_KEYS
          valueFrom:
            secretKeyRef:
              name: swarm-it-secrets
              key: api-keys
```

### AWS

Use IAM roles, not hardcoded credentials:

```yaml
# Lambda / ECS task role
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue"
  ],
  "Resource": "arn:aws:secretsmanager:*:*:secret:swarm-it/*"
}
```

---

## API Authentication

### Enable API Key Auth

```bash
export SWARM_IT_API_KEY_REQUIRED=true
export SWARM_IT_API_KEYS=key1,key2,key3
```

### Client Usage

```python
import httpx

response = httpx.post(
    "http://localhost:8080/api/v1/certify",
    headers={"X-API-Key": "key1"},
    json={"prompt": "..."}
)
```

---

## Pre-Commit Hook

The repository includes a pre-commit hook that blocks commits containing:

- OpenAI API keys (`sk-...`)
- AWS credentials (`AKIA...`)
- GitHub tokens (`ghp_...`)
- Private keys

To install:

```bash
cp .git/hooks/pre-commit.sample .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## Security Checklist

- [ ] Never commit credentials to git
- [ ] Use environment variables in production
- [ ] Enable API key authentication
- [ ] Use IAM roles (not keys) on AWS
- [ ] Rotate API keys regularly
- [ ] Enable TLS in production (via reverse proxy)
- [ ] Set up log monitoring for auth failures
- [ ] Use secrets manager for production credentials

---

## Incident Response

If credentials are exposed:

1. **Rotate immediately** - Generate new keys
2. **Revoke old keys** - In provider dashboard
3. **Audit logs** - Check for unauthorized usage
4. **Git history** - Use `git filter-branch` or BFG to remove
5. **Notify** - If customer data may be affected
