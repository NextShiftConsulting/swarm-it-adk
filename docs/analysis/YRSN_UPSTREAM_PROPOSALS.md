# YRSN Upstream Proposals

**Date:** 2026-02-24
**Context:** SDK development surfaced two minor gaps in yrsn core

---

## Summary

The SDK restructure confirmed yrsn's multimodal architecture is solid. The SDK was ignoring fields that yrsn already ships. However, two small enhancements would benefit both projects:

| Proposal | Impact | Effort |
|----------|--------|--------|
| Diagnostic attribution | Medium | Low |
| solver_type on certificate | Low | Trivial |

---

## Proposal 1: Diagnostic Attribution

### Current State

yrsn's `YRSNCertificate.admissibility_state` returns:
```python
if self.kappa_gate < threshold:
    return AdmissibilityState.INCOMPATIBLE
```

But it doesn't tell you **which modality** caused the incompatibility.

### The Gap

When `kappa_gate = 0.25` and:
- `kappa_H = 0.8` (healthy)
- `kappa_L = 0.25` (critical)
- `kappa_interface = 0.7` (healthy)

The SDK had to build `_diagnose_multimodal()` to answer:
> "Vision (κ_L=0.25) is dragging κ_gate below threshold while text (κ_H=0.8) is healthy."

### Proposed Addition

Add to `YRSNCertificate`:

```python
@property
def weak_modality(self) -> Optional[str]:
    """
    Identify which modality is causing kappa_gate to be low.

    Returns:
        "H" if kappa_H is weakest
        "L" if kappa_L is weakest
        "interface" if kappa_interface is weakest
        None if single-modal or all equal
    """
    if not self.is_multimodal:
        return None

    kappas = {
        "H": self.kappa_H,
        "L": self.kappa_L,
        "interface": self.kappa_interface,
    }
    valid = {k: v for k, v in kappas.items() if v is not None}
    if not valid:
        return None

    return min(valid, key=valid.get)

def diagnose(self) -> Dict[str, Any]:
    """
    Generate diagnostic dict explaining certificate state.

    Returns:
        Dict with attribution, health status, recommendations
    """
    if not self.is_multimodal:
        return {"multimodal": False}

    weak = self.weak_modality
    weak_value = getattr(self, f"kappa_{weak}", None) if weak else None

    # Health status per modality
    health = {}
    for name, value in [("H", self.kappa_H), ("L", self.kappa_L), ("interface", self.kappa_interface)]:
        if value is None:
            continue
        if value >= 0.7:
            health[name] = "healthy"
        elif value >= 0.4:
            health[name] = "degraded"
        else:
            health[name] = "critical"

    return {
        "multimodal": True,
        "kappa_gate": self.kappa_gate,
        "weak_modality": weak,
        "weak_value": weak_value,
        "health": health,
        "hierarchy_gap": self.hierarchy_gap,
        "is_desynced": any(h == "critical" for h in health.values()),
    }
```

### File to Modify

`yrsn/src/yrsn/core/decomposition/certificate.py` (or wherever `YRSNCertificate` lives)

---

## Proposal 2: solver_type on Certificate

### Current State

RSCT theory distinguishes solver types:
- Transformer (neural, high-level)
- Symbolic (SAT, theorem provers)
- Neuromorphic (analog compute)
- Hybrid

But `YRSNCertificate` doesn't carry `solver_type`. It's implicit in how κ is computed.

### The Gap

For compliance audits (SR 11-7), the certificate should be **self-contained**. Knowing what kind of solver produced it matters:
- Different solvers have different failure modes
- Regulatory documentation requires solver identification
- Cross-solver comparison needs explicit typing

### Proposed Addition

```python
class SolverType(Enum):
    """Type of solver that produced this certificate."""
    TRANSFORMER = "transformer"
    SYMBOLIC = "symbolic"
    NEUROMORPHIC = "neuromorphic"
    HYBRID = "hybrid"
    TOOL = "tool"
    HUMAN = "human"
    UNKNOWN = "unknown"

@dataclass
class YRSNCertificate:
    # ... existing fields ...

    # NEW: Optional solver identification
    solver_type: Optional[SolverType] = None
    solver_model: Optional[str] = None  # e.g., "claude-3-opus", "z3"
```

### Backward Compatibility

- Field is `Optional`, defaults to `None`
- Existing code unaffected
- `to_dict()` includes it only when set

---

## What Stays in SDK

Everything else from the SDK restructure is SDK-layer concern:

| Component | Reason to stay in SDK |
|-----------|----------------------|
| Error code taxonomy (V1.1.1, V4.4.1) | Operational interpretation, not geometry |
| ValidationFeedbackLoop | Threshold tuning is deployment-specific |
| Bridge functions | SDK ↔ Backend serialization |
| SR117AuditFormatter | Compliance formatting, not core math |
| Swarm topology models | Multi-agent orchestration, not RSCT core |

**Separation principle:** yrsn computes the geometry. SDK interprets it for operational use.

---

## Implementation Path

1. **PR to yrsn** with `weak_modality` property and `diagnose()` method
2. **Optional:** Add `solver_type` field to `YRSNCertificate`
3. **SDK update:** Remove `_diagnose_multimodal()`, call `cert.diagnose()` via bridge

---

## Appendix: SDK's _diagnose_multimodal() for Reference

```python
def diagnose_multimodal(cert: RSCTCertificate) -> Dict[str, Any]:
    """
    Diagnose multimodal issues based on kappa decomposition.
    """
    if not cert.has_kappa_decomposition:
        return {"available": False, "reason": "Kappa decomposition not available"}

    kappas = {
        "high_level": cert.kappa_H,
        "low_level": cert.kappa_L,
        "abstraction": cert.kappa_A,
        "interface": cert.kappa_interface,
    }

    valid_kappas = {k: v for k, v in kappas.items() if v is not None}
    if not valid_kappas:
        return {"available": False, "reason": "No valid kappa values"}

    weakest = min(valid_kappas, key=valid_kappas.get)
    weakest_value = valid_kappas[weakest]

    health = {}
    for name, value in valid_kappas.items():
        if value >= 0.7:
            health[name] = "healthy"
        elif value >= 0.4:
            health[name] = "degraded"
        else:
            health[name] = "critical"

    recommendations = []
    if weakest_value < 0.4:
        if weakest == "high_level":
            recommendations.append("Re-encode input with clearer semantic structure")
        elif weakest == "low_level":
            recommendations.append("Check signal quality or sensor calibration")
        elif weakest == "interface":
            recommendations.append("Check cross-modal alignment or use unified encoder")

    return {
        "available": True,
        "kappas": valid_kappas,
        "health": health,
        "weakest": weakest,
        "weakest_value": weakest_value,
        "recommendations": recommendations,
        "is_desynced": any(h == "critical" for h in health.values()),
    }
```

This function should live in yrsn core, not SDK.
