# Architecture Decision Record: Hardware Compression Profiles

**Date**: 2026-03-23
**Status**: ACCEPTED
**Decision**: Preserve two distinct embedding dimension profiles

---

## Context

The system currently operates with 1024-dimensional embeddings (Track 2 baseline).

A separate 1024→64 dimension compression path exists for:
- Future hardware embodiment (memristor crossbars)
- Multimodal text/vision alignment
- Edge deployment scenarios

**Critical distinction**: These are two separate profiles, not a migration path.

---

## Decision

We will maintain **two explicit profiles** with clear boundaries:

### Profile A: Native 1024-dim Track 2 (Current Operational Baseline)

- **Input**: 1024-dim embeddings from Bedrock Titan
- **Projection**: None (native dimension preserved)
- **Use case**: Current production, API deployment
- **Status**: PRODUCTION_VALIDATED
- **Certificate path**: Direct R-S-N decomposition from 1024-dim
- **Rotor checkpoint**: `trained_rotor_universal1024_titan.pt`

### Profile B: 1024→64 Hardware Compression (Protected Path)

- **Input**: 1024-dim embeddings from Bedrock Titan
- **Projection**: Learned linear projection to 64-dim
- **Use case**:
  - Future memristor/analog hardware
  - Multimodal alignment (text + vision)
  - Edge deployment with resource constraints
- **Status**: EXPERIMENTAL (protected architecture)
- **Certificate path**: R-S-N decomposition after 64-dim projection
- **Rotor checkpoint**: `trained_rotor_universal64.pt`
- **Projection checkpoint**: Required (versioned, validated)

---

## Key Principle

**Profile B is NOT the default production path.**

Profile B is a protected architecture profile that must not be accidentally removed or conflated with Profile A.

We preserve Profile B because:
1. Hardware path must remain viable for future embodiment
2. Multimodal alignment requires consistent dimension
3. Removing it would foreclose hardware deployment options
4. Re-creating the projection artifact later is expensive

---

## What We Do NOT Claim

❌ "Memristor-ready" (no isolated hardware validation yet)
❌ "Compression is harmless" (semantic loss is expected)
❌ "64-dim is proven optimal" (it's a design target, not proof)
❌ "Profile B is production-default" (it's experimental/protected)

---

## What We DO Preserve

✅ **64-dim path exists and is protected**
✅ **Dimension contract enforces change control**
✅ **Projection checkpoint is versioned and validated**
✅ **Hardware team approval required to remove Profile B**
✅ **Certificate quality must be validated after compression**

---

## Enforcement Mechanisms

1. **Dimension Contract** (`config/dimension_contract.yaml`)
   - Specifies input/output dimensions
   - Documents rationale and tradeoffs
   - Requires architecture + hardware approval for changes

2. **Projection Module** (`swarm_it/projection.py`)
   - Loads dimension contract at startup
   - Enforces dimension matching
   - Requires trained checkpoint (no fallback)

3. **Startup Validation**
   - Fail-fast if Profile B selected but checkpoint missing
   - Dimension assertions before server starts

4. **CI/CD Tests** (minimum 4 tests)
   - Projection dimensions match contract
   - Checkpoint exists for Profile B
   - Certificate quality validated after compression
   - Multimodal dimension alignment holds

5. **Profile Flags**
   - Explicit mode selection (A or B)
   - No silent switching between profiles
   - Logs show active profile at startup

---

## Profile Selection

Developers must explicitly choose profile:

```python
# Profile A: Native 1024-dim (current baseline)
engine = RSCTEngine(profile="TRACK2_NATIVE_1024")

# Profile B: Hardware compression (protected path)
engine = RSCTEngine(profile="COMPACT_64_MULTIMODAL")
```

**Default**: If unspecified, use Profile A (native 1024-dim).

---

## Change Control

### To modify Profile A (native 1024-dim):
- Architecture review (affects production)
- Update Track 2 rotor checkpoint
- Validate certificate quality
- Update deployment docs

### To modify Profile B (hardware compression):
- Architecture review
- **Hardware team approval** (affects future embodiment)
- Retrain projection checkpoint
- Update dimension contract
- Validate certificate quality at new dimension
- Update multimodal alignment tests

### To remove Profile B entirely:
- **Requires executive approval**
- Must document why hardware path is no longer viable
- Must consider multimodal alignment impact
- Cannot be accidental (protected by tests + contract)

---

## Rationale

**Why two profiles?**

- Profile A: Production-validated, current baseline
- Profile B: Future hardware optionality, multimodal readiness

**Why not merge them?**

- Different use cases (API vs hardware)
- Different validation requirements
- Different change control needs
- Semantic fidelity vs efficiency tradeoff

**Why protect Profile B?**

- Prevents accidental removal
- Preserves hardware deployment options
- Maintains multimodal alignment artifacts
- Avoids expensive re-creation later

---

## Consequences

### Accepted

- Two separate code paths for R-S-N decomposition
- Two rotor checkpoints to maintain
- Profile B requires projection checkpoint
- Explicit profile selection in configs

### Benefits

- Hardware path preserved for future embodiment
- Multimodal alignment protected
- Clear separation prevents confusion
- Change control prevents accidental damage

### Risks

- Profile B may become stale if unused
- Maintaining two paths increases complexity
- Profile confusion if not well-documented

### Mitigations

- Quarterly review of Profile B status
- CI tests prevent Profile B from breaking silently
- Clear documentation of profile differences
- Explicit profile flags prevent accidental use

---

## References

- FIRST_PRINCIPLES_v3_MODERN.md - PRINCIPLE 18
- `config/dimension_contract.yaml` - Profile B specification
- `swarm_it/projection.py` - Profile B implementation

---

**Next Review**: 2026-06-23 (quarterly)
**Owner**: Architecture Team
**Stakeholders**: Hardware Team, ML Team, Product
