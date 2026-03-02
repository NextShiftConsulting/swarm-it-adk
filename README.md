# Swarm‑It Monorepo

**RSCT certification (via `yrsn`) delivered as a sidecar runtime + multi‑language clients.**

This repository is intentionally a **monorepo**. It contains:

| Component | Folder | What it is | Owns | Does *not* own |
|---|---|---|---|---|
| Sidecar Runtime | `sidecar/` | Deployable HTTP service | Network boundary, auth hooks, storage adapters, audit export | RSN/rotor math implementation (delegated to `yrsn`) |
| Reference Clients | `clients/` | Thin clients (Python/TS/Go/Rust) | Transport, retries, typed models, DX | RSN/rotor/κ computation |
| Python SDK (batteries‑included) | `adk/` | Higher‑level Python SDK + integrations | DX helpers, middleware/integrations, testing utilities | Re‑implementing `yrsn` core |
| Examples | `examples/` | End‑to‑end demos | “Hello cert” + integrations | Canonical API/spec |
| Docs | `docs/` | Architecture + ops notes | Specs, deployment notes | Runtime code |

## Boundary: where RSCT math lives

**All certificate computation is owned by `yrsn`** (rotor, RSN decomposition, κ/metrics).  
This repo **wraps** that compute behind a **sidecar service** and ships **clients** to call it.

If you ever feel tempted to add RSN/rotor/κ math into a client package, treat that as a bug.

## Quick start

### 1) Run the sidecar

```bash
cd sidecar
docker-compose up -d

curl http://localhost:8080/health
```

More: see **`sidecar/README.md`**.

### 2) Call it from a client

**Python (batteries‑included SDK)**

```bash
pip install swarm-it
```

```python
from swarm_it import SwarmIt

swarm = SwarmIt(base_url="http://localhost:8080")

cert = swarm.certify("What is 2+2?")
if cert.allowed:
    print("execute")
else:
    print("blocked:", cert.reason)
```

**Other languages / thin clients:** see `clients/`.

## Where to go next

- Sidecar runtime: **`sidecar/README.md`**
- Client SDKs: **`clients/README.md`**
- Docs: `docs/sidecar_analysis/` and `docs/architecture/`

## License

Licensed under the **Apache License 2.0**. See `LICENSE`.

- Patent status / disclosures: `PATENT_NOTICE.md` (informational)
- Trademarks: `TRADEMARK_NOTICE.md`

© 2026 Next Shift Consulting LLC
