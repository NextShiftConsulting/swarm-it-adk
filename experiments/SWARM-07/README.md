# SWARM-07 — Coordination-Governance Empirical Validation

**Status:** DRAFT (scoped 2026-07-21). Locks the empirical closure of **V-013**.

## What this is
V-013's *code* contract (the MAS coordination-governance runtime in
`swarm-it-adk/adk/swarm_it/governance/`) is RESOLVED. This series supplies the
missing *empirical* half: it drives the **live governance module** under many
seeded stochastic and adversarial traces to test the guarantees the module claims.

Until this passes, **"chain kappa is preserved" is not citable** — the only prior
datum (SWARM-01 H8) is one deterministic trace per length.

## Hypotheses (see DOE for full design)
- **H1** — weakest-link `chain_kappa_min` is monotone non-increasing == exact running
  min (probes the SWARM-01 H8 rise-anomaly).
- **H2** — receive boundary fails closed on adversarial handoffs; false-authorization = 0.
- **H3** — P10 loops mutually exclusive + budget-terminating (Claim 9, never empirically tested).
- **H4** (stretch) — compounding degradation refused pre-failure; warning lead ≥ 0.

## Module under test (import, do not reimplement)
```
swarm_it.governance:
  HandoffEnvelope, ChainKappaTracker, validate_on_receive,
  recertify_on_output, topology_policy.accept_{pipeline,hub_spoke,mesh}, p10.decide
```

## Layout
```
DOE_SWARM07_COORDINATION_GOVERNANCE_VALIDATION.md   # design (DRAFT)
EXPERIMENT_STATUS.yaml                              # phases + open-before-lock
CHECKLIST.md                                        # pre-run gate
configs/                                            # stochastic model + adversary + seeds (fill before LOCK)
scripts/                                            # harness (build after LOCK)
evidence/                                           # per-hypothesis JSON
results/                                            # analysis, figures, HYPOTHESIS_VERDICTS.md
```

## Before LOCK (inventor/design decisions — do NOT invent)
1. Per-hop `kappa_compat` stochastic model + degradation schedule.
2. Adversary set (5 candidates in the DOE) + which to include.
3. Power: traces/cell (≥200) + seed list.

## Discipline
- Drive the live module; the harness never reimplements governance logic.
- Ground truth (genuine/adversarial, degradation) comes from the seeded generator,
  never from a governance statistic.
- Never modify the governance module to pass a test — fix the harness or file a finding.
