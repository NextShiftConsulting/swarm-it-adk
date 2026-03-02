# Repo boundaries (monorepo layout)

This repository is a **monorepo**. The goal is to keep compute, serving, and developer experience clearly separated.

## Components

### 1) Compute (Generation)
- **Owner:** `yrsn` (external dependency)
- **Owns:** RSN decomposition, rotor, κ/metrics, certificate construction and canonical schema rules
- **Does not own:** HTTP, auth, retries, SDK ergonomics

### 2) Serving (Transmission / Network boundary)
- **Owner:** `sidecar/`
- **Owns:** HTTP surface area, auth hooks, storage adapters, audit export, operational telemetry
- **Does not own:** RSN/rotor/κ computation (delegated to `yrsn`)

### 3) Developer experience (Distribution)
- **Owners:** `clients/` and `adk/`
- **Owns:** client libraries, typed models, retries/backoff, examples, mocks, integrations
- **Does not own:** RSN/rotor/κ computation

## Rule of thumb

If a change alters "what a certificate *means*", it belongs in **`yrsn`**.
If a change alters "how certificates are served or stored", it belongs in **`sidecar/`**.
If a change alters "how developers call the system", it belongs in **`clients/`** or **`adk/`**.
