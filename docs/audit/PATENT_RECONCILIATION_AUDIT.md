# Patent Reconciliation Audit: swarm-it-adk

**Date:** 2026-04-24 (Re-audit)
**Patent:** US Application 19/575,615 (TUP96543)
**Status:** ADVISORY ONLY -- NO CODE CHANGES

---

## Executive Summary

The ADK provides agent framework integration. Only change since initial audit: MeasurementEstimate rename handled correctly in compat bridge. All gaps remain: consumer roles absent, morph repair absent, on_llm_end still `pass`, P1 decorators opt-in with **fail-open bypass** in middleware.

---

## Findings

| Claim | Status | Evidence | Changed? |
|-------|--------|----------|----------|
| Claim 3 (Consumer roles) | **GAP** | No ConsumerRole types anywhere | No |
| Claim 9 Loop 1 (Morph repair) | **GAP** | No morph operators. `_autofix()` at `feedback_loops.py:290-303` is string-append stub | No |
| Claim 9 Loop 2 (Agent handoff) | **TEST-ONLY** | `test_doe_loop2_handoff.py` has EventNode, RepresentationGraph, certify_output(). Not imported by production. Uses fragile `exec()` pattern. | No |
| Claim 9 (on_llm_end) | **GAP** | `langchain.py:204-206` -- `pass`. LLM output not certified. | No |
| P1 (Certificate-first) | **OPT-IN + BYPASSABLE** | `@gate`, `@certified`, `@require_certificate` are opt-in. **Fail-open:** `fastapi.py:132-133` catches Exception and passes through. `decorators.py:46-49` executes without gating when context is None. | No |
| P5 (No runtime learning) | **COMPLIANT** | Hash-based local engine, no optimizer/gradient code | No |
| P11 (DGM output cert) | **GAP** | `on_llm_end` is `pass`. No `@certify_output` in production. | No |
| MeasurementEstimate bridge | **COMPLIANT** | `_compat.py:144` -- `to_certificate_estimate = to_measurement_estimate` alias. All callers use alias. | FIXED |

### Critical Finding: P1 Fail-Open

`swarm-it-adk/adk/swarm_it/integrations/fastapi.py:132-133`:
```python
except Exception:
    pass  # Certification failed, allow through (fail-open)
```

This contradicts P1 certificate-first in any middleware deployment.

### Unprotected Innovations

| Innovation | Location | Description |
|-----------|----------|-------------|
| Loop 2 DOE test architecture | `test_doe_loop2_handoff.py:133-210` | EventNode, RepresentationGraph, certify_output -- test-only |
| Topology/Swarm modeling | `topology/models.py` | SolverType, Modality, Agent, Channel, Swarm |
