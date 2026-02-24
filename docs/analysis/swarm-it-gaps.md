# Swarm It SDK Gap Analysis

**Date:** 2026-02-24
**Reference:** SOTA Paper — *Intelligence as Representation-Solver Compatibility* (RSCT Preprint v3)

---

## Executive Summary

The Swarm It SDK prototype provides a functional certification client with decorator patterns and framework integrations. However, significant gaps exist between the theoretical foundation (RSCT) and the productized implementation. This analysis excavates gaps across **enterprise/compliance**, **cost optimization**, and **audience** dimensions.

**Critical finding:** The SDK gates individual LLM calls but has no implementation of the multi-agent coordination story—which is swarm-it's entire competitive moat.

---

## 1. Enterprise/Compliance Gaps (Highest Priority)

The SOTA paper explicitly positions RSCT as operationalizing SR 11-7 and EU AI Act requirements. The SDK has **zero compliance tooling** despite this being the strongest differentiator.

### 1.1 Certificate Persistence and Audit Trail

**SOTA Requirement (Appendix B.3):**
> Every gatekeeper invocation produces:
> $$\mathcal{L} = (\alpha, \omega, \alpha_\omega, \kappa_{\text{gate}}, \sigma, \texttt{gate\_reached}, \texttt{outcome}, t_{\text{stamp}})$$
> This tuple directly satisfies SR 11-7 Section 4(c) requirements.

**SDK State:** The `Certificate` dataclass lives in memory only. No persistence layer exists.

**Missing:**
- S3/DynamoDB audit storage adapter
- Immutable append-only log with tamper detection
- Certificate retrieval by ID, time range, or session
- Retention policy enforcement (SR 11-7 requires multi-year retention)
- Export formats (JSON-LD, XBRL for regulatory submission)

**Gap Severity:** Critical — Regulated firms cannot use the SDK without this.

---

### 1.2 Policy Engine

**SOTA Context:** The gatekeeper enforces thresholds ($N_{\text{threshold}}$, $c_{\min}$, $\kappa_{\text{base}}$, $\lambda$, $\sigma_{\text{thr}}$) that must be configurable per deployment context.

**SDK State:** The `certify()` call accepts a `policy` string but:
- No policy definition format exists
- No policy versioning or approval workflow
- No policy-to-threshold mapping
- No audit trail of policy changes

**Missing:**
```yaml
# Example: What a policy definition should look like
policy:
  name: "financial-compliance-strict"
  version: "3.2"
  approved_by: "compliance-team"
  approved_date: "2026-02-15"
  thresholds:
    N_threshold: 0.4      # Tighter than default 0.5
    kappa_base: 0.6       # Higher than default 0.5
    lambda: 0.5           # More conservative Oobleck
    sigma_thr: 0.4        # Lower turbulence tolerance
  gates:
    - integrity_guard     # Gate 1: Always enabled
    - consensus_gate      # Gate 2: Enabled
    - admissibility_gate  # Gate 3: Enabled with Oobleck
    - grounding_repair    # Gate 4: Enabled
```

**Gap Severity:** High — Enterprise customers need governance over threshold configuration.

---

### 1.3 Regulatory Report Generation

**SOTA Requirement:** The paper maps RSCT certificates to SR 11-7, PRA SS1/23, and ECB TRIM requirements.

**SDK State:** No report generation capability.

**Missing:**
- SR 11-7 formatted audit reports
- EU AI Act risk assessment templates
- Model card generation with RSCT metrics
- Back-testing record aggregation (required by SR 11-7 §4(c))
- Examiner-ready documentation export

---

### 1.4 Role-Based Access Control

**SDK State:** No concept of authorization.

**Missing:**
- Who can set/modify policies
- Who can override gate blocks
- Who can access audit logs
- API key scoping by role
- SSO/SAML integration hooks

---

## 2. Cost Optimization Gaps (Completely Absent)

The SDK has no cost awareness despite cost being a primary concern for LLM deployments.

### 2.1 Token/Cost Telemetry

**Missing:**
- Cost of certification call itself (the RSCT computation)
- Token usage tracking per certified request
- Cost attribution by policy, user, session
- Budget enforcement (block if cost threshold exceeded)

### 2.2 Gate Savings Calculator

**Value Proposition Proof Point:**

The SDK should answer: "We blocked N bad prompts this week, saving $X in wasted inference."

**Missing:**
- Blocked request counter with estimated cost savings
- Quality improvement metrics (error rate before/after gating)
- ROI dashboard data export

### 2.3 Cost-Aware Routing

**SOTA Context (Section 5.1):** The gatekeeper can route to different execution modes based on certificate values.

**SDK State:** No routing logic. The SDK is a binary gate (allow/block) with no intermediate modes.

**Missing from SOTA Implementation:**
| Gate Decision | RSCT Action | SDK Implementation |
|---------------|-------------|-------------------|
| High κ, low σ | FAST mode (direct LLM) | Not implemented |
| Medium κ | GUARDED mode (with guardrails) | Not implemented |
| Low κ, recoverable | RE_ENCODE (retry with repair) | Not implemented |
| Low κ_L | REPAIR (grounding augmentation) | Not implemented |

The yrsn SERG handlers have this routing logic, but it's not exposed in the SDK.

---

## 3. ML Engineer Experience Gaps

### 3.1 No Tests

**SDK State:** Zero test files.

**Impact:** An ML engineer evaluating via `pip install` will check for tests first. No tests = no confidence.

**Missing:**
- Unit tests for `Certificate`, `SwarmIt`, decorators
- Integration tests with mocked API
- Property-based tests for simplex normalization (R + S + N = 1)
- Adversarial input tests (gatekeeper bypass detection per Mode 4.4)

---

### 3.2 No Local/Embedded Mode

**SDK State:** Requires a running API backend. No offline capability.

**Missing:**
```python
# What should exist:
swarm = SwarmIt(mode="local")  # Runs RSCT math in-process
swarm = SwarmIt(mode="embedded", checkpoint="rotor.pt")  # With trained model
```

**Why it matters:**
- Development without network dependency
- Edge deployment (the SOTA paper explicitly addresses neuromorphic/edge contexts)
- Proof that the math works independent of infrastructure
- Latency-sensitive applications

---

### 3.3 No Observability Hooks

**SDK State:** No structured logging, no metrics export.

**Missing:**
- OpenTelemetry spans for certification calls
- Prometheus metrics (`swarmit_certifications_total`, `swarmit_blocks_total`, `swarmit_latency_seconds`)
- Structured logging with correlation IDs
- Trace context propagation

**Irony:** This is an observability product with no observability in the SDK.

---

### 3.4 Async Support Incomplete

**SDK State:** The `@gate` decorator doesn't properly handle async functions.

```python
# This will fail:
@swarm.gate
async def ask_llm(prompt):
    return await openai.chat.completions.create(...)
```

**Missing:**
- `@gate` decorator with async/await support
- Async `certify()` method
- Connection pooling for async HTTP client

---

## 4. Architecture Gaps (The Big One)

### 4.1 SDK ↔ Dashboard Disconnection

**Problem:** The SDK and swarm-it dashboard are completely separate systems with no integration.

**Missing:**
- Event bus / webhook for SDK → dashboard certificate events
- WebSocket/SSE stream for live visualization
- Shared schema for certificate format
- Dashboard can't see what the SDK is certifying

---

### 4.2 No Multi-Agent Topology Model

**SOTA Context (Section 6.1, Table 5):** The paper introduces the "Navigator" class—systems whose function is to certify representational conditions across heterogeneous workflows.

> As AI systems migrate from single-model deployments to heterogeneous agentic pipelines—operating across modalities, solver types, and deployment environments... the question of which solver to use becomes secondary to the question of whether the encoding presented to any given solver lies within its admissible region.

**SDK State:** Gates individual LLM calls only. No concept of:
- Agent identity
- Agent-to-agent communication flows
- Cross-agent interface compatibility ($\kappa_{\text{interface}}$)
- Swarm topology representation
- Coordination conflict detection

**This is critical:** Swarm-it's positioning is "observability for AI agent swarms." The SDK has no swarm concept at all.

**Missing Data Model:**
```python
# What should exist:
class Agent:
    id: str
    role: str
    solver_type: str  # transformer, symbolic, hybrid
    kappa_profile: Dict[str, float]  # Per-modality health

class AgentLink:
    source: Agent
    target: Agent
    interface_type: str  # message, tool_call, memory_share
    kappa_interface: float  # Cross-agent compatibility

class Swarm:
    agents: List[Agent]
    topology: List[AgentLink]
    consensus: float  # c in RSCT (phasor coherence)

# Certification at swarm level:
cert = swarm_client.certify_swarm(swarm, task_encoding)
```

---

### 4.3 The 16-Mode Collapse Taxonomy Not Exposed

**SOTA Contribution:** Table 3 provides a 16-type failure taxonomy across four groups:
- Group 1: Noise Saturation (N ≥ 0.5)
- Group 2: Turbulence/Instability (σ > σ_thr)
- Group 3: Compatibility Gap (κ < κ_req)
- Group 4: Meta-Safety Violations

**SDK State:** Returns a single `GateDecision` enum with limited types.

**Missing:**
- Full 16-mode classification in certificate response
- Mode-specific remediation recommendations
- Collapse mode tracking for analytics
- Detector implementations (GradientStarvationDetector, RewardHackingDetector, GatekeeperBypassDetector exist in yrsn but not in SDK)

---

## 5. Gap Prioritization

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| Local certification mode | Proves math works | Medium | **P0** |
| Multi-agent topology model | Core differentiator | High | **P0** |
| Certificate persistence + audit | Enterprise requirement | Medium | **P1** |
| Tests | Credibility | Low | **P1** |
| 16-mode taxonomy exposure | Diagnostic value | Low | **P1** |
| Policy engine | Enterprise governance | Medium | **P2** |
| Observability hooks | Dogfooding | Low | **P2** |
| Cost tracking | ROI proof | Medium | **P2** |
| Async support | Developer experience | Low | **P2** |
| Regulatory reports | Compliance automation | High | **P3** |
| RBAC | Enterprise security | Medium | **P3** |

---

## 6. Recommendations

### Immediate (Week 1)
1. **Add local certification mode** — Embed the HybridSimplexRotor from yrsn directly in the SDK with a fallback hash-based mode already exists but a real local mode with trained checkpoint
2. **Add tests** — At minimum, test the Certificate simplex constraint (R + S + N = 1), gate decision mapping, and decorator behavior
3. **Expose full 16-mode taxonomy** — Port the `classify_rsct()` function from yrsn's `collapse_classifier.py`

### Short-term (Month 1)
4. **Design multi-agent data model** — Define `Agent`, `AgentLink`, `Swarm` schemas that can feed the dashboard topology view
5. **Add certificate persistence** — S3 adapter from yrsn already exists; expose it through the SDK
6. **Add OpenTelemetry instrumentation** — One day of work, massive credibility boost

### Medium-term (Quarter 1)
7. **Build policy engine** — YAML-based policy definition with versioning
8. **Connect SDK to dashboard** — WebSocket event stream for live certificate flow
9. **Cost tracking** — Token telemetry and savings calculator

---

## 7. The Fundamental Question

The SOTA paper's abstract states:

> RSCT provides the mathematical language to make representation certification precise, tractable, and auditable.

The SDK provides *tractable* (you can call `certify()`). It does not yet provide:
- **Precise** — Local mode needed to prove the math
- **Auditable** — Persistence and compliance tooling needed

And critically, the multi-agent coordination story—the entire positioning of "swarm-it"—has no implementation whatsoever.

**The SDK is a single-agent gating tool being marketed as a swarm governance platform.**

This gap must close before launch.
