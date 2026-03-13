# RSCT Deep Dive: P15 Rotor Architecture & T⁴ Toroidal Extension

A PhD-level technical reference for the RSCT certification system.

**Generated:** 2026-03-13
**Source:** SWARM-01 Experiment Analysis Session

---

## Table of Contents

1. [SWARM-01 Theoretical Foundations](#swarm-01-theoretical-foundations)
2. [The 4-Gate Pipeline](#the-4-gate-pipeline)
3. [κ Decomposition (Hierarchical Compatibility)](#κ-decomposition-hierarchical-compatibility)
4. [P15 Rotor Architecture](#p15-rotor-architecture)
5. [T⁴ Toroidal Extension](#t4-toroidal-extension)
6. [Proofs](#proofs)

---

## SWARM-01 Theoretical Foundations

### The Core Problem

Multi-agent systems lack a **formal certification mechanism** for output quality. RSCT (Representation-Space Compatibility Theory) proposes a mathematically rigorous framework where agent outputs are certified through a 4-gate pipeline with provable guarantees.

### Hypothesis Validation — Gate Boundary Conditions

| H | Formal Statement | Gate | Mathematical Basis |
|---|------------------|------|-------------------|
| H1 | ∀x: N(x) ≥ 0.5 → REJECT | G1 | Noise dominance threshold |
| H2 | ∀x: c(x) < 0.4 → BLOCK | G2 | Consensus failure detection |
| H3 | κ_req(σ) = 0.5 + 0.4σ | G3 | Oobleck dynamics (stress-adaptive) |
| H4 | Gray zone: κ_req ± 0.05, σ tie-breaker | G3 | Landauer tolerance bound |
| H5 | κ_L < 0.3 → REPAIR | G4 | Grounding failure threshold |
| H6 | ∀x: R + S + N = 1 ± 1e-6 | All | Simplex invariant (by construction) |
| H7 | Var(API entry points) = 0 | All | Implementation consistency |
| H8 | ∀chains: κ_interface ≥ 0.5 | Handoff | Certificate chaining |

**Why 100% matters:** These aren't statistical hypotheses—they're **structural invariants**. Failure would indicate a bug in the certification logic, not sampling variance.

---

## The 4-Gate Pipeline

```
Input → [G1: Noise] → [G2: Consensus] → [G3: Oobleck] → [G4: Grounding] → Output
           ↓              ↓                ↓                ↓
        REJECT          BLOCK          RE_ENCODE          REPAIR
```

| Gate | Signal | Threshold | Failure Mode |
|------|--------|-----------|--------------|
| G1 | N | ≥ 0.5 | Noise saturation |
| G2 | c (consensus) | < 0.4 | Multi-agent disagreement |
| G3 | κ vs κ_req(σ) | κ < κ_req | Compatibility failure |
| G4 | κ_L | < 0.3 | Grounding collapse |

### Gate Order Security

**Theorem:** G₁ → G₂ → G₃ → G₄ is the **unique valid ordering**.

```
Lemma 1: N ≥ 0.5 corrupts all downstream signals
         ∴ G₁ < {G₂, G₃, G₄}

Lemma 2: c < 0.4 means incoherent simplex projections across agents
         ∴ G₂ < G₃

Lemma 3: Global κ failure makes local κ_L evaluation pointless
         ∴ G₃ < G₄

Combining: G₁ < G₂ < G₃ < G₄ (total order, unique)
```

### RSN Simplex Decomposition

The signal space is a 2-simplex Δ² embedded in ℝ³:

```
Δ² = {(R, S, N) ∈ ℝ³ : R + S + N = 1, R,S,N ≥ 0}
```

| Region | Condition | Interpretation |
|--------|-----------|----------------|
| R-dominant | R > max(S, N) | Signal-aligned, high intent fidelity |
| S-dominant | S > max(R, N) | Redundancy-heavy, verbose but safe |
| N-dominant | N > max(R, S) | Noise-saturated, reject candidate |
| Balanced | max(R,S,N) < 0.4 | Mixed signal, requires disambiguation |

### Oobleck Dynamics

Named after the non-Newtonian fluid that hardens under stress:

```
κ_req(σ) = κ_base + β·σ
         = 0.5 + 0.4σ
```

Where:
- κ_req ∈ [0.5, 0.9]: Required compatibility threshold
- σ ∈ [0, 1]: Turbulence (measured from σ_var, σ_growth, σ_entropy)
- κ_base = 0.5: Baseline compatibility (calm conditions)
- β = 0.4: Oobleck coefficient (stress sensitivity)

**Uniqueness proof:** The function is the unique linear mapping satisfying:
1. κ_req(0) = 0.5 (baseline)
2. κ_req(1) = 0.9 (maximum stress)
3. dκ_req/dσ > 0 (monotonically increasing)

**Phase regions:**

| Zone | Condition | Action |
|------|-----------|--------|
| EXECUTE | κ ≥ κ_req(σ) | Pass to next gate |
| RE_ENCODE | 0.3 ≤ κ < κ_req(σ) | Request reformulation |
| BLOCK | κ < 0.3 | Hard reject |

---

## κ Decomposition (Hierarchical Compatibility)

### The Four Kappas

| κ | Name | What It Measures | Failure Mode |
|---|------|------------------|--------------|
| κ_H | High-level | Semantic/symbolic coherence | "Knows facts but wrong context" |
| κ_L | Low-level | Perceptual/signal grounding | "Sees pixels but misidentifies objects" |
| κ_A | Abstraction | Concept-to-implementation mapping | "Correct abstraction, wrong instantiation" |
| κ_interface | Interface | Cross-modal agreement | "Text says X, image shows Y" |

### Hierarchical Architecture (Multimodal)

```
          ┌─────────────┐
          │   κ_H       │  ← Text/reasoning layer
          │ (semantic)  │
          └──────┬──────┘
                 │ κ_interface (cross-modal binding)
          ┌──────┴──────┐
          │   κ_L       │  ← Vision/perception layer
          │ (grounding) │
          └─────────────┘
                 │
          ┌──────┴──────┐
          │   κ_A       │  ← Abstraction mapping
          │ (concept→impl)│
          └─────────────┘
```

### Gating Computation

The enforced `kappa_gate` is the **bottleneck**:

```python
kappa_gate = min(kappa_H, kappa_L, kappa_A, kappa_interface)
```

### Failure Mode Taxonomy (Group 4)

| Mode | Condition | Diagnosis |
|------|-----------|-----------|
| 4.1 WEAKEST_LINK_CASCADE | min(κ_H, κ_L, κ_A) < 0.3 | One layer collapsed, propagates up |
| 4.2 CROSS_MODAL_DESYNC | κ_interface < 0.3 | Modalities disagree on same input |

### Full RSCT Mode Taxonomy

```python
def _classify_local(self) -> str:
    # Group 1: Encoding
    if self.N >= 0.5:           return "1.1"  # Noise Saturation
    if self.S > 0.6 and R < 0.2: return "1.2"  # Superfluous Drowning

    # Group 2: Dynamics
    if self.sigma > 0.7:         return "2.1"  # Trajectory Divergence

    # Group 3: Semantic
    if kappa_gate > 0.7 and R < 0.4: return "3.1"  # Fluent Hallucination
    if alpha < 0.3:              return "3.2"  # Phasor Conflict

    # Group 4: Execution
    if min(κ_H, κ_L, κ_A) < 0.3: return "4.1"  # Weakest-Link Cascade
    if κ_interface < 0.3:        return "4.2"  # Cross-Modal Desync

    return "0.0"  # No collapse
```

| Group | Domain | What Breaks |
|-------|--------|-------------|
| 1.x | Encoding | Input signal itself is garbage |
| 2.x | Dynamics | System trajectory is unstable |
| 3.x | Semantic | Meaning is corrupted (hallucination, conflict) |
| 4.x | Execution | Multi-layer or multi-modal failure |

---

## P15 Rotor Architecture

### The Core Insight: Why Rotations?

**Problem:** How do you map a high-dimensional embedding (768D from BERT, 1536D from OpenAI) to the 2-simplex (R + S + N = 1) while:
1. Preserving semantic structure
2. Guaranteeing the simplex constraint
3. Making the transformation interpretable

**Answer:** Geometric Algebra rotors with barycentric projection.

### Architecture Overview

```
                    HybridSimplexRotor Pipeline
    ┌──────────────────────────────────────────────────────────────┐
    │                                                              │
    │   embed_dim (768)        hidden (256)        subspace (64)   │
    │       │                     │                    │           │
    │       ▼                     ▼                    ▼           │
    │   ┌───────┐   ReLU    ┌───────┐   ReLU    ┌───────┐         │
    │   │Linear │ ────────► │Linear │ ────────► │Linear │         │
    │   └───────┘           └───────┘           └───────┘         │
    │                                                │             │
    │                         Nonlinear Encoder      │             │
    │   ─────────────────────────────────────────────┼─────────    │
    │                                                ▼             │
    │                                          ┌─────────┐         │
    │                                          │ to_2D   │         │
    │                                          │ Linear  │         │
    │                                          └────┬────┘         │
    │                                               │              │
    │                                          (u, v) ∈ ℝ²         │
    │                                               │              │
    │                         Explicit Rotor       ▼              │
    │   ─────────────────────────────────────────────────────────  │
    │                                     ┌─────────────────┐      │
    │                                     │  R(θ) rotation  │      │
    │                                     │  [cos θ  -sin θ]│      │
    │                                     │  [sin θ   cos θ]│      │
    │                                     └────────┬────────┘      │
    │                                              │               │
    │                                         (u', v')             │
    │                                              │               │
    │                      Barycentric Map         ▼               │
    │   ─────────────────────────────────────────────────────────  │
    │                              ┌────────────────────────┐      │
    │                              │  Equilateral Triangle  │      │
    │                              │      R (0°)            │      │
    │                              │     /    \             │      │
    │                              │    /      \            │      │
    │                              │   S(120°)  N(240°)     │      │
    │                              └────────────────────────┘      │
    │                                              │               │
    │                                         softmax              │
    │                                              │               │
    │                                      (R, S, N) ∈ Δ²          │
    │                                   R + S + N = 1 ✓            │
    └──────────────────────────────────────────────────────────────┘
```

### Stage 1: Nonlinear Encoder

```python
self.encoder = nn.Sequential(
    nn.Linear(embed_dim, hidden_dim),      # 768 → 256
    nn.ReLU(),
    nn.Linear(hidden_dim, hidden_dim // 2), # 256 → 128
    nn.ReLU(),
    nn.Linear(hidden_dim // 2, subspace_dim), # 128 → 64
)
```

**Why nonlinear?** Pure geometric rotors (Phase B experiment) failed on real data because:
- Real embeddings live on complex nonlinear manifolds
- Linear projection loses semantic structure
- Need capacity to "unfold" the manifold before rotation

### Stage 2: Projection to 2D Plane

```python
self.to_2d = nn.Linear(subspace_dim, 2)
```

The 2-simplex Δ² is a 2-dimensional surface embedded in ℝ³. We project to 2D because:
- Rotations in 2D are parameterized by a single angle θ
- Interpretable: θ tells you the "rotation to quality"
- Efficient: Only 2 parameters learned

### Stage 3: Explicit Rotor

```python
self.theta = nn.Parameter(torch.tensor(0.0))  # Learned angle
self.scale = nn.Parameter(torch.tensor(1.0))  # Learned scale

c, s = torch.cos(self.theta), torch.sin(self.theta)
u_rot = (c * uv[:, 0] - s * uv[:, 1]) * self.scale
v_rot = (s * uv[:, 0] + c * uv[:, 1]) * self.scale
```

This is a standard 2D rotation matrix:

```
R(θ) = [cos θ  -sin θ] × scale
       [sin θ   cos θ]
```

### Lie Algebra Parameterization (Higher Dimensions)

For higher dimensions, learning rotation matrices directly causes orthogonality drift. The Lie algebra approach:

```python
class RotorLayer(nn.Module):
    """
    Learn bivector B (skew-symmetric), compute R = exp(B).
    Guaranteed orthogonal with det(R) = +1.
    """
    def get_bivector(self):
        return self.B_param - self.B_param.T  # Skew-symmetric

    def get_rotation_matrix(self):
        B = self.get_bivector()
        return torch.matrix_exp(B)  # Guaranteed orthogonal
```

### Stage 4: Barycentric Map to Simplex

The magic that guarantees R + S + N = 1:

```python
# Vertices of equilateral triangle at 120° angles
rsn_logits = torch.stack([
    1.0 + u_rot,                          # R vertex (0°)
    1.0 - 0.5 * u_rot + 0.866 * v_rot,   # S vertex (120°)
    1.0 - 0.5 * u_rot - 0.866 * v_rot,   # N vertex (240°)
], dim=-1)
rsn = F.softmax(rsn_logits, dim=-1)  # GUARANTEES sum = 1
```

**Why 0.866?** That's √3/2, the height of an equilateral triangle with unit base.

### Low-Rank Rotor Adaptation (RoRA)

```python
class LowRankRotorLayer(nn.Module):
    """
    Constrains rotor to rotate in only `rank` planes.
    Forces "minimal geometric action".

    B = UV^T - VU^T  # Skew-symmetric, rank ≤ 2*rank
    """
    def __init__(self, dim, rank=1):
        self.U = nn.Parameter(torch.randn(dim, rank) * 0.01)
        self.V = nn.Parameter(torch.randn(dim, rank) * 0.01)
```

**Benefits:**
1. Parameter efficiency: Only 2 × dim × rank parameters
2. Prevents catastrophic forgetting
3. Mergeable via SLERP on bivectors

### Variant Comparison

| Variant | Params | Architecture | Use Case |
|---------|--------|--------------|----------|
| **LARGE** | 107K | 3-layer encoder + rotor | Production, best accuracy |
| **COMPACT** | 37K | 2-layer encoder + rotor | Edge deployment |
| **TINY** | 8.5K | 2-layer small encoder | Extreme constraints |
| **PURE** | 516 | Linear + rotor only | Research, synthetic data |

### Why This Is Patented (P15)

**IP protection via geometric constraint:**
- Simple `nn.Linear → softmax` is trivial to copy
- The specific combination of:
  1. Nonlinear encoder
  2. Lie algebra rotor parameterization
  3. Barycentric equilateral projection
  4. Interpretable θ parameter

...is patented and validated across modalities.

---

## T⁴ Toroidal Extension

### The Core Insight: Why a Torus?

**Problem:** The RSN simplex Δ² (R + S + N = 1) is a 2-dimensional surface. But RSCT needs to track 4 independent quality dimensions. How do you extend without breaking the simplex constraint?

**Answer:** Embed the simplex in a 4-dimensional torus T⁴ = S¹ × S¹ × S¹ × S¹

### What Is T⁴?

A **4-torus** is the Cartesian product of four circles:

```
T⁴ = S¹ × S¹ × S¹ × S¹
```

Each circle S¹ is parameterized by an angle θ ∈ [0, 360°). The 4-torus has:
- **4 independent periodic dimensions** (each wraps around)
- **Topology:** 4 non-contractible loops (H₁ = 4)
- **Metric:** Geodesic distance requires wrapped arithmetic

### The 4 Coordinates

```python
def compute_t4_coordinates(R, S, N) -> dict:
    return {
        'simplex_theta': compute_simplex_theta(R, S, N),  # [0, 360°)
        'phi_simplex': compute_phi_simplex(R, S, N),      # [0, 360°)
        'alpha_t4': compute_alpha(R, S, N),               # [0, 180°)
        'omega_t4': compute_omega(R, S, N),               # [0, 90°]
    }
```

| Coordinate | Range | Derivation | Interpretation |
|------------|-------|------------|----------------|
| **simplex_θ** | [0, 360°) | atan2(barycentric coords) | Angular position on simplex |
| **φ_simplex** | [0, 360°) | distance from center | How extreme (center vs vertex) |
| **α_t4** | [0, 180°) | arccos(R) × 180/π | Quality level |
| **ω_t4** | [0, 90°] | arccos(φ_normalized) | OOD confidence |

### Coordinate Derivations

#### 1. simplex_θ: Angular Position

```python
def compute_simplex_theta(R, S, N):
    """Where on the simplex are you?"""
    # Simplex vertices (equilateral triangle)
    # R = (0, 0), S = (1, 0), N = (0.5, √3/2)
    x = S + 0.5 * N
    y = (np.sqrt(3) / 2) * N

    # Shift to center then compute angle
    return atan2(y - center_y, x - center_x)
```

**Interpretation:**
- θ = 240°: R-dominant (near R vertex)
- θ = 0°: S-dominant (near S vertex)
- θ = 120°: N-dominant (near N vertex)

#### 2. φ_simplex: Distance from Center

```python
def compute_phi_simplex(R, S, N):
    """How far from the center (R=S=N=1/3)?"""
    center = 1/3
    distance = sqrt((R - center)² + (S - center)² + (N - center)²)
    max_distance = sqrt(2/3)  # Distance to any vertex
    return (distance / max_distance) * 360
```

**Interpretation:**
- φ ≈ 0°: Balanced signal (near center)
- φ ≈ 360°: Extreme signal (pure R, S, or N)

#### 3. α_t4: Quality Level

```python
def compute_alpha(R, S, N):
    """Quality from Relevance."""
    return arccos(R) * 180 / π
```

**Interpretation:**
- α = 0°: Perfect quality (R = 1.0)
- α = 60°: Good quality (R = 0.5)
- α = 180°: Zero quality (R = 0.0)

#### 4. ω_t4: OOD Confidence

```python
def compute_omega(R, S, N):
    """Out-of-distribution detection."""
    phi_normalized = compute_phi_simplex(R, S, N) / 360
    return arccos(phi_normalized) * 180 / π
```

**Interpretation:**
- ω ≈ 0°: High confidence (at boundary, clear signal)
- ω ≈ 90°: Low confidence (at center, ambiguous)

**Critical bug fix (v2.6):** ω ∈ [0, 90°], NOT [0, 180°).

### Why Wrapped Distance Matters

```python
# WRONG: Euclidean distance
euclidean = abs(350° - 10°)  # = 340° (WRONG!)

# CORRECT: Wrapped distance
wrapped = min(|350° - 10°|, 360° - |350° - 10°|)  # = 20° ✓
```

**Why this matters:**
- 10° and 350° are **neighbors** on a circle
- Gradient descent without wraparound diverges
- Clustering algorithms fail near boundaries

### Geodesic Distance on T⁴

```python
def geodesic_distance_t4(point1, point2, weights=None):
    """
    Geodesic distance on T⁴ = S¹ × S¹ × S¹ × S¹
    """
    wrapped = []
    for i in range(4):
        d = wrapped_angle_distance(point1[i], point2[i])
        wrapped.append(d)

    return sqrt(sum(w * d² for w, d in zip(weights, wrapped)))
```

**Experimental result:** T⁴ chordal distance is **135% more discriminative** than Euclidean (expS5_001d).

### Topological Validation (H₁ Betti Number)

```python
def validate_topology(t4_coords):
    """
    T⁴ has exactly 4 non-contractible loops (H₁ = 4).
    If H₁ < 4, the manifold has collapsed.
    """
    result = ripser(t4_coords, maxdim=1)
    h1_count = count_significant_features(result['dgms'][1])
    return h1_count >= 4
```

**What H₁ = 4 means:**
- The 4-torus has 4 independent "holes"
- Each circle S¹ contributes one generator to H₁
- If data collapses to lower dimension, H₁ decreases

### Pipeline Coordinate Functions

| Pipeline | Dims | Coordinates | Tests |
|----------|------|-------------|-------|
| **P1: T⁴ Full** | 4 | (θ, φ, α, ω) | Full claim |
| **P2: T² Intrinsic** | 2 | (θ, φ) | Is 2-torus sufficient? |
| **P3: T³ + Domain** | 3 | (θ, φ, domain) | Hard boundaries |
| **P4: T⁴ Soft** | 4 | (θ, φ, α, ω) | Soft boundaries |

### Connection to Rotor

The rotor outputs (R, S, N). T⁴ coordinates are **derived**:

```
Embeddings → Rotor → (R, S, N) → compute_t4_coordinates → (θ, φ, α, ω)
```

### Summary Diagram

```
                        R, S, N (Simplex Δ²)
                              │
                              │ compute_t4_coordinates()
                              ▼
        ┌─────────────────────────────────────────────┐
        │                   T⁴                        │
        │                                             │
        │    simplex_θ ─────────── S¹ (position)      │
        │         │                                   │
        │    φ_simplex ─────────── S¹ (extremity)     │
        │         │                                   │
        │    α_t4 ──────────────── S¹ (quality)       │
        │         │                                   │
        │    ω_t4 ──────────────── S¹ (confidence)    │
        │                                             │
        └─────────────────────────────────────────────┘
                              │
                              │ geodesic_distance_t4()
                              ▼
                    Distance-preserving metric
                    for clustering, drift, stability
```

---

## Proofs

### Proof 1: Simplex Guarantee

**Theorem:** For all certification inputs, R + S + N = 1.0 (±1e-6) is guaranteed by construction.

**Proof:**
1. **Hash-based (Local):** R + S + N = (raw_r + raw_s + raw_n) / total = 1.0
2. **Rotor-based (Production):** Barycentric coordinates sum to 1 by definition
3. **API consistency:** All entry points share implementation

**Experimental verification:** Max deviation = 2.22e-16 (machine epsilon)

### Proof 2: Oobleck Dynamics

**Theorem:** κ_req(σ) = 0.5 + 0.4σ is the unique linear function satisfying baseline and maximum constraints.

**Proof:**
- Linear form: κ_req(σ) = a + bσ
- Condition 1: κ_req(0) = 0.5 → a = 0.5
- Condition 2: κ_req(1) = 0.9 → b = 0.4
- Uniquely determined: κ_req(σ) = 0.5 + 0.4σ

### Proof 3: Gate Order Security

**Theorem:** G₁ → G₂ → G₃ → G₄ is uniquely determined by RSCT semantics.

**Proof by partial order:**
- Lemma 1: G₁ < {G₂, G₃, G₄} (noise corrupts downstream)
- Lemma 2: G₂ < G₃ (consensus before compatibility)
- Lemma 3: G₃ < G₄ (global before local)
- Combined: G₁ < G₂ < G₃ < G₄ (total order)

---

## References

### Source Files

| File | Description |
|------|-------------|
| `yrsn/core/decomposition/hybrid_rotor.py` | HybridSimplexRotor implementation |
| `yrsn/core/geometric/primitives/rotor.py` | Lie algebra rotor layers |
| `yrsn/core/decomposition/geometric_utils.py` | T⁴ coordinate computations |
| `yrsn/core/enforcement/topology_cache.py` | H₁ Betti number validation |
| `swarm-it-adk/adk/swarm_it/local/engine.py` | LocalEngine certification |

### Experiments

| Experiment | Validates |
|------------|-----------|
| SWARM-01 | 8 hypotheses, all gates, simplex invariant |
| EXP-ROTOR-001 | Hybrid vs pure rotor performance |
| expS5_001d | T⁴ chordal distance (135% improvement) |

### Patent Sections

- §7.4: RSN Decomposition
- §7.6: Toroidal Geometric Mapping
- §7.6.2: Functional Requirements
- §7.6.3: Mathematical Foundation
- §7.6.4: Mapping Architectures

---

## Quick Reference

### Quality Tiers

| Badge | Condition | Symbol |
|-------|-----------|--------|
| Exceptional | κ ≥ 0.9 | 🥇 |
| High Quality | κ ≥ 0.8 | 🥈 |
| Certified | κ ≥ 0.7 | 🥉 |
| Pending | κ < 0.7 | ⏳ |

### Stability Tiers

| Tier | Condition |
|------|-----------|
| STABLE | σ < 0.3 |
| MODERATE | 0.3 ≤ σ < 0.7 |
| TURBULENT | σ ≥ 0.7 |

### Color Reference

| Color | Hex | Meaning |
|-------|-----|---------|
| Green | #2ECC71 | PASS / EXECUTE / Relevant |
| Red | #E74C3C | FAIL / REJECT / Noise |
| Orange | #F39C12 | Threshold / PARTIAL / Moderate |
| Blue | #3498DB | Support / Info / Minimal |
| Purple | #9B59B6 | Unknown / Special |
| Gray | #95A5A6 | Not tested / Neutral |

---

## RSCT vs MARL: The Anti-MARL Paradigm

RSCT is fundamentally **orthogonal to MARL** (Multi-Agent Reinforcement Learning) and serves as a corrective to its failure modes.

### Paradigm Contrast

| Aspect | MARL | RSCT |
|--------|------|------|
| **Core mechanism** | Learned rewards | Mathematical invariants |
| **Agent coordination** | Emergent from optimization | Certified handoffs |
| **Under stress** | Explore (can diverge) | Harden (Oobleck) |
| **Quality measure** | Cumulative reward | Simplex decomposition (R, S, N) |
| **Guarantees** | Probabilistic (convergence hopes) | Provable (by construction) |
| **Failure mode** | Reward hacking, instability | Gate rejection (explicit) |

### The Anti-MARL Properties

#### 1. No Learned Rewards

MARL agents optimize `max E[Σ r_t]` — rewards can be gamed, sparse, or misaligned.

RSCT doesn't use rewards. Quality is **decomposed geometrically**:
```
R + S + N = 1  (by construction, not learned)
```

#### 2. Hardening vs Exploration

MARL under stress: **increase exploration** (ε-greedy, entropy bonus)
→ Can lead to chaotic divergence

RSCT under stress: **increase threshold** (Oobleck)
```
κ_req(σ) = 0.5 + 0.4σ
```
→ Higher σ means stricter gating, not more exploration

#### 3. Certificate Chaining vs Negotiation

MARL: Agents negotiate/compete, emergent equilibria (Nash, etc.)
→ Equilibria can be suboptimal, unstable, or adversarial

RSCT: Agent A's certificate becomes Agent B's input constraint
```
κ_interface = compatibility(C_A.output, C_B.input) ≥ 0.5
```
→ No negotiation, just verification

#### 4. Deterministic Gating vs Stochastic Policies

MARL: π(a|s) is a probability distribution
→ Same state can yield different actions

RSCT: Gates are deterministic functions of (R, S, N, κ, σ)
→ Same certificate always yields same decision

#### 5. Topological Stability vs Reward Landscape

MARL: Reward landscape can have local minima, saddle points, deceptive gradients

RSCT: T⁴ topology is fixed, H₁ = 4 is invariant
→ No landscape to get stuck in

### MARL Failure Modes Prevented by RSCT

| MARL Failure | RSCT Prevention |
|--------------|-----------------|
| **Reward hacking** | No rewards to hack — simplex is geometric |
| **Specification gaming** | 4-gate pipeline catches semantic misalignment |
| **Catastrophic forgetting** | Low-rank rotors (RoRA) preserve structure |
| **Multi-agent instability** | κ_interface enforces compatibility at handoffs |
| **Exploration explosion** | Oobleck hardening under stress |
| **Mode collapse** | H₁ = 4 topology validation catches collapse |

### The Philosophical Shift

**MARL assumption:** Let agents learn optimal behavior through interaction

**MARL problem:** "Optimal" is defined by reward, which is often misspecified

**RSCT assumption:** Define quality mathematically, then verify agents meet it

**RSCT benefit:** No reward to misspecify — the simplex decomposition IS the definition

### When to Use Each

| Use Case | Approach |
|----------|----------|
| Game playing (known rules) | MARL works |
| Robotics (sim-to-real) | MARL + safety wrapper |
| LLM pipelines (production) | **RSCT** — need guarantees |
| Multi-agent content generation | **RSCT** — need quality control |
| Autonomous vehicles | Hybrid (RSCT for certification layer) |

### Summary

RSCT replaces "hope agents learn to cooperate" with "mathematically verify they're compatible."

It's not anti-learning — agents can still learn internally — but it's **anti-emergent-chaos**. The certification layer provides formal guarantees that MARL cannot offer by construction.

---

## Dimension Expansion for Rotor Capacity

### The κ Problem (Sudjianto, SSRN 6101568)

Rotors require sufficient "room to rotate" in the embedding space:

```
κ = dim / stable_rank(Cov)

κ < 50:  "rank-choked" — rotor can't find rotation plane
κ ≥ 50:  "room to rotate" — rotor can align subspaces
```

### The Fix (Adila et al., arXiv:2603.08647)

Function-preserving MLP dimension expansion:

```python
# Double MLP hidden dimension
W_up_new = [W_up | W_up]           # h × 2p (horizontal concat)
W_down_new = [W_down/2; W_down/2]  # 2p × h (vertical concat, scaled)

# Proof of function preservation:
# [Y Y] @ [W/2; W/2] = Y·W/2 + Y·W/2 = Y·W  ✓
```

### SWARM-02 Experimental Validation

| Hypothesis | Result | Evidence |
|------------|--------|----------|
| κ scales linearly with k | ✓ PASS | κ_new ≈ k × κ_old |
| Function preservation | ✓ PASS | MSE < 1e-10 |
| Accuracy improves when κ crosses 50 | ✓ PASS | +8.8% to +17.4% |
| Higher k always better | ✗ NUANCED | Sweet spot at κ ≈ 50-80 |

### Key Finding: Optimal Expansion

Over-expansion has diminishing returns:

```
κ_base = 16.4:
  k=2: accuracy=91.8% (+6.5%)  ← BEST
  k=3: accuracy=91.0% (+5.6%)
  k=4: accuracy=90.6% (+5.1%)
  k=5: accuracy=90.6% (+5.1%)
```

### Recommended Formula

```python
def optimal_expansion(kappa_current: float) -> int:
    """
    Compute expansion factor to reach rotor capacity sweet spot.

    Target: κ ≈ 65 (middle of 50-80 range)
    Cap: k ≤ 5 (diminishing returns beyond)
    """
    if kappa_current >= 50:
        return 1  # Already sufficient

    k = math.ceil(65 / kappa_current)
    return min(k, 5)
```

### Integration with HybridSimplexRotor

```python
def prepare_features_for_rotor(features: torch.Tensor) -> torch.Tensor:
    """Expand features if κ < 50 to enable rotor."""
    kappa = compute_kappa(features)

    if kappa < 50:
        k = optimal_expansion(kappa)
        features = torch.cat([features] * k, dim=1)

    return features
```

### References

- Adila et al. (2026). "Grow, Don't Overwrite." arXiv:2603.08647
- Sudjianto (2024). "RoRA: Low-Rank Rotational Adaptation." SSRN 6101568
- SWARM-02 Experiment: `experiments/SWARM-02/`
