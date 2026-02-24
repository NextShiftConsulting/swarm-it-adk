# SDK Certificate Alignment Strategy

**Date:** 2026-02-24
**Status:** PROPOSAL
**Key Insight:** Don't replicate YRSNCertificate — align for round-trip compatibility

---

## The Problem

| YRSNCertificate (Full) | SDK Certificate (Current) |
|------------------------|---------------------------|
| 6D signal: R, S, N, α, ω, τ | SimplexCoordinates(r, s, n) |
| Three stability concepts | Single κ float |
| 8 degradation types | None |
| Full κ/σ simplex decomposition | σ not exposed |
| Type I-VI validation hooks | None |
| Audit tuple format | Minimal dict |

**The SDK certificate is a lossy projection of the real thing.**

---

## The Wrong Move

❌ Replicate YRSNCertificate in SDK:
- Pulls in yrsn dependency tree (torch, numpy, etc.)
- Duplicates logic, creates drift
- Forces SDK users to understand full RSCT theory
- Bloats package size

---

## The Right Move

✅ **Alignment Layer**: SDK certificate round-trips with YRSNCertificate via JSON

```
┌─────────────────────────────────────────────────────────────┐
│                        YRSN Backend                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  YRSNCertificate                         ││
│  │  R, S, N, alpha, omega, tau                              ││
│  │  kappa_H, kappa_L, kappa_A, kappa_interface              ││
│  │  sigma, sigma_history                                    ││
│  │  admissibility, quality_envelope, lyapunov               ││
│  │  degradation_type, gate_reached, ...                     ││
│  └────────────────────────┬────────────────────────────────┘│
│                           │                                  │
│                     to_sdk_dict()                            │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │ JSON
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                        Swarm It SDK                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                  Certificate (Aligned)                   │  │
│  │                                                          │  │
│  │  # Core simplex (required)                               │  │
│  │  R, S, N: float                                          │  │
│  │                                                          │  │
│  │  # Compatibility (required)                              │  │
│  │  kappa_gate: float       # min(kappa_H, kappa_L, ...)    │  │
│  │  sigma: float            # Turbulence                    │  │
│  │                                                          │  │
│  │  # Extended (optional, from backend)                     │  │
│  │  alpha: Optional[float]  # Purity R/(R+N)                │  │
│  │  omega: Optional[float]  # OOD score                     │  │
│  │  tau: Optional[float]    # Temperature                   │  │
│  │                                                          │  │
│  │  # Stability (optional)                                  │  │
│  │  admissibility: Optional[float]                          │  │
│  │  quality_envelope: Optional[float]                       │  │
│  │  lyapunov: Optional[float]                               │  │
│  │                                                          │  │
│  │  # Classification (thin layer)                           │  │
│  │  rsct_mode: Optional[str]         # "3.1", computed      │  │
│  │  degradation_type: Optional[str]  # From backend or SDK  │  │
│  │  error_codes: List[str]           # V1.1.1, V5.II.1...   │  │
│  │                                                          │  │
│  │  # Gate result (required)                                │  │
│  │  decision: GateDecision                                  │  │
│  │  gate_reached: int                                       │  │
│  │  reason: str                                             │  │
│  │                                                          │  │
│  │  # Audit (required)                                      │  │
│  │  id: str                                                 │  │
│  │  timestamp: str                                          │  │
│  │  raw: Dict[str, Any]     # Preserves full backend data   │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 1. Round-Trip Protocol

### Backend → SDK

```python
# In yrsn certify_handler.py
def to_sdk_dict(self) -> dict:
    """Export YRSNCertificate for SDK consumption."""
    return {
        # Core (SDK required)
        "R": self.R,
        "S": self.S_sup,  # Note: S_sup in yrsn, S in SDK
        "N": self.N,
        "kappa_gate": self.kappa_gate,
        "sigma": self.sigma,

        # Extended (SDK optional)
        "alpha": self.alpha,
        "omega": self.omega,
        "tau": self.tau,
        "kappa_H": self.kappa_H,
        "kappa_L": self.kappa_L,
        "kappa_A": self.kappa_A,
        "kappa_interface": self.kappa_interface,

        # Stability (SDK optional)
        "admissibility": self.admissibility,
        "quality_envelope": self.quality_envelope,
        "lyapunov": self.lyapunov,

        # Classification
        "rsct_mode": self.rsct_mode,
        "degradation_type": self.degradation_type.value if self.degradation_type else None,

        # Gate
        "gate_decision": self.gate_decision.value,
        "gate_reached": self.gate_reached,
        "gate_reason": self.gate_reason,

        # Audit
        "certificate_id": self.certificate_id,
        "timestamp": self.timestamp,
    }
```

### SDK → Backend (for logging/audit)

```python
# In SDK client.py
def to_backend_dict(self) -> dict:
    """Export SDK Certificate for backend logging."""
    return {
        "certificate_id": self.id,
        "timestamp": self.timestamp,
        "simplex": {"R": self.R, "S": self.S, "N": self.N},
        "kappa_gate": self.kappa_gate,
        "sigma": self.sigma,
        "gate_decision": self.decision.value,
        "gate_reached": self.gate_reached,
        "source": "sdk",
        "sdk_version": __version__,
        # Include raw for full fidelity
        "raw": self.raw,
    }
```

---

## 2. Thin Classification Layer

Instead of computing degradation types from scratch, the SDK:

1. **Receives** classification from backend (if available)
2. **Computes** a lightweight approximation locally (fallback)

### Backend-Provided Classification

```python
# SDK receives from API
{
    "rsct_mode": "3.1",
    "degradation_type": "HALLUCINATION",
    "error_codes": ["V3.3.1"],
    ...
}

# SDK just stores it
cert.rsct_mode = data.get("rsct_mode")
cert.degradation_type = data.get("degradation_type")
cert.error_codes = data.get("error_codes", [])
```

### Local Fallback Classification

```python
# In SDK, when backend doesn't provide classification
def classify_local(self) -> str:
    """
    Lightweight RSCT mode classification.

    This is an APPROXIMATION. Full classification requires
    the rotor and additional signals not available locally.
    """
    # Group 1: Encoding
    if self.N >= 0.5:
        return "1.1"  # Noise Saturation
    if self.S > 0.6 and self.R < 0.2:
        return "1.2"  # Superfluous Drowning

    # Group 2: Dynamics (requires σ)
    if self.sigma and self.sigma > 0.7:
        return "2.1"  # Trajectory Divergence

    # Group 3: Semantic
    if self.kappa_gate > 0.7 and self.R < 0.4:
        return "3.1"  # Fluent Hallucination

    # Default
    return "0.0"  # No collapse detected
```

---

## 3. Updated SDK Certificate Class

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class GateDecision(Enum):
    EXECUTE = "EXECUTE"
    REJECT = "REJECT"
    BLOCK = "BLOCK"
    RE_ENCODE = "RE_ENCODE"
    REPAIR = "REPAIR"
    HALT = "HALT"
    TIMEOUT = "TIMEOUT"
    ESCALATE = "ESCALATE"


@dataclass
class Certificate:
    """
    SDK Certificate aligned with YRSNCertificate.

    Core fields are always present. Extended fields are populated
    when received from a full YRSN backend, None otherwise.
    """

    # === REQUIRED: Core Simplex ===
    id: str
    timestamp: str
    R: float          # Relevance [0, 1]
    S: float          # Support/Superfluous [0, 1]
    N: float          # Noise [0, 1]

    # === REQUIRED: Compatibility ===
    kappa_gate: float  # Enforced compatibility score
    sigma: float       # Turbulence

    # === REQUIRED: Gate Result ===
    decision: GateDecision
    gate_reached: int
    reason: str

    # === OPTIONAL: Extended Signals ===
    alpha: Optional[float] = None   # Purity: R/(R+N)
    omega: Optional[float] = None   # OOD score
    tau: Optional[float] = None     # Temperature

    # === OPTIONAL: Decomposed Kappa ===
    kappa_H: Optional[float] = None       # High-level
    kappa_L: Optional[float] = None       # Low-level
    kappa_A: Optional[float] = None       # Abstraction
    kappa_interface: Optional[float] = None  # Cross-modal

    # === OPTIONAL: Stability Metrics ===
    admissibility: Optional[float] = None
    quality_envelope: Optional[float] = None
    lyapunov: Optional[float] = None

    # === CLASSIFICATION ===
    rsct_mode: Optional[str] = None
    degradation_type: Optional[str] = None
    error_codes: List[str] = field(default_factory=list)

    # === AUDIT ===
    policy: str = "default"
    raw: Dict[str, Any] = field(default_factory=dict)

    # === COMPUTED PROPERTIES ===

    @property
    def allowed(self) -> bool:
        """Is execution allowed?"""
        return self.decision in (
            GateDecision.EXECUTE,
            GateDecision.REPAIR,  # Proceed with repair
        )

    @property
    def margin(self) -> float:
        """Safety margin: how far from rejection."""
        # Higher R, lower N, higher kappa = more margin
        return min(self.R, self.kappa_gate, 1.0 - self.N)

    @property
    def simplex_valid(self) -> bool:
        """Check R + S + N ≈ 1."""
        return abs(self.R + self.S + self.N - 1.0) < 0.01

    @property
    def has_extended_signals(self) -> bool:
        """Check if extended signals are available."""
        return self.alpha is not None

    @property
    def has_stability_metrics(self) -> bool:
        """Check if stability metrics are available."""
        return self.admissibility is not None

    def get_rsct_mode(self) -> str:
        """
        Get RSCT mode, computing locally if not provided.
        """
        if self.rsct_mode:
            return self.rsct_mode
        return self._classify_local()

    def _classify_local(self) -> str:
        """Lightweight local classification."""
        if self.N >= 0.5:
            return "1.1"
        if self.S > 0.6 and self.R < 0.2:
            return "1.2"
        if self.sigma and self.sigma > 0.7:
            return "2.1"
        if self.kappa_gate > 0.7 and self.R < 0.4:
            return "3.1"
        return "0.0"

    # === SERIALIZATION ===

    def to_dict(self) -> Dict[str, Any]:
        """Export for JSON serialization."""
        return {
            "certificate_id": self.id,
            "timestamp": self.timestamp,

            "simplex": {"R": self.R, "S": self.S, "N": self.N},
            "kappa_gate": self.kappa_gate,
            "sigma": self.sigma,

            "extended": {
                "alpha": self.alpha,
                "omega": self.omega,
                "tau": self.tau,
                "kappa_H": self.kappa_H,
                "kappa_L": self.kappa_L,
                "kappa_A": self.kappa_A,
                "kappa_interface": self.kappa_interface,
            } if self.has_extended_signals else None,

            "stability": {
                "admissibility": self.admissibility,
                "quality_envelope": self.quality_envelope,
                "lyapunov": self.lyapunov,
            } if self.has_stability_metrics else None,

            "classification": {
                "rsct_mode": self.get_rsct_mode(),
                "degradation_type": self.degradation_type,
                "error_codes": self.error_codes,
            },

            "gate": {
                "decision": self.decision.value,
                "gate_reached": self.gate_reached,
                "reason": self.reason,
            },

            "allowed": self.allowed,
            "margin": self.margin,
            "policy": self.policy,
        }

    @classmethod
    def from_backend(cls, data: Dict[str, Any]) -> "Certificate":
        """
        Parse backend response into SDK Certificate.

        Handles both full YRSNCertificate and minimal responses.
        """
        # Handle S vs S_sup naming
        s_value = data.get("S", data.get("S_sup", 0.0))

        # Parse decision
        decision_str = data.get("gate_decision", "EXECUTE")
        try:
            decision = GateDecision(decision_str)
        except ValueError:
            decision = GateDecision.EXECUTE

        return cls(
            id=data.get("certificate_id", ""),
            timestamp=data.get("timestamp", ""),

            # Core
            R=data.get("R", 0.0),
            S=s_value,
            N=data.get("N", 0.0),
            kappa_gate=data.get("kappa_gate", data.get("kappa", 0.0)),
            sigma=data.get("sigma", 0.0),

            # Extended (optional)
            alpha=data.get("alpha"),
            omega=data.get("omega"),
            tau=data.get("tau"),
            kappa_H=data.get("kappa_H"),
            kappa_L=data.get("kappa_L"),
            kappa_A=data.get("kappa_A"),
            kappa_interface=data.get("kappa_interface"),

            # Stability (optional)
            admissibility=data.get("admissibility"),
            quality_envelope=data.get("quality_envelope"),
            lyapunov=data.get("lyapunov"),

            # Classification
            rsct_mode=data.get("rsct_mode"),
            degradation_type=data.get("degradation_type"),
            error_codes=data.get("error_codes", []),

            # Gate
            decision=decision,
            gate_reached=data.get("gate_reached", 0),
            reason=data.get("gate_reason", data.get("reason", "")),

            # Audit
            policy=data.get("policy", "default"),
            raw=data,
        )
```

---

## 4. Validation Layer (Thin Wrapper)

```python
# swarm_it/classification.py

from typing import List
from .certificate import Certificate


def add_error_codes(cert: Certificate) -> Certificate:
    """
    Add error codes based on certificate values.

    This is a thin classification layer that doesn't
    require the full YRSN dependency tree.
    """
    codes = []

    # Pre-execution codes (based on simplex + kappa + sigma)
    if cert.N >= 0.5:
        codes.append("V1.1.1")  # Noise Saturation
    elif cert.N >= 0.3:
        codes.append("V1.1.1-WARN")

    if cert.S > 0.6 and cert.R < 0.2:
        codes.append("V1.1.2")  # Superfluous Drowning

    if cert.sigma and cert.sigma > 0.7:
        codes.append("V2.2.1")  # Trajectory Divergence

    if cert.kappa_gate > 0.7 and cert.R < 0.4:
        codes.append("V3.3.1")  # Fluent Hallucination

    if not cert.simplex_valid:
        codes.append("V0.0.1")  # Simplex Violation

    cert.error_codes = codes
    return cert


def classify_degradation(cert: Certificate) -> str:
    """
    Classify degradation type from certificate.

    Returns one of the 8 core degradation types.
    """
    if cert.degradation_type:
        return cert.degradation_type

    # Local approximation
    if cert.N >= 0.5:
        return "RSN_COLLAPSE"
    if cert.kappa_gate > 0.7 and cert.R < 0.4:
        return "HALLUCINATION"
    if cert.sigma and cert.sigma > 0.7:
        return "TRAJECTORY_DIVERGENCE"
    if cert.R < 0.3:
        return "LOW_RELEVANCE"

    return "NOMINAL"
```

---

## 5. What This Enables

### SDK User Experience (Simple)

```python
from swarm_it import SwarmIt

swarm = SwarmIt(api_key="...")
cert = swarm.certify("What is the capital of France?")

# Simple interface
if cert.allowed:
    print("Safe to execute")

print(f"Margin: {cert.margin:.2f}")
print(f"Mode: {cert.get_rsct_mode()}")  # "0.0" or "3.1" etc.
```

### Power User Experience (Full Access)

```python
# Access extended signals when available
if cert.has_extended_signals:
    print(f"Alpha: {cert.alpha:.3f}")
    print(f"Omega: {cert.omega:.3f}")
    print(f"Tau: {cert.tau:.3f}")

if cert.has_stability_metrics:
    print(f"Admissibility: {cert.admissibility:.3f}")
    print(f"Lyapunov: {cert.lyapunov:.3f}")

# Full backend data always available
print(cert.raw)
```

### Backend Integration (Zero Loss)

```python
# Backend logs the full certificate
audit_record = cert.to_dict()
s3_adapter.store(audit_record)

# Can reconstruct full YRSNCertificate from raw
full_cert = YRSNCertificate.from_dict(cert.raw)
```

---

## 6. Migration Path

| Phase | Action |
|-------|--------|
| 1 | Update SDK `Certificate` class with optional fields |
| 2 | Add `from_backend()` parser that handles full/minimal responses |
| 3 | Add thin `classification.py` layer for error codes |
| 4 | Update yrsn `certify_handler` to emit `to_sdk_dict()` format |
| 5 | Test round-trip: SDK → Backend → SDK |

---

## 7. What We DON'T Do

- ❌ Import yrsn in SDK
- ❌ Replicate rotor/simplex computation
- ❌ Implement full 40-type degradation taxonomy
- ❌ Run Type I-VI detectors in SDK (too heavy)
- ❌ Store σ_history (just current σ)

---

## Summary

**The SDK certificate is a projection, not a copy.** It carries enough information for:

1. **Gating decisions** (allowed, margin, decision)
2. **Basic diagnostics** (R/S/N, kappa, sigma)
3. **Classification** (rsct_mode, error_codes)
4. **Round-trip preservation** (raw dict)

Full RSCT analysis stays in the backend. The SDK is a thin, aligned client.
