# V-013 Task 6 — Per-topology acceptance policy (PIPELINE / HUB_SPOKE / MESH)

## Summary

Added `adk/swarm_it/governance/topology_policy.py`: independent acceptance
functions for the three in-scope `SwarmPattern` topologies, each with its
own executable acceptance test file proving support is not inherited from
a shared interface alone.

## Interfaces implemented

- `TopologyDecision` — frozen dataclass: `verdict`, `reason`, `gating_hop`,
  `detail`.
- `HopInput` — frozen dataclass carrying `envelope`, `produced_payload`,
  `successor_representation_id`, `successor_state`, `hop_kappa`.
- `UnsupportedTopologyError` — defined per spec; `accept()` does not raise
  it (fails closed with a REFUSE `TopologyDecision` instead, for
  consistency with every other fail-closed verdict style in this
  codebase's governance layer).
- `accept(pattern, hops, *, certifier, min_chain_kappa, threshold=None)` —
  dispatches to the per-topology function; RING/HIERARCHICAL (and any
  other non-PIPELINE/HUB_SPOKE/MESH value) REFUSE with
  `reason="UNSUPPORTED_TOPOLOGY"`.
- `accept_pipeline` — single `ChainKappaTracker` threaded across all hops
  in order; stops and REFUSEs at the first hop whose observation drives
  the running chain-kappa min below `min_chain_kappa` (`gating_hop` = that
  hop's index).
- `accept_hub_spoke` — each spoke gets its OWN fresh `ChainKappaTracker`
  (independent evaluation); any single failing spoke (below threshold,
  incomparable, or certifier refusal) REFUSEs the whole hub result, with
  `gating_hop` = the failing spoke's index. A weak spoke never drags down
  or is masked by another spoke (`test_hub_spoke_each_evaluated_independently`).
- `accept_mesh` — every edge tracked by `handoff_id` in a `traversed`
  set; an edge whose `envelope.trace_parent` is non-`None` and not yet in
  `traversed` REFUSEs with `reason="UNTRAVERSED_PARENT"` before any
  certifier/chain-kappa work runs (no path inherits authorization from an
  untraversed edge). Edges are also threaded through one
  `ChainKappaTracker` for aggregate chain-kappa health.
- Each per-topology decision (including the unsupported-pattern REFUSE)
  emits one `TraceRecord(event="topology_decision", ...)`.

## Constraints honored

- No gate/kappa math beyond reading `ChainKappaTracker` state and the
  injected `certifier`'s duck-typed verdict (`.allowed` / `.verdict ==
  "EXECUTE"`), matching the existing pattern in `receive_boundary.py` /
  `output_boundary.py`.
- No `sigma`/`sigma_*`, no `kappa_gate`, no `time.time(`/`datetime.now(`
  anywhere in `topology_policy.py` (verified by grep; the docstring was
  reworded after an initial pass literally contained the word "sigma" in
  prose, which would have tripped the repo's `"sigma" not in
  source.lower()` convention).
- No AI attribution.
- Fail-closed throughout: unsupported pattern, certifier error, certifier
  refusal, incomparable chain-kappa, and below-threshold chain-kappa all
  REFUSE; nothing has a default-permissive path.

## TDD evidence

Three new test files, written first and confirmed to fail
(`ModuleNotFoundError: No module named 'swarm_it.governance.topology_policy'`)
before implementation:

- `adk/tests/governance/test_topology_pipeline.py` — 3 tests (weakest-hop
  gates chain, all-healthy executes, trace emission).
- `adk/tests/governance/test_topology_hub_spoke.py` — 4 tests (one failing
  spoke refuses, all-healthy executes, independent-evaluation ordering
  check, trace emission).
- `adk/tests/governance/test_topology_mesh.py` — 3 tests (untraversed
  parent refuses, properly-parented chain executes, trace emission).

## Verification

```
cd adk && python -m pytest tests/governance -v
```

Result: **60 passed** (48 pre-existing + 12 new topology tests across the
3 new files), 0 failed, 0 skipped.

## Files changed

- `adk/swarm_it/governance/topology_policy.py` (new)
- `adk/swarm_it/governance/__init__.py` (export new symbols)
- `adk/tests/governance/test_topology_pipeline.py` (new)
- `adk/tests/governance/test_topology_hub_spoke.py` (new)
- `adk/tests/governance/test_topology_mesh.py` (new)

## Concerns / open items

- `accept()`'s `threshold` parameter is accepted per the spec'd signature
  but is not itself gate math in this task — chain-kappa gating uses
  `min_chain_kappa`; documented in the function docstring rather than
  silently ignored.
- MESH's chain-kappa aggregation reuses one shared `ChainKappaTracker`
  across all edges in evaluation order (same weakest-link pattern as
  pipeline) since the task spec did not prescribe per-edge trackers for
  mesh the way it explicitly did for hub-spoke; flagging in case a future
  task wants per-edge-pair isolation instead.
- `accept_hub_spoke`/`accept_pipeline`/`accept_mesh` call the certifier
  once per hop even though the task's own test guidance says a fake
  always-EXECUTE certifier is sufficient for these tests — kept the call
  (rather than dropping it) because `certifier` is a required, documented
  parameter of every per-topology function signature and skipping it
  would leave it unused/misleading.

---

# V-013 Task 6 -- Review Fix Pass (Spec REJECTED remediation)

Fixes the "topology adapters do NOT route hops through the real
receive/output boundaries" Spec-failing finding from the Task 6 code
review. All items below were TDD'd against `adk/tests/governance` and
verified against the full `adk` suite.

## Fix 1 (PRIMARY) -- route each hop through the real boundaries

`_certify_hop` (a bare `certifier(hop.successor_state)` call) is gone.
Replaced with `_cross_hop_boundaries()`, called once per hop from all
three `accept_*` functions:

1. `validate_on_receive(hop.envelope, hop.produced_payload,
   successor_representation_id=hop.successor_representation_id,
   cert_resolver=cert_resolver, certifier=certifier,
   successor_state=hop.successor_state, min_chain_kappa=min_chain_kappa,
   now_epoch=now_epoch)` -- `ok=False` REFUSEs at that hop, propagating
   the boundary's own `reason` (e.g. PAYLOAD_HASH_MISMATCH,
   INCOMPATIBLE_REPRESENTATION, UNRESOLVED_CERT, STALE_CERT,
   RECERT_REFUSED, CHAIN_KAPPA_BELOW_THRESHOLD, CHAIN_KAPPA_INCOMPARABLE)
   and setting `gating_hop=index`.
2. `recertify_on_output(hop.successor_state, certifier=certifier,
   handoff_id=hop.envelope.handoff_id)` -- `released=False` REFUSEs the
   same way, propagating OUTPUT_RECERT_REFUSED / OUTPUT_CERTIFIER_ERROR /
   MISSING_CERTIFIER.

Only once both boundaries clear does a hop reach the topology's own
weakest-link `ChainKappaTracker.observe(hop.envelope, hop.hop_kappa)` --
kept as a second, topology-level aggregate on top of the boundary's own
(single-hop, envelope-seeded) chain-kappa read, preserving the original
cross-hop "weakest hop gates the whole chain" semantics and the
[0.8, 0.4, 0.9] -> gating_hop=1 pipeline test (still passes, now via
`accept_pipeline(hops, certifier=..., cert_resolver=..., min_chain_kappa=0.5)`).

`accept_pipeline` / `accept_hub_spoke` / `accept_mesh` / `accept` all
gained a required `cert_resolver` kwarg and an optional `now_epoch=None`
kwarg (injected, never read from the wall clock). `__init__.py` exports
were checked -- no name changes were needed (HopInput, TopologyDecision,
accept* all keep their names, only their keyword-arg signatures grew).

Adversarial proof (Fix 6, same commit): `test_pipeline_tampered_payload_refuses`
(a hop's produced_payload doesn't match envelope.payload_hash -> REFUSE
PAYLOAD_HASH_MISMATCH, gating_hop=1) and
`test_pipeline_wrong_representation_refuses` (successor_representation_id
!= envelope.representation_id -> REFUSE INCOMPATIBLE_REPRESENTATION,
gating_hop=1), both in test_topology_pipeline.py.

## Fix 2 -- MESH: CycleGuard + per-lineage trackers

`accept_mesh` now wraps its whole traversal in
`with CycleGuard.enter("handoff"):` (Claim 9 repair/handoff mutual
exclusion -- a mesh acceptance evaluation IS a handoff-mode traversal).

Replaced the single shared ChainKappaTracker with one tracker per
connected lineage: `lineage_root_of` (handoff_id -> lineage root) and
`lineage_trackers` (lineage root -> ChainKappaTracker). An edge with
trace_parent=None starts a new lineage (its own handoff_id is the root);
an edge with a traversed trace_parent inherits that parent's lineage.
Added `test_mesh_unrelated_lineages_isolated`: a healthy root (rep-good)
followed by an unrelated bad root (rep-bad, itself healthy) followed by
a bad-lineage CHILD with a third, incompatible representation
(rep-other). Asserts the overall decision REFUSEs with
CHAIN_KAPPA_INCOMPARABLE at gating_hop=2 (the bad lineage's OWN internal
weakness), not at gating_hop=1 (what a shared-tracker bug would
produce, since bad-root's differing representation would falsely clash
against good-root's baseline) -- this discriminates the fix from the
pre-fix shared-tracker behavior. A second assertion re-evaluates just
the good lineage's hop on its own and confirms EXECUTE, proving
isolation.

## Fix 3 -- removed dead threshold kwarg

`accept()`'s unused `threshold: Optional[float] = None` parameter is
gone; grepping topology_policy.py for "threshold" now only matches
docstring prose, no parameter.

## Fix 4 -- accept() dispatcher + UNSUPPORTED_TOPOLOGY coverage

New `adk/tests/governance/test_topology_dispatch.py`:
- `test_accept_dispatches_to_each_topology` (parametrized over
  PIPELINE/HUB_SPOKE/MESH): asserts accept() reaches the correct handler
  via each pattern's distinguishing EXECUTE reason (CHAIN_HEALTHY /
  ALL_SPOKES_HEALTHY / MESH_HEALTHY).
- `test_accept_ring_refuses_unsupported` / `test_accept_hierarchical_refuses_unsupported`:
  verdict=="REFUSE", reason=="UNSUPPORTED_TOPOLOGY".

## Fix 5 -- hub-spoke independence test rewritten to discriminate

Old `test_hub_spoke_each_evaluated_independently` short-circuited on the
first failing spoke (index 0) and would have passed even with one
shared tracker across spokes. Rewritten: two spokes on DIFFERENT
representation_ids (rep-A, rep-B), each independently healthy on its
own kappa. Asserts verdict == EXECUTE. Verified this actually
discriminates: temporarily patched accept_hub_spoke to use one
ChainKappaTracker shared across the loop (simulating the pre-fix bug)
and re-ran just this test -- it FAILED (REFUSE instead of EXECUTE,
because spoke 1's differing representation clashed against spoke 0's
tracker baseline), confirming the rewritten test is a genuine
discriminator. The patch was then reverted (via git checkout, which
required rewriting topology_policy.py from the Fix 1/2/3/7 state -- see
below) before re-verifying the real, fixed implementation.

## Fix 6 -- adversarial pipeline tests

Covered under Fix 1 above (test_pipeline_tampered_payload_refuses,
test_pipeline_wrong_representation_refuses).

## Fix 7 -- dedup _derived_verdict_ok + trace lineage

Extracted the three copy-pasted `_derived_verdict_ok` functions into
`adk/swarm_it/governance/_certifier_shims.py` (`derived_verdict_ok`),
imported (not copied) by receive_boundary.py and output_boundary.py.
topology_policy.py no longer needs its own copy since it never calls the
certifier directly anymore -- it goes through the boundaries, which
already duck-type the verdict. Behavior verified identical via the
existing test_receive_enforcement.py / test_output_enforcement.py
suites (still 100% passing).

`_emit_decision` (topology_policy.py) now threads a `trace_parent`
through to the topology_decision TraceRecord -- set to the relevant
hop's envelope.trace_parent for every per-hop REFUSE/EXECUTE, and to
None only for the pattern-level UNSUPPORTED_TOPOLOGY REFUSE (no hop
exists at that point to derive a parent from). Verified with a one-off
script: a topology_decision record's trace_parent matched the
originating envelope's trace_parent.

## Constraints re-verified

- Checked for "sigma", "kappa_gate", "time.time(", "datetime.now(" --
  all clean across topology_policy.py, receive_boundary.py,
  output_boundary.py, _certifier_shims.py.
- Fail-closed preserved throughout: every new/changed branch REFUSEs on
  ambiguity, never defaults to EXECUTE.
- No AI attribution.

## Verification

    cd adk && python -m pytest tests/governance -v

Result: 68 passed (60 pre-existing/updated + 8 net new across the
governance suite: 5 in test_topology_dispatch.py, 2 adversarial in
test_topology_pipeline.py, 1 lineage-isolation in test_topology_mesh.py;
the hub-spoke independence test was rewritten in place, not added). 0
failed, 0 skipped.

    cd adk && python -m pytest -q

Result: 220 passed (full adk suite; 212 pre-existing + 8 new governance
tests), confirming the _certifier_shims extraction and boundary-wiring
changes caused no regressions elsewhere in the repo.

## Files changed

- adk/swarm_it/governance/topology_policy.py (rewritten: boundary
  wiring, per-lineage mesh trackers, CycleGuard, dead threshold removed,
  trace_parent propagation)
- adk/swarm_it/governance/receive_boundary.py (dedup: imports
  derived_verdict_ok from _certifier_shims)
- adk/swarm_it/governance/output_boundary.py (dedup: same)
- adk/swarm_it/governance/_certifier_shims.py (new)
- adk/tests/governance/test_topology_pipeline.py (rewritten: FakeCert +
  cert_resolver fixtures, 2 new adversarial tests)
- adk/tests/governance/test_topology_hub_spoke.py (rewritten: FakeCert +
  cert_resolver fixtures, independence test replaced)
- adk/tests/governance/test_topology_mesh.py (rewritten: FakeCert +
  cert_resolver fixtures, 1 new lineage-isolation test)
- adk/tests/governance/test_topology_dispatch.py (new)

## Concerns / open items

- The receive boundary's OWN internal chain-kappa check (single-hop,
  fresh ChainKappaTracker.from_envelope(envelope) per call) and the
  topology's own cross-hop ChainKappaTracker are now two independent
  chain-kappa gates layered on the same hop_kappa-vs-kappa_compat data.
  In these tests the certifier's derived kappa_compat is set to match
  each hop's intended hop_kappa so both gates agree; a caller whose
  certifier's derived kappa disagrees with its own hop_kappa could see
  the boundary refuse a hop the topology's own tracker would otherwise
  have accepted (or vice versa). This is intentional defense-in-depth,
  not a bug, but is worth flagging for anyone wiring a real certifier
  in.
- Coverage tooling (pytest-cov) hit an unrelated environment issue in
  this sandbox (ImportError: cannot load module more than once per
  process, from numpy, triggered by coverage's tracer) when measuring
  swarm_it.governance.* coverage directly; verification here relies on
  the full green test run plus manual enumeration of the new/changed
  branches rather than a machine coverage percentage.
