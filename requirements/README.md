# Requirements Guide

This directory contains tiered requirements for different use cases.

## Installation Tiers

### Tier 1: Base (Minimal)

**Install**: `pip install -r requirements/base.txt`

**What Works**:
- Core LocalEngine certification
- Structured error handling
- Circuit breakers
- Audit logging
- Chaos engineering
- Local storage
- Email notifications (SMTP)

**What Doesn't Work**:
- Input validation (needs pydantic)
- Caching (needs Redis)
- Async processing (needs Celery)
- Rate limiting (needs Redis)
- Cloud storage (needs cloud SDKs)
- Monitoring (needs Prometheus)
- Tracing (needs OpenTelemetry)

**Use Cases**:
- Development and testing
- Learning and experimentation
- Minimal dependencies required

---

### Tier 2: Recommended (Default)

**Install**: `pip install -r requirements/recommended.txt` or `pip install -r requirements.txt`

**Adds**:
- Input validation (Pydantic)
- Health checks with memory/disk monitoring (psutil)
- Prometheus metrics collection (prometheus-client)

**What Works**:
- Everything in Tier 1
- Pydantic validation
- Health endpoint with system metrics
- Prometheus metrics export

**Use Cases**:
- Development with validation
- Simple production deployments
- Single-server setups

---

### Tier 3: Performance

**Install**: `pip install -r requirements/performance.txt`

**Adds**:
- Redis caching (5x latency reduction)
- Celery async processing (10x throughput)
- Rate limiting

**External Services Required**:
- Redis server
- RabbitMQ (for Celery)

**What Works**:
- Everything in Tier 2
- Multi-layer caching
- Async batch processing
- Distributed rate limiting

**Use Cases**:
- High-volume production (100+ req/min)
- Performance-critical applications
- Multi-instance deployments

---

### Tier 4: Observability

**Install**: `pip install -r requirements/observability.txt`

**Adds**:
- OpenTelemetry distributed tracing
- Jaeger/Zipkin export
- Request instrumentation

**External Services Required**:
- Jaeger or Zipkin server
- Redis (from Tier 3)
- RabbitMQ (from Tier 3)

**What Works**:
- Everything in Tier 3
- End-to-end distributed tracing
- Performance bottleneck identification
- Service dependency mapping

**Use Cases**:
- Production deployments needing observability
- Microservices architectures
- Performance debugging

---

### Tier 5: Cloud

**Install**: `pip install -r requirements/cloud.txt`

**Adds**:
- AWS S3 storage
- Google Cloud Storage
- Azure Blob storage
- Hashicorp Vault secrets
- Webhook notifications

**External Services Required**:
- AWS account (for S3, Secrets Manager)
- GCP account (for Cloud Storage)
- Azure account (for Blob Storage)
- Hashicorp Vault instance

**What Works**:
- Everything in Tier 4
- Multi-cloud evidence storage
- Vault/AWS secrets management
- Webhook notifications (Slack, PagerDuty, etc.)

**Use Cases**:
- Multi-cloud deployments
- Enterprise security requirements
- Compliance requirements (SR 11-7)

---

### Tier 6: UI

**Install**: `pip install -r requirements/ui.txt`

**Adds**:
- Streamlit interactive playground
- Jupyter notebook support

**What Works**:
- Everything in Tier 5
- Web-based certification playground
- Interactive notebooks for experimentation

**Use Cases**:
- Developer onboarding
- Demos and presentations
- Interactive testing

---

### Tier 7: Development

**Install**: `pip install -r requirements/dev.txt`

**Adds**:
- Testing frameworks (pytest)
- Linting tools (black, ruff, mypy)
- Documentation tools (mkdocs)

**What Works**:
- Everything in Tier 6
- Unit and integration testing
- Code quality checks
- Documentation generation

**Use Cases**:
- Contributing to swarm-it-adk
- Running test suites
- Documentation updates

---

## Quick Start Guide

### Minimal Setup (No External Services)

```bash
# Install base requirements
pip install -r requirements/base.txt

# Test core functionality
python -c "from swarm_it.local.engine import certify_local; print(certify_local('test'))"
```

### Recommended Setup (With Validation)

```bash
# Install recommended requirements
pip install -r requirements/recommended.txt

# Test validation
python -c "from swarm_it.validation import validate_certify_request; print('Validation works!')"
```

### Production Setup (With Performance)

```bash
# Install performance requirements
pip install -r requirements/performance.txt

# Start Redis (required)
docker run -d -p 6379:6379 redis:latest

# Start RabbitMQ (required for async)
docker run -d -p 5672:5672 rabbitmq:latest

# Test caching
python -c "from swarm_it.caching import CacheClient; print('Caching works!')"
```

### Full Setup (Everything)

```bash
# Install all requirements
pip install -r requirements/dev.txt

# Run comprehensive tests
python test_real_implementation.py
```

---

## Feature → Requirements Matrix

| Feature | Requirements File | External Services |
|---------|------------------|-------------------|
| Core certification | base.txt | None |
| Validation | recommended.txt | None |
| Caching | performance.txt | Redis |
| Async processing | performance.txt | Redis, RabbitMQ |
| Rate limiting | performance.txt | Redis |
| Secrets (Vault) | cloud.txt | Hashicorp Vault |
| Secrets (AWS) | cloud.txt | AWS Secrets Manager |
| Tracing | observability.txt | Jaeger/Zipkin |
| Monitoring | recommended.txt | None (Prometheus scrapes) |
| Storage (S3) | cloud.txt | AWS S3 |
| Storage (GCS) | cloud.txt | Google Cloud Storage |
| Storage (Azure) | cloud.txt | Azure Blob Storage |
| Storage (local) | base.txt | None |
| Notifications (Slack) | cloud.txt | Slack webhook |
| Notifications (PagerDuty) | cloud.txt | PagerDuty API |
| Notifications (email) | base.txt | SMTP server |
| Playground | ui.txt | None |
| Circuit breakers | base.txt | None |
| Audit logging | base.txt | None |
| Chaos engineering | base.txt | None |
| Errors | base.txt | None |
| Health checks (basic) | base.txt | None |
| Health checks (full) | recommended.txt | None |

---

## Troubleshooting

### Import Errors

If you see:
```
ImportError: No module named 'redis'
```

**Solution**: Install the appropriate requirements tier:
```bash
pip install -r requirements/performance.txt
```

### OpenTelemetry Import Errors

OpenTelemetry has many packages. If you see:
```
ImportError: No module named 'opentelemetry.exporter.jaeger'
```

**Solution**: Install observability requirements:
```bash
pip install -r requirements/observability.txt
```

### Version Conflicts

If you see version conflicts between packages:

**Solution**: Use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements/<tier>.txt
```

---

## Version Pinning

All requirements use minimum version specifiers (`>=`) for flexibility. For production deployments, consider pinning exact versions:

```bash
# Generate pinned requirements
pip freeze > requirements-pinned.txt
```

---

## Docker Setup

For containerized deployments with all services:

```bash
# Create docker-compose.yml with Redis, RabbitMQ, Jaeger
docker-compose up -d

# Install full requirements
pip install -r requirements/cloud.txt
```

See `docker-compose.yml` (if available) for service configuration.
