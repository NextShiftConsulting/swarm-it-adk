"""
SWARM-02: Dimension Expansion for Rotor Capacity

Tests whether MLP dimension expansion (Adila et al., arXiv:2603.08647)
increases κ and enables rotors to work in rank-choked scenarios.

Usage:
    python -m experiments.SWARM-02.run_experiment
"""

import json
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Tuple, Dict, List, Optional

# Experiment paths
EXP_DIR = Path(__file__).parent
EVIDENCE_DIR = EXP_DIR / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)


# =============================================================================
# Core Functions from Papers
# =============================================================================

def compute_stable_rank(features: torch.Tensor) -> float:
    """
    Compute stable rank of feature covariance.

    stable_rank = trace(Cov) / max_eigenvalue(Cov)

    This measures the "effective dimensionality" of the data.
    """
    if features.dim() == 1:
        return 1.0

    # Center features
    centered = features - features.mean(dim=0)

    # Compute covariance
    cov = centered.T @ centered / (features.shape[0] - 1)

    # Eigenvalues
    eigenvalues = torch.linalg.eigvalsh(cov)
    eigenvalues = torch.clamp(eigenvalues, min=1e-10)

    # Stable rank
    stable_rank = eigenvalues.sum() / eigenvalues.max()

    return stable_rank.item()


def compute_kappa(features: torch.Tensor) -> float:
    """
    Compute over-parameterization ratio κ.

    κ = dim / stable_rank(Cov)

    Per Sudjianto (SSRN 6101568):
    - κ < 50: rank-choked (rotor can't work)
    - κ ≥ 50: room to rotate (rotor can align)
    """
    dim = features.shape[1]
    stable_rank = compute_stable_rank(features)
    return dim / stable_rank


def expand_mlp_weights(
    W_up: torch.Tensor,
    W_down: torch.Tensor,
    k: int = 2
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Expand MLP dimension by factor k (Adila et al., arXiv:2603.08647).

    W_up:   [h, p] -> [h, k*p]  (horizontal concat)
    W_down: [p, h] -> [k*p, h]  (vertical concat, scaled by 1/k)

    This is function-preserving:
        [Y Y ... Y] @ [W/k; W/k; ...; W/k] = Y @ W
    """
    # Expand up-projection (horizontal concat)
    W_up_expanded = torch.cat([W_up] * k, dim=1)

    # Expand down-projection (vertical concat with scaling)
    W_down_scaled = W_down / k
    W_down_expanded = torch.cat([W_down_scaled] * k, dim=0)

    return W_up_expanded, W_down_expanded


def verify_function_preservation(
    W_up: torch.Tensor,
    W_down: torch.Tensor,
    W_up_exp: torch.Tensor,
    W_down_exp: torch.Tensor,
    inputs: torch.Tensor,
    activation: str = "relu"
) -> Dict[str, float]:
    """
    Verify that expansion is function-preserving.

    Original: Y = act(X @ W_up) @ W_down
    Expanded: Y' = act(X @ W_up_exp) @ W_down_exp

    Should have: Y ≈ Y' (MSE < 1e-6)
    """
    # Apply activation
    if activation == "relu":
        act = torch.relu
    elif activation == "gelu":
        act = torch.nn.functional.gelu
    else:
        act = lambda x: x

    # Original output
    Y_orig = act(inputs @ W_up) @ W_down

    # Expanded output
    Y_exp = act(inputs @ W_up_exp) @ W_down_exp

    # Compute error
    mse = torch.mean((Y_orig - Y_exp) ** 2).item()
    max_diff = torch.max(torch.abs(Y_orig - Y_exp)).item()

    return {
        "mse": mse,
        "max_abs_diff": max_diff,
        "preserved": mse < 1e-6
    }


# =============================================================================
# Synthetic Data Generators
# =============================================================================

def generate_low_rank_embeddings(
    n_samples: int = 1000,
    dim: int = 64,
    intrinsic_rank: int = 5,
    noise: float = 0.01
) -> torch.Tensor:
    """
    Generate embeddings with controlled stable rank.

    Creates data that lies mostly in a low-dimensional subspace,
    simulating the "rank-choked" scenario.
    """
    # Low-rank structure
    U = torch.randn(n_samples, intrinsic_rank)
    V = torch.randn(intrinsic_rank, dim)

    # Base embeddings (low rank)
    embeddings = U @ V

    # Add small noise
    embeddings = embeddings + noise * torch.randn_like(embeddings)

    # Normalize
    embeddings = embeddings / embeddings.norm(dim=1, keepdim=True)

    return embeddings


def generate_high_rank_embeddings(
    n_samples: int = 1000,
    dim: int = 64
) -> torch.Tensor:
    """
    Generate embeddings with high stable rank.

    Creates data that uses most of the ambient dimension,
    simulating the "room to rotate" scenario.
    """
    embeddings = torch.randn(n_samples, dim)
    embeddings = embeddings / embeddings.norm(dim=1, keepdim=True)
    return embeddings


# =============================================================================
# Simple Rotor for Testing
# =============================================================================

class SimpleRotor(nn.Module):
    """
    Simplified rotor for testing κ effects.

    Uses low-rank parameterization per Sudjianto.
    """

    def __init__(self, dim: int, rank: int = 4):
        super().__init__()
        self.dim = dim
        self.rank = rank

        # Low-rank bivector: B = UV^T - VU^T
        self.U = nn.Parameter(torch.randn(dim, rank) * 0.01)
        self.V = nn.Parameter(torch.randn(dim, rank) * 0.01)

        # Output projection (to 3 for RSN)
        self.proj = nn.Linear(dim, 3)

    def get_rotation_matrix(self) -> torch.Tensor:
        """Compute R = exp(B) where B is skew-symmetric."""
        B = self.U @ self.V.T - self.V @ self.U.T
        return torch.matrix_exp(B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        R = self.get_rotation_matrix()
        rotated = x @ R.T
        logits = self.proj(rotated)
        return torch.softmax(logits, dim=-1)


def train_rotor(
    features: torch.Tensor,
    labels: torch.Tensor,
    epochs: int = 100,
    lr: float = 0.01
) -> Tuple[SimpleRotor, float]:
    """
    Train a simple rotor classifier.

    Returns trained rotor and final accuracy.
    """
    dim = features.shape[1]
    rotor = SimpleRotor(dim)

    optimizer = torch.optim.Adam(rotor.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    # Training loop
    for epoch in range(epochs):
        optimizer.zero_grad()
        outputs = rotor(features)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

    # Final accuracy
    with torch.no_grad():
        preds = rotor(features).argmax(dim=1)
        accuracy = (preds == labels).float().mean().item()

    return rotor, accuracy


# =============================================================================
# Hypothesis Tests
# =============================================================================

def test_h1_kappa_scaling() -> Dict:
    """
    H1: κ doubles with dimension expansion.

    Test that κ_new ≈ k × κ_original for various expansion factors.
    """
    results = {
        "hypothesis_id": "H1",
        "statement": "κ scales linearly with expansion factor k",
        "test_cases": []
    }

    # Test different intrinsic ranks
    for intrinsic_rank in [3, 5, 8, 12]:
        embeddings = generate_low_rank_embeddings(
            n_samples=500,
            dim=64,
            intrinsic_rank=intrinsic_rank
        )

        kappa_original = compute_kappa(embeddings)

        # Test expansion factors
        for k in [2, 3, 4]:
            # Expand by duplicating features (simulating expanded MLP output)
            expanded = torch.cat([embeddings] * k, dim=1)
            kappa_expanded = compute_kappa(expanded)

            kappa_ratio = kappa_expanded / kappa_original
            expected_ratio = float(k)

            results["test_cases"].append({
                "intrinsic_rank": intrinsic_rank,
                "expansion_factor": k,
                "kappa_original": round(kappa_original, 2),
                "kappa_expanded": round(kappa_expanded, 2),
                "kappa_ratio": round(kappa_ratio, 2),
                "expected_ratio": expected_ratio,
                "within_20pct": abs(kappa_ratio - expected_ratio) / expected_ratio < 0.2
            })

    # Aggregate
    passing = sum(1 for tc in results["test_cases"] if tc["within_20pct"])
    total = len(results["test_cases"])
    results["metric_value"] = passing / total
    results["supported"] = results["metric_value"] >= 0.9

    return results


def test_h2_threshold_crossing() -> Dict:
    """
    H2: Rank-choked scenarios (κ < 50) become viable (κ ≥ 50) after expansion.
    """
    results = {
        "hypothesis_id": "H2",
        "statement": "Expansion enables rank-choked scenarios to cross κ ≥ 50 threshold",
        "test_cases": []
    }

    # Create scenarios with κ < 50
    target_kappas = [20, 25, 30, 35, 40, 45]

    for target in target_kappas:
        # Find intrinsic_rank that gives approximately target κ
        # κ ≈ dim / stable_rank, stable_rank ≈ intrinsic_rank
        # So intrinsic_rank ≈ dim / target
        dim = 64
        intrinsic_rank = max(2, int(dim / target))

        embeddings = generate_low_rank_embeddings(
            n_samples=500,
            dim=dim,
            intrinsic_rank=intrinsic_rank
        )

        kappa_before = compute_kappa(embeddings)

        # Apply k=2 expansion
        expanded = torch.cat([embeddings, embeddings], dim=1)
        kappa_after = compute_kappa(expanded)

        results["test_cases"].append({
            "target_kappa": target,
            "intrinsic_rank": intrinsic_rank,
            "kappa_before": round(kappa_before, 2),
            "kappa_after": round(kappa_after, 2),
            "was_choked": kappa_before < 50,
            "now_viable": kappa_after >= 50,
            "threshold_crossed": kappa_before < 50 and kappa_after >= 50
        })

    # Count successful threshold crossings (for those that were choked)
    choked_cases = [tc for tc in results["test_cases"] if tc["was_choked"]]
    crossed = sum(1 for tc in choked_cases if tc["threshold_crossed"])

    results["metric_value"] = crossed / len(choked_cases) if choked_cases else 0
    results["supported"] = results["metric_value"] >= 0.8

    return results


def compute_required_k(kappa_current: float, kappa_target: float = 50.0) -> int:
    """Compute minimum expansion factor to reach target κ."""
    if kappa_current >= kappa_target:
        return 1
    import math
    return math.ceil(kappa_target / kappa_current)


def test_h3_rotor_accuracy() -> Dict:
    """
    H3: Rotor accuracy improves when κ crosses from <50 to ≥50.

    UPDATED: Now uses adaptive k to ensure κ ≥ 50.
    """
    results = {
        "hypothesis_id": "H3",
        "statement": "Rotor accuracy improves when κ crosses ≥50 threshold (adaptive k)",
        "test_cases": []
    }

    # Create classification task with structure
    n_samples = 500
    n_classes = 3

    # Test with different intrinsic ranks (severely choked scenarios)
    for intrinsic_rank in [3, 5, 8, 12]:
        # Generate low-rank embeddings (choked)
        embeddings_low = generate_low_rank_embeddings(
            n_samples=n_samples,
            dim=64,
            intrinsic_rank=intrinsic_rank,
            noise=0.05
        )

        # Create structured labels (based on first principal component)
        # This gives the rotor something meaningful to learn
        _, _, V = torch.linalg.svd(embeddings_low, full_matrices=False)
        pca_scores = embeddings_low @ V[0]  # Project onto first PC
        labels = torch.bucketize(pca_scores, torch.quantile(pca_scores, torch.linspace(0, 1, n_classes + 1)[1:-1]))

        # Train on original (choked)
        kappa_original = compute_kappa(embeddings_low)
        _, acc_original = train_rotor(embeddings_low, labels, epochs=100)

        # Compute required k to cross threshold
        k_required = compute_required_k(kappa_original, kappa_target=50.0)
        k_required = min(k_required, 5)  # Cap at 5x

        # Expand embeddings with required k
        embeddings_expanded = torch.cat([embeddings_low] * k_required, dim=1)
        kappa_expanded = compute_kappa(embeddings_expanded)

        # Train on expanded
        _, acc_expanded = train_rotor(embeddings_expanded, labels, epochs=100)

        improvement = (acc_expanded - acc_original) / acc_original if acc_original > 0 else 0

        results["test_cases"].append({
            "intrinsic_rank": intrinsic_rank,
            "k_used": k_required,
            "kappa_original": round(kappa_original, 2),
            "kappa_expanded": round(kappa_expanded, 2),
            "crossed_threshold": kappa_expanded >= 50,
            "accuracy_original": round(acc_original, 3),
            "accuracy_expanded": round(acc_expanded, 3),
            "improvement_pct": round(improvement * 100, 1),
            "improved": acc_expanded > acc_original
        })

    # Check: when κ crosses 50, does accuracy improve?
    crossed_cases = [tc for tc in results["test_cases"] if tc["crossed_threshold"]]
    improved_when_crossed = sum(1 for tc in crossed_cases if tc["improved"])

    results["metric_value"] = improved_when_crossed / len(crossed_cases) if crossed_cases else 0
    results["supported"] = results["metric_value"] >= 0.5  # At least half improve

    return results


def test_h3b_fixed_k_comparison() -> Dict:
    """
    H3b: Compare k=2, k=3, k=4 expansion factors directly.
    """
    results = {
        "hypothesis_id": "H3b",
        "statement": "Higher k enables better rotor performance for severely choked cases",
        "test_cases": []
    }

    n_samples = 500
    n_classes = 3

    for intrinsic_rank in [3, 4, 5]:
        embeddings = generate_low_rank_embeddings(
            n_samples=n_samples,
            dim=64,
            intrinsic_rank=intrinsic_rank,
            noise=0.05
        )

        # Structured labels (based on first PC)
        _, _, V = torch.linalg.svd(embeddings, full_matrices=False)
        pca_scores = embeddings @ V[0]
        labels = torch.bucketize(pca_scores, torch.quantile(pca_scores, torch.linspace(0, 1, n_classes + 1)[1:-1]))

        kappa_base = compute_kappa(embeddings)
        _, acc_base = train_rotor(embeddings, labels, epochs=100)

        test_case = {
            "intrinsic_rank": intrinsic_rank,
            "kappa_base": round(kappa_base, 2),
            "accuracy_base": round(acc_base, 3),
            "expansions": []
        }

        best_acc = acc_base
        best_k = 1

        for k in [2, 3, 4, 5]:
            expanded = torch.cat([embeddings] * k, dim=1)
            kappa_k = compute_kappa(expanded)
            _, acc_k = train_rotor(expanded, labels, epochs=100)

            test_case["expansions"].append({
                "k": k,
                "kappa": round(kappa_k, 2),
                "crossed_50": kappa_k >= 50,
                "accuracy": round(acc_k, 3),
                "improvement_vs_base": round((acc_k - acc_base) / acc_base * 100 if acc_base > 0 else 0, 1)
            })

            if acc_k > best_acc:
                best_acc = acc_k
                best_k = k

        test_case["best_k"] = best_k
        test_case["best_accuracy"] = round(best_acc, 3)
        test_case["improvement_with_best_k"] = round((best_acc - acc_base) / acc_base * 100 if acc_base > 0 else 0, 1)

        results["test_cases"].append(test_case)

    # Success if higher k consistently helps
    cases_where_expansion_helped = sum(1 for tc in results["test_cases"] if tc["best_k"] > 1)
    results["metric_value"] = cases_where_expansion_helped / len(results["test_cases"])
    results["supported"] = results["metric_value"] >= 0.5

    return results


def test_h4_function_preservation() -> Dict:
    """
    H4: Expansion is function-preserving (output identical at init).
    """
    results = {
        "hypothesis_id": "H4",
        "statement": "Model output identical (MSE < 1e-6) before/after expansion",
        "test_cases": []
    }

    # Test various dimensions
    for h, p in [(64, 256), (128, 512), (256, 1024)]:
        # Create MLP weights
        W_up = torch.randn(h, p) * 0.01
        W_down = torch.randn(p, h) * 0.01

        # Random input
        inputs = torch.randn(100, h)

        # Expand with k=2
        W_up_exp, W_down_exp = expand_mlp_weights(W_up, W_down, k=2)

        # Verify preservation
        verification = verify_function_preservation(
            W_up, W_down, W_up_exp, W_down_exp, inputs
        )

        results["test_cases"].append({
            "hidden_dim": h,
            "mlp_dim": p,
            "expanded_mlp_dim": p * 2,
            "mse": verification["mse"],
            "max_abs_diff": verification["max_abs_diff"],
            "preserved": verification["preserved"]
        })

    # All cases should preserve
    passing = sum(1 for tc in results["test_cases"] if tc["preserved"])
    results["metric_value"] = passing / len(results["test_cases"])
    results["supported"] = results["metric_value"] == 1.0

    return results


def test_h5_rsn_quality() -> Dict:
    """
    H5: RSN decomposition improves when κ ≥ 50.
    """
    results = {
        "hypothesis_id": "H5",
        "statement": "RSN correlation with ground truth improves when κ ≥ 50",
        "test_cases": []
    }

    for intrinsic_rank in [3, 5, 7]:
        n_samples = 500
        dim = 64

        # Generate embeddings
        embeddings_low = generate_low_rank_embeddings(
            n_samples=n_samples,
            dim=dim,
            intrinsic_rank=intrinsic_rank
        )

        # Create "ground truth" RSN based on embedding structure
        # R = signal alignment, S = redundancy, N = noise
        norms = embeddings_low.norm(dim=1)
        variance_per_dim = embeddings_low.var(dim=0).mean()

        # Synthetic ground truth
        R_true = torch.sigmoid(norms - norms.mean())
        N_true = 1 - R_true
        S_true = torch.zeros_like(R_true) + 0.1

        # Normalize to simplex
        total = R_true + S_true + N_true
        R_true /= total
        S_true /= total
        N_true /= total

        kappa_low = compute_kappa(embeddings_low)

        # Train rotor on low-κ
        rotor_low = SimpleRotor(dim)
        optimizer = torch.optim.Adam(rotor_low.parameters(), lr=0.01)
        for _ in range(50):
            optimizer.zero_grad()
            rsn_pred = rotor_low(embeddings_low)
            # Simple loss: match R component
            loss = ((rsn_pred[:, 0] - R_true) ** 2).mean()
            loss.backward()
            optimizer.step()

        with torch.no_grad():
            rsn_low = rotor_low(embeddings_low)
            corr_low = torch.corrcoef(torch.stack([rsn_low[:, 0], R_true]))[0, 1].item()

        # Expand and retrain
        embeddings_high = torch.cat([embeddings_low, embeddings_low], dim=1)
        kappa_high = compute_kappa(embeddings_high)

        rotor_high = SimpleRotor(dim * 2)
        optimizer = torch.optim.Adam(rotor_high.parameters(), lr=0.01)
        for _ in range(50):
            optimizer.zero_grad()
            rsn_pred = rotor_high(embeddings_high)
            loss = ((rsn_pred[:, 0] - R_true) ** 2).mean()
            loss.backward()
            optimizer.step()

        with torch.no_grad():
            rsn_high = rotor_high(embeddings_high)
            corr_high = torch.corrcoef(torch.stack([rsn_high[:, 0], R_true]))[0, 1].item()

        # Handle NaN correlations
        corr_low = 0.0 if np.isnan(corr_low) else corr_low
        corr_high = 0.0 if np.isnan(corr_high) else corr_high

        results["test_cases"].append({
            "intrinsic_rank": intrinsic_rank,
            "kappa_before": round(kappa_low, 2),
            "kappa_after": round(kappa_high, 2),
            "rsn_correlation_before": round(corr_low, 3),
            "rsn_correlation_after": round(corr_high, 3),
            "improvement": round(corr_high - corr_low, 3),
            "improved": corr_high > corr_low + 0.05
        })

    improved_count = sum(1 for tc in results["test_cases"] if tc["improved"])
    results["metric_value"] = improved_count / len(results["test_cases"])
    results["supported"] = improved_count >= 1

    return results


# =============================================================================
# Main Experiment Runner
# =============================================================================

def run_all_hypotheses() -> Dict:
    """Run all hypothesis tests and aggregate results."""
    print("\n" + "="*60)
    print("SWARM-02: Dimension Expansion for Rotor Capacity")
    print("="*60 + "\n")

    hypotheses = []

    # H1: κ scaling
    print("Testing H1: κ scales with expansion factor...")
    h1 = test_h1_kappa_scaling()
    hypotheses.append(h1)
    print(f"  Result: {'PASS' if h1['supported'] else 'FAIL'} ({h1['metric_value']:.0%})")

    # H2: Threshold crossing
    print("Testing H2: Rank-choked scenarios cross threshold...")
    h2 = test_h2_threshold_crossing()
    hypotheses.append(h2)
    print(f"  Result: {'PASS' if h2['supported'] else 'FAIL'} ({h2['metric_value']:.0%})")

    # H3: Rotor accuracy (adaptive k)
    print("Testing H3: Rotor accuracy with adaptive k...")
    h3 = test_h3_rotor_accuracy()
    hypotheses.append(h3)
    print(f"  Result: {'PASS' if h3['supported'] else 'FAIL'} ({h3['metric_value']:.0%})")

    # H3b: Fixed k comparison
    print("Testing H3b: Comparing k=2,3,4,5...")
    h3b = test_h3b_fixed_k_comparison()
    hypotheses.append(h3b)
    print(f"  Result: {'PASS' if h3b['supported'] else 'FAIL'} ({h3b['metric_value']:.0%})")

    # H4: Function preservation
    print("Testing H4: Function preservation...")
    h4 = test_h4_function_preservation()
    hypotheses.append(h4)
    print(f"  Result: {'PASS' if h4['supported'] else 'FAIL'} ({h4['metric_value']:.0%})")

    # H5: RSN quality
    print("Testing H5: RSN decomposition quality...")
    h5 = test_h5_rsn_quality()
    hypotheses.append(h5)
    print(f"  Result: {'PASS' if h5['supported'] else 'FAIL'} ({h5['metric_value']:.0%})")

    # Save individual evidence files
    for h in hypotheses:
        filename = f"h{h['hypothesis_id'][1]}_{'_'.join(h['statement'].split()[:3]).lower()}.json"
        with open(EVIDENCE_DIR / filename, "w") as f:
            json.dump(h, f, indent=2, default=str)

    # Aggregate results
    supported_count = sum(1 for h in hypotheses if h["supported"])

    master_evidence = {
        "experiment_id": "SWARM-02",
        "name": "Dimension Expansion for Rotor Capacity",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "reference": "arXiv:2603.08647",
        "metadata": {
            "hypotheses": [
                {
                    "hypothesis_id": h["hypothesis_id"],
                    "statement": h["statement"],
                    "supported": h["supported"],
                    "metric_value": h["metric_value"]
                }
                for h in hypotheses
            ],
            "supported_count": supported_count,
            "total_count": len(hypotheses)
        }
    }

    # Save master evidence
    with open(EVIDENCE_DIR / "swarm_evidence_SWARM-02.json", "w") as f:
        json.dump(master_evidence, f, indent=2)

    # Summary
    print("\n" + "="*60)
    print(f"SWARM-02 RESULTS: {supported_count}/{len(hypotheses)} hypotheses supported")
    print("="*60)

    for h in hypotheses:
        status = "✓ PASS" if h["supported"] else "✗ FAIL"
        print(f"  {h['hypothesis_id']}: {status} - {h['statement'][:50]}...")

    print(f"\nEvidence saved to: {EVIDENCE_DIR}")

    return master_evidence


if __name__ == "__main__":
    results = run_all_hypotheses()
