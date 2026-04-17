# Architecture Decision Record: Controlplane Sole Gate Authority

**Date**: 2026-04-17
**Status**: ACCEPTED
**Decision**: All enforcement gate outcomes must be computed by yrsn-controlplane's SequentialGatekeeper

---

## Context

Prior to this decision, gate logic existed in three repositories with drifting semantics:

1. **yrsn** — authoritative 5-gate SequentialGatekeeper (FIG. 24), Landauer buffer, sigma-adaptive kappa_req
2. **rsct** (now yrsn-orchestration) — simplified 4-gate `evaluate_gates()` with generic GateConfig
3. **swarm-it-adk** — hardcoded reimplementations in 13+ code paths: `if N > 0.5: REJECT` scattered across client.py, byok_engine.py, local/engine.py, topology/certifier.py, mcp_tools.py

The ADK contained at least three critical gate bypasses:
- `client.py._local_certify()` — inline `if N > threshold` with hardcoded values
- `mcp_tools.py.QualityGateTool.execute()` — full 5-gate reimplementation with wrong kappa semantics (`kappa = min(R, S)`)
- `topology/certifier.py._generate_agent_certificates()` — `GateDecision.EXECUTE if kappa >= 0.4 else GateDecision.BLOCK`

Each bypass was a policy fork: different thresholds, different gate counts, different kappa formulas. Any change to gate policy required updating all paths — and in practice, only the yrsn path was updated.

---

## Decision

**No production gate outcome may be computed outside yrsn-controlplane except in explicitly marked test fixtures.**

Specifically:

1. **SequentialGatekeeper** is the sole authority for enforcement decisions (EXECUTE, REJECT, BLOCK, RE_ENCODE, REPAIR, WARN, FALLBACK).
2. All consumers — yrsn, yrsn-orchestration, swarm-it-adk, swarm-it-api — delegate to `SequentialGatekeeper.evaluate()`.
3. Gate policy is configured via `GatekeeperConfig` and named presets (`universal`, `strict`, `permissive`, `research`, `multimodal`), not inline threshold comparisons.
4. The bridge layer (`_compat.py`, `_config_bridge.py`) handles type mapping between ADK's extended `GateDecision` enum and controlplane's `EnforcementDecision`.

### What counts as a gate outcome

Any code that determines whether execution should proceed, be blocked, or require remediation based on certificate metrics (R, S, N, kappa, sigma, alpha). This includes:

- `if N > threshold: REJECT`
- `if kappa < threshold: BLOCK`
- Any conditional branching on certificate values that produces an enforcement decision

### What does NOT count

- **Audit risk classification** (LOW/MEDIUM/HIGH/CRITICAL) — reporting concern, not enforcement
- **Certificate construction** — building RSCTCertificate or CertificateEstimate objects
- **Metric computation** — computing R, S, N, kappa, sigma from embeddings
- **Routing logic** — choosing downstream handler based on an already-computed decision

---

## Consequences

### Positive

- **Policy drift eliminated**: One place to update gate thresholds, formulas, and gate structure
- **Correct semantics guaranteed**: Wrong kappa formulas (`min(R, S)`) cannot recur in side paths
- **Future specialization safe**: New profiles (regulated, quantum, hardware) are preset configs, not code forks
- **Testable in isolation**: Gate logic is tested once in yrsn-controlplane with 100% coverage requirement

### Negative

- **Import dependency**: All consumers depend on yrsn-controlplane (zero-dep, but still a dependency)
- **Bridge complexity**: ADK's extended enum (HALT, TIMEOUT, ESCALATE) requires a shim layer
- **Migration cost**: Existing inline gate logic had to be identified and replaced across 13+ files

### Risks

- **Import isolation**: If `from yrsn_controlplane import ...` accidentally triggers heavy imports from yrsn proper, the zero-dep promise breaks. Mitigated by: controlplane is a separate package with its own pyproject.toml.
- **Enum divergence**: If controlplane adds new EnforcementDecision values, ADK's GateDecision must be updated. Mitigated by: bridge tests parametrize over all EnforcementDecision values.

---

## Enforcement

1. **Code review**: Any PR introducing `if N >`, `if kappa <`, or similar certificate-metric conditionals outside yrsn-controlplane must be flagged.
2. **CI check** (recommended): `grep -rn 'if.*\b[NR]\b.*>' --include='*.py' | grep -v controlplane | grep -v test` as a lint step.
3. **Bridge test coverage**: `test_compat_bridge.py` parametrizes over all `EnforcementDecision` values — new values cause test failure until the bridge is updated.

---

## References

- Patent FIG. 24: Sequential gate architecture
- Patent section B.3: Two-contract architecture (G_R, G_S measurement ports)
- `yrsn-controlplane/src/yrsn_controlplane/gatekeeper.py`: Canonical SequentialGatekeeper
- `swarm-it-adk/adk/swarm_it/_compat.py`: ADK bridge layer
- `swarm-it-adk/adk/swarm_it/_config_bridge.py`: Config adapter
- `swarm-it-api/engine/_controlplane_compat.py`: API compat bridge

---

## Change Control

| Date | Change | Author |
|------|--------|--------|
| 2026-04-17 | Initial decision | — |
| 2026-04-17 | Add swarm-it-api as delegating consumer | — |
