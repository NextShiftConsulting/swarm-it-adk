# SWARM-01 Chart Explanation Guide

A walkthrough of each visualization in the SWARM-01 experiment dashboard.

---

## 1. Hypothesis Validation Bar Chart

**Purpose:** Shows pass/fail status for all 8 hypotheses tested.

**Reading the Chart:**
- **X-axis:** Hypothesis ID (H1-H8)
- **Y-axis:** Accuracy (0-100%)
- **Green bars:** PASS (≥90% accuracy)
- **Red bars:** FAIL (<90% accuracy)
- **Orange dashed line:** 90% threshold

**What Each Hypothesis Tests:**

| ID | Test | Threshold |
|----|------|-----------|
| H1 | Gate 1 Integrity | N ≥ 0.5 → REJECT |
| H2 | Gate 2 Consensus | c < 0.4 → BLOCK |
| H3 | Oobleck Formula | κ_req = 0.5 + 0.4σ |
| H4 | Landauer Tolerance | Gray zone ±0.05 |
| H5 | Gate 4 Grounding | κ_L < 0.3 → REPAIR |
| H6 | Simplex Constraint | R + S + N = 1.0 |
| H7 | API Consistency | All entry points identical |
| H8 | Multi-Agent Handoff | κ_interface ≥ 0.5 |

**Key Insight:** All bars at 100% indicates the certification system behaves exactly as theorized.

---

## 2. RSN Ternary Scatter Plot

**Purpose:** Visualizes the simplex decomposition R + S + N = 1 for all test cases.

**Reading the Chart:**
- **Triangle vertices:**
  - **R (Relevant):** Top-left, green - signal aligned with intent
  - **S (Support):** Top-right, blue - redundant/superfluous content
  - **N (Noise):** Bottom, red - irrelevant/harmful content
- **Point position:** Closer to a vertex = higher proportion of that component
- **Point color:** Prompt complexity level

**Complexity Colors:**
- 🔵 Minimal (simple prompts)
- 🟢 Low
- 🟡 Moderate
- 🟠 High
- 🔴 Extreme (edge cases, special chars)

**Key Insight:** Points clustered away from the N vertex indicate low-noise inputs that pass Gate 1.

---

## 3. κ vs σ Phase Diagram (Oobleck)

**Purpose:** Shows the dynamic threshold relationship between compatibility (κ) and turbulence (σ).

**Reading the Chart:**
- **X-axis:** σ (Turbulence) - system stress level [0, 1]
- **Y-axis:** κ (Compatibility) - certification threshold [0, 1]
- **Black curve:** Oobleck threshold κ_req = 0.5 + 0.4σ
- **Green region:** EXECUTE zone (above curve)
- **Orange region:** RE_ENCODE zone (below curve, above 0.3)
- **Red region:** BLOCK zone (below 0.3)

**Vertical Lines (Stability Tiers):**
- σ < 0.3: **STABLE** (green dotted)
- 0.3 ≤ σ < 0.7: **MODERATE**
- σ ≥ 0.7: **TURBULENT** (red dotted)

**The Oobleck Effect:**
Like the non-Newtonian fluid, the system "hardens under stress":
- Low stress (σ=0): κ_req = 0.5 (relaxed threshold)
- High stress (σ=1): κ_req = 0.9 (strict threshold)

**Key Insight:** Points in the green zone pass Gate 3. The curve shows why higher turbulence requires higher compatibility.

---

## 4. Noise Distribution Box Plot

**Purpose:** Shows how noise levels vary by prompt complexity.

**Reading the Chart:**
- **X-axis:** Complexity level
- **Y-axis:** Noise (N) value [0, 1]
- **Box:** Interquartile range (25th-75th percentile)
- **Line in box:** Median
- **Whiskers:** Min/max (excluding outliers)
- **Points:** Individual test cases
- **Red dashed line:** N = 0.5 (Gate 1 REJECT threshold)

**Expected Pattern:**
- Minimal/Low complexity: Lower noise
- High/Extreme complexity: Higher noise (but still below 0.5)

**Key Insight:** All points below the red line means all inputs passed Gate 1 (no false rejections).

---

## 5. Multi-Agent Handoff Chart

**Purpose:** Validates certificate chaining across agent pipelines.

**Reading the Chart:**
- **X-axis:** Chain length (number of agents in pipeline)
- **Y-axis:** κ_interface_min (weakest link compatibility)
- **Green bars:** Successful handoffs (κ_interface ≥ 0.5)
- **Red bars:** Failed handoffs (κ_interface < 0.5)
- **Orange dashed line:** 0.5 threshold

**What It Tests:**
When Agent A passes work to Agent B:
- A's output certificate becomes B's input
- κ_interface measures compatibility at the handoff point
- If κ_interface < 0.5, the chain breaks

**Key Insight:** All green bars indicate certificate chaining works correctly for pipelines of 2-5 agents.

---

## 6. Summary Stats Panel

**Purpose:** Quick reference for experiment status.

**Metrics Shown:**
- **Status:** Overall pass/fail
- **Hypotheses:** X/8 verified
- **Test Cases:** Number of prompts tested
- **Evidence Files:** JSON files generated
- **Proofs:** Mathematical proofs written

**Quality Tier Badge:**
- 🥇 Exceptional (κ ≥ 0.9)
- 🥈 High Quality (κ ≥ 0.8)
- 🥉 Certified (κ ≥ 0.7)
- ⏳ Pending (κ < 0.7)

---

## Chart Relationships

```
┌─────────────────┐     ┌─────────────────┐
│  RSN Ternary    │────▶│  N Distribution │
│  (R, S, N)      │     │  (Gate 1 check) │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  κ vs σ Phase   │────▶│  Hypothesis     │
│  (Gate 3 check) │     │  Validation     │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Multi-Agent    │
│  Handoff (H8)   │
└─────────────────┘
```

**Flow:**
1. RSN decomposition determines simplex position
2. N value checked against Gate 1 threshold
3. κ computed and checked against Oobleck curve (Gate 3)
4. For multi-agent: κ_interface checked at each handoff
5. All results aggregated in hypothesis validation

---

## Interactive Features (Plotly Dashboard)

- **Hover:** See exact values for any point
- **Zoom:** Click and drag to zoom into regions
- **Pan:** Shift + drag to move around
- **Download:** Camera icon saves PNG
- **Reset:** Home icon resets view

---

## Color Reference

| Color | Meaning |
|-------|---------|
| 🟢 Green (#2ECC71) | PASS / EXECUTE / Relevant |
| 🔴 Red (#E74C3C) | FAIL / REJECT / Noise |
| 🟡 Orange (#F39C12) | Threshold / PARTIAL / Moderate |
| 🔵 Blue (#3498DB) | Support / Info / Minimal |
| 🟣 Purple (#9B59B6) | Unknown / Special |
| ⚪ Gray (#95A5A6) | Not tested / Neutral |

---

## When to Use Each Chart

| Question | Chart to Check |
|----------|----------------|
| Did all hypotheses pass? | Hypothesis Validation |
| What's the RSN distribution? | RSN Ternary |
| Is the Oobleck formula working? | κ vs σ Phase |
| Are noisy inputs being rejected? | N Distribution |
| Does multi-agent work? | Handoff Chart |
| Quick status check? | Summary Stats |

---

Generated for SWARM-01 Experiment
