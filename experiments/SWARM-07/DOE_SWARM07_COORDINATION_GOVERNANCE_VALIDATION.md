# DOE: SWARM-07 — Coordination-Governance Empirical Validation

**Experiment:** SWARM-07 (V-013 empirical closure)
**Program:** MAS coordination governance (ADR-079 §Rollout)
**Status:** DRAFT — lock before running
**Execution:** LOCAL deterministic, seeded RNG. Drives the LIVE `swarm_it.governance`
module (no external data, no SageMaker).
**Depends on:** V-013 code contract (RESOLVED 2026-07-21). Successor to SWARM-01 H8.

---

## Problem statement

V-013's **code** contract is resolved: the coordination-governance runtime is
implemented and verified in live code (`swarm-it-adk/adk/swarm_it/governance/`:
`HandoffEnvelope`, `ChainKappaTracker`, `validate_on_receive`, `recertify_on_output`,
`topology_policy.accept_*`, `p10.decide`). The **empirical** obligation remains
open (thread `mas-coordination-empirical-gaps`, ADR-079 §Rollout). Today the only
chain-kappa datum is **SWARM-01 H8** — ONE deterministic trace per length
(`total_handoffs=4`), which is an existence demo, not evidence, and must NOT be
cited as "chain kappa preserved."

This series powers that up: it drives the **real governance module** under many
stochastic and adversarial traces to test the guarantees the module is supposed
to provide. It is the prerequisite for retiring the empirical half of V-013.

> **Baseline anomaly to explain (H1):** SWARM-01 H8 shows `kappa_interface_min`
> *rising* 0.608 → 0.665 over chain length 2 → 5. Weakest-link tracking should make
> the running min **non-increasing**. Under the true `ChainKappaTracker`, the min
> must not rise — if it does, H8's rise was a trace-construction artifact. Confirm
> and document either way.

## Hypotheses

### H1 — Weakest-link min-monotonicity holds under stochastic handoffs
Across many seeded stochastic traces, `ChainKappaTracker.chain_kappa_min` is
**monotone non-increasing** along each chain and equals the exact running min of
per-hop derived `kappa_compat`.
- Independent: chain_length ∈ {2,4,8,16} × topology ∈ {pipeline, hub_spoke, mesh}
  × per-hop kappa drawn from a stochastic model × seed (≥200 traces/cell).
- Dependent: `chain_kappa_min` trajectory; monotonicity-violation count (any hop
  where the running min rises); |tracker_min − true_running_min|.
- Success: **0** monotonicity violations across all traces AND tracker_min == running
  min (exact). Directly probes the H8 rise.

### H2 — Receive-boundary fails closed on adversarial handoffs (no inherited trust)
An adversarial predecessor cannot authorize the successor: `validate_on_receive`
re-derives over successor state and **refuses (non-EXECUTE)** regardless of the
predecessor's claimed verdict. False-authorization = 0.
- Independent: adversary ∈ {inflated_kappa, stale_representation, incomparable_chain,
  missing_threshold, incomplete_enforcement_config} × topology.
- Dependent: false-authorization rate (successor EXECUTE while derived verdict
  refuses); typed refusal reason per adversary.
- Success: **false-authorization = 0** across all adversary types AND each yields the
  correct typed fail-closed reason (`CHAIN_KAPPA_INCOMPARABLE`,
  `MISSING_CHAIN_KAPPA_THRESHOLD`, `MISSING_REPRESENTATION`, `INCOMPLETE_ENFORCEMENT_CONFIG`).

### H3 — P10 loops are mutually exclusive and budget-terminating (Claim 9)
`p10.decide` selects **exactly one** of {repair, handoff, refuse} per failure; repair
and handoff are never both taken for the same failure; budgets strictly decrement and
exhaustion terminates with `refuse` (no unbounded loop).
- Independent: scenario ∈ {repairable, non-repairable, budget-exhausted} × budget config.
- Dependent: decision sequence; mutual-exclusivity violations (repair AND handoff for
  one failure); trajectory length (termination within budget).
- Success: **0** mutual-exclusivity violations; every trajectory terminates within
  budget; exhaustion → `refuse`. This is the Claim 9 property never empirically tested.

### H4 — Compounding degradation is refused pre-failure (stretch)
As per-hop kappa drifts down along the chain, `chain_kappa_min` crosses
`min_chain_kappa` and the receive boundary refuses **before** an unsafe hop executes;
the warning (min dipping toward threshold) leads the refusal.
- Independent: per-hop degradation rate.
- Dependent: hop index at threshold-cross vs hop index at first unsafe execution;
  warning lead (in hops).
- Success: refusal fires at/before the first sub-threshold hop (no unsafe hop slips
  through); warning lead ≥ 0.

## Ablations (pre-registered)
1. **min-monotone tracker vs naive per-hop kappa** — naive can rise; reproduces the
   SWARM-01 H8 artifact and shows the tracker fixes it.
2. **receive boundary inert (shape+hash only) vs enforcement (re-derive)** —
   false-authorization should be non-zero inert, **zero** enforcement.
3. **P10 with budget vs unbounded** — budget is what guarantees termination.

## Primary metrics
- `monotonicity_violation_rate` (H1) — target 0
- `false_authorization_rate` (H2) — target 0
- `mutual_exclusivity_violations` + `nontermination_count` (H3) — target 0
- `warning_lead_hops` (H4)

## Test bed — stochastic + adversarial handoff-chain generator
A seeded generator produces per-hop derived certificates (kappa_compat draws) and
adversarial handoffs. **Ground truth (genuine-vs-adversarial, the degradation
schedule) comes from the generator, never from a governance statistic.** The harness
feeds these through the LIVE module: `HandoffEnvelope` → `validate_on_receive`
(enforcement mode, real `cert_resolver`/`certifier`) → `ChainKappaTracker.observe` →
`recertify_on_output`; P10 scenarios through `p10.decide`.

## DO NOT
- Do **not** reimplement governance logic in the experiment — **import and drive**
  `swarm_it.governance`. The experiment is a harness, not a reimplementation.
- Do **not** derive any correctness label from a governance statistic (SWARM-01 A1
  discipline) — genuine/adversarial and the degradation ground-truth come from the
  seeded generator.
- Do **not** cite results until powered (≥200 traces/cell; all seeds logged).
- Do **not** modify the governance module to make a test pass — that games the gate.
  Fix the harness, or file a finding (and open a variance) against the module.

## Success criteria
| H | Criterion | Status |
|---|-----------|--------|
| H1 | 0 monotonicity violations; tracker_min == running min (exact) | PENDING |
| H2 | false-authorization = 0; correct typed reason per adversary | PENDING |
| H3 | 0 mutual-exclusivity violations; all trajectories terminate; exhaustion→refuse | PENDING |
| H4 | refusal at/before first sub-threshold hop; warning lead ≥ 0 | PENDING |

## Baseline
SWARM-01 H8 (`experiments/SWARM-01/evidence/h8_multiagent_handoff.json`): single
deterministic trace/length, `kappa_interface_min` 0.608→0.665 — the underpowered
datum this series replaces.

## Change control
DRAFT. Fill the stochastic model + adversary set + power (traces/cell) + seed list,
then set Status: LOCKED. Changes after lock require a DOE_AMENDMENT.
Closes the empirical half of V-013 (register) + open thread
`mas-coordination-empirical-gaps` on passing H1–H3 with artifacts.
