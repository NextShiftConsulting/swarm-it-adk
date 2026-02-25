# Clean Architecture: Tendermint-Inspired Separation

## First Principles

The swarm-it sidecar follows the Tendermint ABCI model:

| Component | Role | Knows Domain? |
|-----------|------|---------------|
| **Sidecar** | Infrastructure (API, pre-screening, metrics) | No |
| **yrsn core** | Domain logic (RSN, gates, certificates) | Yes |

**Key insight**: The sidecar is domain-agnostic. It doesn't know what R, S, N mean. It just:
1. Pre-screens for obvious attacks (like Tendermint's CheckTx)
2. Delegates to yrsn for actual computation
3. Provides observability

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   swarm-it sidecar                          │
│                                                             │
│  ┌───────────┐   ┌─────────────┐   ┌──────────────────┐   │
│  │ REST/gRPC │──▶│ Pre-screen  │──▶│ YRSNAdapter      │   │
│  │ API       │   │ (patterns)  │   │ (Local or Mock)  │   │
│  └───────────┘   └──────┬──────┘   └────────┬─────────┘   │
│                         │                    │             │
│                  gate=0 │             pass   │             │
│                  REJECT ▼             ───────┼─────────────┼──
└─────────────────────────────────────────────┼─────────────┘
                                               │
                                               ▼
                          ┌──────────────────────────────────┐
                          │           yrsn core               │
                          │                                   │
                          │  • HybridSimplexRotor            │
                          │  • RSN computation               │
                          │  • 5-gate logic                  │
                          │  • Certificate generation        │
                          └──────────────────────────────────┘
```

## Flow

1. **Request arrives** at sidecar (REST or gRPC)
2. **Pre-screen** checks for severe patterns (XSS, jailbreak, injection)
   - If severe (score ≥ 0.9): **REJECT at gate=0** (don't call yrsn)
   - If moderate: flag and pass to yrsn
   - If clean: pass to yrsn
3. **yrsn adapter** receives request with:
   - Prompt
   - Embeddings (user-provided OR adapter calls OpenAI)
   - Pre-screen metadata
4. **yrsn computes** RSN using HybridSimplexRotor
5. **yrsn applies** 5-gate logic → decision
6. **Certificate returned** through sidecar to client

## Key Files

| File | Purpose |
|------|---------|
| `engine/interface.py` | Clean SGCI boundary (CertifyRequest/Response) |
| `engine/yrsn_adapter.py` | Adapters: LocalYRSNAdapter, MockYRSNAdapter |
| `engine/rsct.py` | Thin pre-screen layer (NO domain logic) |
| `engine/patterns.py` | Pattern detection (injection, spam, XSS) |

## Embeddings

Three options for providing embeddings:

### Option 1: User provides (recommended for production)
```python
embeddings = openai_client.embeddings.create(model="text-embedding-3-small", input=prompt)
cert = engine.certify(prompt, embeddings=embeddings.data[0].embedding)
```

### Option 2: Sidecar convenience wrapper
```bash
OPENAI_API_KEY=sk-... USE_YRSN=1 python app.py
```
Sidecar calls OpenAI automatically.

### Option 3: Mock (development/testing)
```python
engine = RSCTEngine(use_mock=True)  # No embeddings needed
```

## Requirements

- **Sidecar**: Python 3.7+ (pattern detection, API)
- **yrsn integration**: Python 3.8+ (typing.Protocol, torch)
- **Real RSN**: OpenAI API key OR pre-computed embeddings

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `USE_YRSN` | Enable real yrsn (set to "1") | "0" (mock) |
| `OPENAI_API_KEY` | For embedding convenience | None |
| `EMBED_MODEL` | OpenAI model | text-embedding-3-small |
| `ROTOR_CHECKPOINT` | Trained rotor weights | None (untrained) |

## Why This Architecture?

1. **Separation of concerns**: Sidecar doesn't need to understand RSN math
2. **Testability**: Mock adapter for sidecar tests, real yrsn for integration
3. **Flexibility**: Swap adapters (local, remote, mock) without changing sidecar
4. **Security**: Pre-screen catches attacks before they reach yrsn
5. **Observability**: Sidecar adds metrics without touching domain logic
