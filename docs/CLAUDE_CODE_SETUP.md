# Swarm-It + Claude Code Integration

Run RSCT certification directly in Claude Code via MCP.

## Setup

### 1. Add to Claude Code settings

Edit `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "swarm-it": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/Users/rudy/GitHub/swarm-it/sidecar",
      "env": {
        "PYTHONPATH": "/Users/rudy/GitHub/yrsn/src"
      }
    }
  }
}
```

### 2. Restart Claude Code

```bash
# Exit and restart Claude Code
claude
```

### 3. Verify tools available

In Claude Code, type:
```
/mcp
```

You should see `swarm-it` with 4 tools:
- `rsct_certify`
- `rsct_validate`
- `rsct_audit`
- `rsct_health`

---

## Example: Certified Code Generation

### Workflow

```
User Request
    │
    ▼
┌─────────────────┐
│  rsct_certify   │  ← Pre-check prompt quality
│  R=0.7, S=0.2   │
│  decision=EXEC  │
└────────┬────────┘
         │ allowed=true
         ▼
┌─────────────────┐
│  Generate Code  │  ← Claude generates code
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  rsct_validate  │  ← Post-check: was output good?
│  TYPE_I, 0.95   │
└─────────────────┘
```

### Example Session

**User:** Write a Python function to calculate fibonacci numbers

**Claude (with swarm-it):**

1. First, certify the request:
```
Tool: rsct_certify
Input: {"prompt": "Write a Python function to calculate fibonacci numbers"}
Result: {
  "certificate_id": "abc123",
  "R": 0.72,
  "S": 0.18,
  "N": 0.10,
  "kappa": 0.88,
  "decision": "EXECUTE",
  "allowed": true
}
```

2. Generate the code (kappa > 0.7, proceed):
```python
def fibonacci(n: int) -> int:
    """Calculate nth Fibonacci number."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
```

3. Validate the output:
```
Tool: rsct_validate
Input: {
  "certificate_id": "abc123",
  "validation_type": "TYPE_I",
  "score": 0.95,
  "failed": false
}
Result: {"recorded": true}
```

---

## Multi-Agent Swarm Example

### Scenario: Code Review Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Architect  │───▶│  Developer  │───▶│  Reviewer   │
│  κ ≥ 0.8    │    │  κ ≥ 0.7    │    │  κ ≥ 0.85   │
└─────────────┘    └─────────────┘    └─────────────┘
```

Each agent certifies before acting:

```python
# Pseudo-code for swarm orchestration
async def code_review_swarm(task: str):
    # Stage 1: Architect plans
    arch_cert = await rsct_certify(f"Plan implementation for: {task}")
    if arch_cert.kappa < 0.8:
        return "Architect blocked - unclear requirements"

    plan = await architect_agent(task)

    # Stage 2: Developer implements
    dev_cert = await rsct_certify(f"Implement: {plan}")
    if dev_cert.kappa < 0.7:
        return "Developer blocked - plan too vague"

    code = await developer_agent(plan)

    # Stage 3: Reviewer checks
    rev_cert = await rsct_certify(f"Review code quality: {code[:500]}")
    if rev_cert.kappa < 0.85:
        return "Reviewer blocked - code unclear"

    review = await reviewer_agent(code)

    # Validate entire pipeline
    await rsct_validate(arch_cert.id, "TYPE_V", 0.9)  # Reasoning
    await rsct_validate(dev_cert.id, "TYPE_I", 0.85)  # Groundedness
    await rsct_validate(rev_cert.id, "TYPE_VI", 0.9)  # Domain

    return {"plan": plan, "code": code, "review": review}
```

---

## Validation Types

| Type | Name | Use Case |
|------|------|----------|
| TYPE_I | Groundedness | Was output factually correct? |
| TYPE_II | Contradiction | Any internal inconsistencies? |
| TYPE_III | Inversion | Did meaning get reversed? |
| TYPE_IV | Drift | Did it stay on topic? |
| TYPE_V | Reasoning | Was logic sound? |
| TYPE_VI | Domain | Appropriate for domain? |

---

## Audit Trail

Export certificates for compliance:

```
Tool: rsct_audit
Input: {"limit": 10, "format": "SR11-7"}
Result: {
  "certificate_count": 10,
  "format": "SR11-7",
  "records": [...]
}
```

SR 11-7 format includes:
- Quantitative metrics (R, S, N, kappa)
- Gate outcomes
- Risk indicators
- Pattern flags
