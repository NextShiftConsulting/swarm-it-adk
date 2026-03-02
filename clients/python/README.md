# Python Thin Client

This is a **thin** `httpx` client for the Swarm‑It sidecar.

## Use

```python
from swarm_it.client import SwarmIt

swarm = SwarmIt(url="http://localhost:8080")
cert = swarm.certify("Summarize this document")

if cert.allowed:
    # call your LLM
    pass
```

## Notes

- This folder is currently a **reference client** (not a published PyPI package).
- If you want the published Python SDK (`pip install swarm-it`) and integrations, use `adk/`.
