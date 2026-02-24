# Sidecar Operations Guide

## Monitoring

### Health Endpoints

```bash
# Liveness
curl http://localhost:8080/health
# {"status": "healthy", "service": "swarm-it-sidecar"}

# Readiness
curl http://localhost:8080/ready
# {"status": "ready"}

# Statistics
curl http://localhost:8080/api/v1/statistics
# {"total_certificates": 1234, "thresholds": {...}, "failure_rates": {...}}
```

### Prometheus Metrics (coming soon)

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'swarm-it'
    static_configs:
      - targets: ['swarm-it:8080']
    metrics_path: /metrics
```

Expected metrics:
```
swarm_it_certifications_total{decision="EXECUTE"} 1234
swarm_it_certifications_total{decision="BLOCK"} 56
swarm_it_validation_failures_total{type="TYPE_I"} 12
swarm_it_certification_latency_seconds{quantile="0.99"} 0.05
```

---

## Logging

### Log Format

```json
{
  "timestamp": "2026-02-24T12:00:00Z",
  "level": "INFO",
  "event": "certification",
  "certificate_id": "a1b2c3d4",
  "decision": "EXECUTE",
  "kappa_gate": 0.72,
  "latency_ms": 15
}
```

### Log Levels

| Level | Use |
|-------|-----|
| DEBUG | Detailed RSN computation |
| INFO | Certifications, validations |
| WARN | Threshold adjustments |
| ERROR | Failed requests |

### Environment

```bash
export LOG_LEVEL=INFO
export LOG_FORMAT=json  # or "text"
```

---

## Scaling

### Horizontal Scaling

Sidecar is stateless (with external DB). Scale freely:

```yaml
# kubernetes
spec:
  replicas: 10
```

### With Shared Database

```yaml
services:
  swarm-it-1:
    image: swarmit/sidecar
    environment:
      SWARM_IT_DB_PATH: postgres://db:5432/swarmit

  swarm-it-2:
    image: swarmit/sidecar
    environment:
      SWARM_IT_DB_PATH: postgres://db:5432/swarmit

  db:
    image: postgres:15
```

### Load Balancing

```nginx
upstream swarm-it {
    least_conn;
    server swarm-it-1:8080;
    server swarm-it-2:8080;
    server swarm-it-3:8080;
}

server {
    location /api/ {
        proxy_pass http://swarm-it;
    }
}
```

---

## Backup & Recovery

### SQLite Backup

```bash
# Backup
sqlite3 /data/certificates.db ".backup /backup/certificates-$(date +%Y%m%d).db"

# Restore
cp /backup/certificates-20260224.db /data/certificates.db
```

### Postgres Backup

```bash
pg_dump swarmit > backup.sql
psql swarmit < backup.sql
```

---

## Troubleshooting

### Common Issues

#### 1. Connection Refused

```
httpx.ConnectError: Connection refused
```

**Fix:** Sidecar not running or wrong URL.

```bash
# Check if running
curl http://localhost:8080/health

# Check Docker
docker ps | grep swarm-it
```

#### 2. Certificate Not Found

```json
{"detail": "Certificate not found"}
```

**Fix:** Certificate expired from memory store, or wrong ID.

```bash
# Check if using persistent storage
echo $SWARM_IT_DB_PATH
```

#### 3. High Latency

**Check:**
1. Is DB on slow storage?
2. Is RSN computation heavy?
3. Network latency to sidecar?

```bash
# Profile request
time curl -X POST http://localhost:8080/api/v1/certify \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'
```

#### 4. Memory Growth

Memory store has LRU eviction (default 10k certs). If using SQLite:

```bash
# Check DB size
ls -lh /data/certificates.db

# Vacuum
sqlite3 /data/certificates.db "VACUUM;"
```

---

## Tuning

### Thresholds

```bash
# Via API
curl -X POST http://localhost:8080/api/v1/thresholds \
  -H "Content-Type: application/json" \
  -d '{"kappa_threshold": 0.8, "N_threshold": 0.4}'

# Via environment
export KAPPA_THRESHOLD=0.8
export N_THRESHOLD=0.4
```

### Performance

| Setting | Default | Tuning |
|---------|---------|--------|
| Workers | 1 | `--workers 4` for multi-core |
| Timeout | 30s | Reduce for fast-fail |
| DB Pool | 5 | Increase for high concurrency |

```bash
uvicorn main:app --workers 4 --timeout-keep-alive 5
```

---

## Disaster Recovery

### Scenario: Sidecar Down

**Impact:** LLM calls blocked (if hard dependency)

**Mitigation:**
```python
try:
    cert = swarm.certify(prompt)
except Exception:
    # Fallback: allow with logging
    logger.warning("Sidecar unavailable, allowing request")
    cert = None
```

### Scenario: Bad Threshold Deployed

**Impact:** Too many blocks or too many passes

**Recovery:**
```bash
# Reset to defaults
curl -X POST http://localhost:8080/api/v1/thresholds \
  -d '{"kappa_threshold": 0.7, "N_threshold": 0.5}'
```

### Scenario: Database Corruption

**Recovery:**
```bash
# Stop sidecar
docker-compose down

# Restore from backup
cp /backup/certificates-latest.db /data/certificates.db

# Restart
docker-compose up -d
```
