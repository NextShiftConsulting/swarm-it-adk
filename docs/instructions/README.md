# Swarm-IT Documentation

## Instructions

| Guide | Description |
|-------|-------------|
| [Quick Start](./QUICKSTART.md) | 5-minute setup and basic usage |
| [A2A Guide](./A2A_GUIDE.md) | Complete Agent-to-Agent documentation |

---

## What is Swarm-IT?

Swarm-IT is a **certification layer for LLM interactions** that:

1. **Certifies prompts** before they reach LLMs (prevents attacks)
2. **Monitors multi-agent swarms** via kappa_swarm metric
3. **Integrates with** LangChain, AWS Bedrock, and other frameworks

---

## Key Concepts

### RSN Decomposition

Every prompt/message is decomposed into:
- **R** (Relevance): Task-relevant content
- **S** (Support): Supporting context
- **N** (Noise): Irrelevant/harmful content

`R + S + N = 1.0`

### Kappa (κ) Score

Quality metric: `κ = R / (R + N)`

- κ ≥ 0.7: High quality (EXECUTE)
- κ < 0.7: Allowed but flagged (REPAIR)
- κ < 0.4: Blocked (BLOCK/REJECT)

### A2A (Agent-to-Agent)

For multi-agent systems:
- Each agent-to-agent message is certified
- `kappa_swarm = min(kappa_interface)` across all links
- Weak links are automatically identified

---

## Examples

```bash
# Set up paths
export PYTHONPATH="/path/to/yrsn/src:/path/to/yrsn/keys:."

# Run examples
python examples/quickstart.py       # Basic certification
python examples/demo.py             # Full demo
python examples/a2a_swarm.py        # Multi-agent
python examples/a2a_bedrock.py      # AWS Bedrock
python examples/a2a_rag_swarm.py    # RAG pipeline
python examples/a2a_hierarchical.py # Manager/Workers
python examples/langchain_integration.py # LangChain
```

---

## Architecture

```
User Request
     │
     ▼
┌─────────────────┐
│ Pattern Detect  │ ← Regex-based attack detection
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Semantic Check  │ ← Embedding similarity to attacks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RSN Rotor       │ ← Trained 384→64→RSN pipeline
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Gate Decision   │ ← EXECUTE / REPAIR / BLOCK / REJECT
└────────┬────────┘
         │
         ▼
    LLM (if allowed)
```

---

## Support

- GitHub Issues: [Report bugs](https://github.com/your-org/swarm-it/issues)
- See [PATENT_NOTICE.md](../../PATENT_NOTICE.md) for patent information
