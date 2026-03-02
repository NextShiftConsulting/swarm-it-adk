# Swarm‑It Clients

Clients are **transport + DX only**.

- They **never compute** RSN decomposition, rotor outputs, κ/metrics.
- They only **send/receive certificates** and **submit verification/validation requests**.

If you want RSCT compute, that lives in `yrsn` and is exercised through the **sidecar**.

## Packages

| Language | Folder | Status |
|---|---|---|
| Python (thin) | `clients/python/` | Reference client (vendor/copy) |
| TypeScript | `clients/typescript/` | Package skeleton (`@swarmit/client`) |
| Go | `clients/go/` | Go module reference |
| Rust | `clients/rust/` | Cargo crate reference |

For a batteries‑included Python SDK with integrations (LangChain/FastAPI), see `adk/`.
