# SWARM-07 Pre-Flight Checklist

## Before LOCK (design closure)
- [ ] Per-hop `kappa_compat` stochastic model + degradation schedule pinned (`configs/`)
- [ ] Adversary set chosen from DOE candidates + pinned
- [ ] Power pinned: traces/cell (>=200) + explicit seed list
- [ ] DOE status DRAFT -> LOCKED

## Before run (V0)
- [ ] `git status` clean; commit + push (git hash traces the code that ran)
- [ ] Harness imports `swarm_it.governance` (no reimplementation) — grep confirms
- [ ] Seeded RNG only (deterministic, reproducible); seeds logged per trace
- [ ] Ground-truth labels come from the generator, not any governance statistic

## Execution (local-deterministic; NO SageMaker)
- [ ] Run per-hypothesis harness; write `evidence/hN_*.json`
- [ ] Log (chain_length, topology, adversary, seed) per record

## Post-run (V1-V4)
- [ ] H1: 0 monotonicity violations AND tracker_min == running min (exact)
- [ ] H2: false-authorization == 0 AND correct typed reason per adversary
- [ ] H3: 0 mutual-exclusivity violations; all trajectories terminate; exhaustion->refuse
- [ ] Domain invariant: derived certs re-derived over successor state (not inherited)
- [ ] `HYPOTHESIS_VERDICTS.md` written (CONFIRMED/REJECTED per H)
- [ ] >=1 practitioner tip extracted (swarm-experiment-tips)
- [ ] On H1-H3 pass with artifacts: close empirical half of V-013 (register) +
      resolve open thread `mas-coordination-empirical-gaps`

## Execution record
| Run | Phase | Seeds | Traces | Date | Commit | Result |
|-----|-------|-------|--------|------|--------|--------|
|     |       |       |        |      |        |        |
