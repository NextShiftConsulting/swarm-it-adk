# Security Guide

**swarm-it-adk Security Best Practices**

Based on RSCT-certified security team recommendations (4 agents, 100% success rate, CVSS scores up to 8.1).

---

## Critical Security Features (Week 1)

### 1. Rate Limiting (CVSS 7.5 - High)

**Problem**: Certification endpoints vulnerable to DDoS and brute-force attacks.

**Solution**: Multi-tier rate limiting with Redis backend.

#### Quick Start

```python
from swarm_it_adk.rate_limiting import RateLimiter, RateLimitConfig

# Configure rate limiter
config = RateLimitConfig(
    requests_per_minute=100,      # 100 requests per minute per IP
    requests_per_hour=5000,        # 5000 requests per hour
    requests_per_day=100000,       # 100k requests per day
    redis_host="localhost",
    redis_port=6379
)

limiter = RateLimiter(config)

# Check IP rate limit
result = limiter.check_ip("192.168.1.1")
if not result.allowed:
    print(f"Rate limit exceeded. Retry after {result.retry_after} seconds")
else:
    print(f"Allowed. {result.remaining} requests remaining")
```

#### Production Configuration

```python
# config/production.py
from swarm_it_adk.rate_limiting import RateLimitConfig, RateLimitStrategy

RATE_LIMIT_CONFIG = RateLimitConfig(
    # Limits
    requests_per_minute=100,
    requests_per_hour=5000,
    requests_per_day=100000,

    # Strategy (sliding window recommended)
    strategy=RateLimitStrategy.SLIDING_WINDOW,

    # Redis (distributed rate limiting)
    redis_host="redis.production.example.com",
    redis_port=6379,
    redis_db=1,
    redis_password=os.getenv("REDIS_PASSWORD"),

    # Behavior
    block_duration_seconds=60,
    enable_whitelist=True,
    enable_blacklist=True
)
```

#### Whitelist/Blacklist Management

```python
# Whitelist trusted IPs (unlimited requests)
limiter.add_to_whitelist("10.0.0.1")  # Internal monitoring
limiter.add_to_whitelist("trusted-user-123")

# Blacklist malicious actors
limiter.add_to_blacklist("203.0.113.0")  # DDoS attacker
```

#### Integration with FastAPI

```python
from fastapi import FastAPI, Request, HTTPException
from swarm_it_adk.rate_limiting import get_global_limiter, RateLimitExceeded

app = FastAPI()
limiter = get_global_limiter()

@app.post("/certify")
async def certify(request: Request):
    # Check IP rate limit
    result = limiter.check_ip(request.client.host)

    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": result.retry_after,
                "limit": result.limit,
                "reset_at": result.reset_at.isoformat()
            },
            headers={"Retry-After": str(result.retry_after)}
        )

    # Process certification
    return {"status": "ok"}
```

---

### 2. Secrets Management (CVSS 8.1 - High)

**Problem**: API keys stored in plaintext environment variables, vulnerable to theft.

**Solution**: Hashicorp Vault or AWS Secrets Manager integration.

#### Option A: Hashicorp Vault (Recommended)

**Setup Vault**:

```bash
# Start Vault dev server
docker run --cap-add=IPC_LOCK -d -p 8200:8200 \
    --name=vault \
    vault server -dev

# Get root token
docker logs vault | grep "Root Token"
```

**Store Secrets**:

```python
from swarm_it_adk.secrets import create_vault_manager

# Initialize Vault manager
manager = create_vault_manager(
    url="http://localhost:8200",
    token="your_root_token"
)

# Store API keys
manager.set("api_keys/openai", "sk-...")
manager.set("api_keys/anthropic", "sk-ant-...")
manager.set("database/password", "secure_password")
```

**Retrieve Secrets**:

```python
# Get API key (cached for 5 minutes)
openai_key = manager.get("api_keys/openai")

# Use in certification
from openai import OpenAI
client = OpenAI(api_key=openai_key)
```

**Rotate Secrets**:

```python
# Rotate API key every 90 days
manager.rotate("api_keys/openai", "sk-new-key-...")

# Verify rotation
secret = manager.provider.get_secret("api_keys/openai")
print(f"Rotated at: {secret.metadata.get('rotated_at')}")
```

#### Option B: AWS Secrets Manager

**Setup**:

```bash
# Create secret in AWS
aws secretsmanager create-secret \
    --name prod/api_keys/openai \
    --secret-string '{"value":"sk-..."}'
```

**Usage**:

```python
from swarm_it_adk.secrets import create_aws_manager

# Initialize AWS manager (uses IAM role in production)
manager = create_aws_manager(region="us-east-1")

# Get secret
openai_key = manager.get("prod/api_keys/openai")

# Rotate secret
manager.rotate("prod/api_keys/openai", "sk-new-key-...")
```

#### Production Configuration

```python
# config/production.py
from swarm_it_adk.secrets import SecretConfig, SecretBackend

SECRETS_CONFIG = SecretConfig(
    backend=SecretBackend.VAULT,

    # Vault configuration
    vault_url=os.getenv("VAULT_URL", "https://vault.production.example.com"),
    vault_token=os.getenv("VAULT_TOKEN"),  # Use AppRole in production
    vault_namespace="production",
    vault_mount_point="secret",

    # Caching (reduces Vault calls)
    cache_ttl_seconds=300,  # 5 minutes

    # Rotation
    enable_rotation=True,
    rotation_days=90
)
```

#### Migration from Environment Variables

**Before (INSECURE)**:

```python
import os
openai_key = os.getenv("OPENAI_API_KEY")  # Plaintext, vulnerable
```

**After (SECURE)**:

```python
from swarm_it_adk.secrets import SecretManager

manager = SecretManager(SECRETS_CONFIG)
openai_key = manager.get("api_keys/openai")  # Encrypted, rotatable
```

**Migration Script**:

```python
# migrate_secrets.py
import os
from swarm_it_adk.secrets import create_vault_manager

manager = create_vault_manager(
    url=os.getenv("VAULT_URL"),
    token=os.getenv("VAULT_TOKEN")
)

# Migrate environment variables to Vault
secrets_to_migrate = {
    "OPENAI_API_KEY": "api_keys/openai",
    "ANTHROPIC_API_KEY": "api_keys/anthropic",
    "DATABASE_PASSWORD": "database/password"
}

for env_var, vault_path in secrets_to_migrate.items():
    value = os.getenv(env_var)
    if value:
        manager.set(vault_path, value)
        print(f"Migrated {env_var} → {vault_path}")
```

---

## Additional Security Features

### 3. Input Validation (Implemented in Phase 1)

**Prevents**: SQL injection, XSS, path traversal, malformed input

```python
from swarm_it_adk.validation import CertifyRequest

# Automatic validation
request = CertifyRequest(
    prompt="Your text here",
    model="gpt-4",  # Validates alphanumeric only
    kappa=0.9       # Validates 0.0-1.0 range
)
```

### 4. Structured Error Handling (Implemented in Phase 1)

**Prevents**: Information disclosure, debugging in production

```python
from swarm_it_adk.errors import CertificationError, ErrorCode

try:
    result = certifier.certify(prompt)
except CertificationError as e:
    # Structured error with safe message
    return {
        "error_code": e.code.value,  # E201, E301, etc.
        "message": e.message,         # Safe for user
        "guidance": e.guidance        # Actionable steps
        # NO sensitive stack traces or internal details
    }
```

---

## Security Checklist

### Development

- [ ] Use Vault or AWS Secrets Manager (NOT environment variables)
- [ ] Enable rate limiting on all public endpoints
- [ ] Validate all user input with Pydantic
- [ ] Use structured error messages (no stack traces)
- [ ] Enable HTTPS for all connections
- [ ] Set secure cookie flags (HttpOnly, Secure, SameSite)

### Staging

- [ ] Test rate limiting under load
- [ ] Verify secrets rotation works
- [ ] Audit logging enabled
- [ ] Security headers configured (HSTS, CSP, etc.)
- [ ] Penetration testing completed
- [ ] Dependency vulnerability scan (pip-audit, safety)

### Production

- [ ] Vault/AWS Secrets Manager in production mode (no dev mode)
- [ ] Rate limiting connected to Redis cluster
- [ ] API keys rotated every 90 days
- [ ] Audit logs sent to SIEM
- [ ] DDoS protection enabled (CloudFlare, AWS Shield)
- [ ] WAF rules configured
- [ ] Security monitoring (alerts on rate limit exceeded, auth failures)
- [ ] Incident response plan documented

---

## Security Monitoring

### Key Metrics to Track

```python
from swarm_it_adk.rate_limiting import get_global_limiter

limiter = get_global_limiter()

# Monitor rate limiting
rate_limit_metrics = {
    "total_requests": ...,
    "rate_limited_requests": ...,
    "rate_limit_ratio": ...,
    "top_blocked_ips": [...]
}

# Alert on suspicious patterns
if rate_limit_ratio > 0.1:  # >10% rate limited
    send_alert("High rate limiting detected")
```

### Audit Log Format

```python
{
    "timestamp": "2026-03-04T20:00:00Z",
    "event": "certification_request",
    "user_id": "user_123",
    "ip_address": "192.168.1.1",
    "endpoint": "/certify",
    "rate_limit_remaining": 95,
    "status": "success",
    "kappa": 0.842,
    "decision": "EXECUTE"
}
```

---

## Common Vulnerabilities and Mitigations

### 1. API Key Leakage

**Risk**: CVSS 8.1 (High)
**Attack**: Environment variable dump, git commit, log exposure

**Mitigation**:
- ✅ Use Vault/AWS Secrets Manager (NOT env vars)
- ✅ Rotate keys every 90 days
- ✅ Scan git history for leaked keys (truffleHog, git-secrets)
- ✅ Never log API keys

### 2. DDoS Attacks

**Risk**: CVSS 7.5 (High)
**Attack**: Flood certification endpoint with requests

**Mitigation**:
- ✅ Rate limiting (100 req/min per IP)
- ✅ Redis-backed distributed limiting
- ✅ Blacklist malicious IPs
- ✅ CDN/WAF protection (CloudFlare, AWS WAF)

### 3. SQL Injection

**Risk**: CVSS 9.8 (Critical)
**Attack**: Malicious input in prompt/parameters

**Mitigation**:
- ✅ Pydantic input validation
- ✅ Parameterized queries (if using SQL)
- ✅ ORM usage (SQLAlchemy)
- ✅ Input sanitization

### 4. Replay Attacks

**Risk**: CVSS 7.5 (High)
**Attack**: Reuse stolen API keys or tokens

**Mitigation**:
- ✅ API key rotation
- ✅ Short-lived JWT tokens
- ✅ Request signatures (HMAC)
- ✅ Nonce/timestamp validation

---

## OWASP Top 10 Compliance

| OWASP Risk | Status | Mitigation |
|------------|--------|------------|
| A01: Broken Access Control | ✅ | Rate limiting, input validation |
| A02: Cryptographic Failures | ✅ | Vault/AWS encryption, HTTPS |
| A03: Injection | ✅ | Pydantic validation, sanitization |
| A04: Insecure Design | ⏳ | Circuit breakers (Week 2-3) |
| A05: Security Misconfiguration | ✅ | Secure defaults, no debug mode |
| A06: Vulnerable Components | ⏳ | Dependency scanning (ongoing) |
| A07: Auth Failures | ⏳ | OAuth 2.0 (Phase 3) |
| A08: Software/Data Integrity | ✅ | Evidence export, audit logging |
| A09: Logging Failures | ⏳ | SIEM integration (Week 3) |
| A10: SSRF | ✅ | Input validation, URL whitelisting |

---

## Questions?

**SecurityAuditor (kappa=0.333)**:
> "Rate limiting and secrets management aren't optional. They're the minimum security requirements for any production deployment."

**AuthArchitect (kappa=0.336)**:
> "A single API key leak can compromise your entire system. Vault/AWS Secrets Manager are production requirements, not nice-to-haves."

**For more security guidance**, see:
- [UNIFIED_API_IMPROVEMENT_ROADMAP.md](../yrsn-experiments/exp/multi_provider_swarms/UNIFIED_API_IMPROVEMENT_ROADMAP.md)
- [AGENT_NEXT_STEPS.md](../yrsn-experiments/exp/multi_provider_swarms/AGENT_NEXT_STEPS.md)

---

**Last Updated**: 2026-03-04
**Security Level**: Week 1 Critical Features Implemented
**Next**: Circuit breakers + audit logging (Week 2-3)
