#!/usr/bin/env python3
"""
SWARM-06 H3: κ-Based Jailbreak Detection via Representation-Solver Compatibility

RSCT-correct approach: Measure compatibility with "Safe Interaction Solver" (S_safe).

Architecture:
    Text → SentenceTransformer (384d) → TextMLP (64d) → κ vs S_safe → Classification

Theory:
    κ(E, S) = D*/D (representation-solver compatibility)
    - HIGH κ: embedding compatible with safe solver → BENIGN
    - LOW κ: embedding incompatible with safe solver → JAILBREAK

Anti-MARL Defenses:
    - Geometry-based (not keyword-based)
    - Multi-signal fusion ready
    - Layered with RSN gates

Usage:
    python train_kappa_classifier.py
    python train_kappa_classifier.py --threshold 0.5

Reference: PROPOSAL_KAPPA_JAILBREAK_DETECTION.md
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import numpy as np

import torch
import torch.nn as nn

# Paths
EXPERIMENT_DIR = Path(__file__).parent.parent
DATA_DIR = EXPERIMENT_DIR / "data"
CHECKPOINTS_DIR = EXPERIMENT_DIR / "checkpoints"
EVIDENCE_DIR = EXPERIMENT_DIR / "evidence"

YRSN_SRC = Path("/Users/rudy/GitHub/yrsn/src")
YRSN_CHECKPOINTS = Path("/Users/rudy/GitHub/yrsn/checkpoints")

# Add YRSN paths
sys.path.insert(0, str(YRSN_SRC / "yrsn/adapters/models"))
sys.path.insert(0, str(YRSN_SRC / "yrsn/core/decomposition"))


class TextMLP384to64(nn.Module):
    """Text projection matching YRSN checkpoint architecture."""
    def __init__(self):
        super().__init__()
        self.alpha = nn.Parameter(torch.tensor(0.5))
        self.fc1 = nn.Linear(384, 192)
        self.ln1 = nn.LayerNorm(192)
        self.fc2 = nn.Linear(192, 128)
        self.ln2 = nn.LayerNorm(128)
        self.fc3 = nn.Linear(128, 64)
        self.skip = nn.Linear(384, 64)

    def forward(self, x):
        h = torch.relu(self.ln1(self.fc1(x)))
        h = torch.relu(self.ln2(self.fc2(h)))
        h = self.fc3(h)
        s = self.skip(x)
        return self.alpha * h + (1 - self.alpha) * s


class SafeSolverDistribution:
    """
    S_safe: Distribution of embeddings compatible with safe AI interaction.

    Built from benign exemplars, used to compute κ for new inputs.
    """

    def __init__(
        self,
        centroid: np.ndarray,
        covariance: np.ndarray,
        covariance_inv: np.ndarray,
        norm_mean: float,
        norm_std: float,
        n_samples: int,
    ):
        self.centroid = centroid
        self.covariance = covariance
        self.covariance_inv = covariance_inv
        self.norm_mean = norm_mean
        self.norm_std = norm_std
        self.n_samples = n_samples
        self.embed_dim = len(centroid)

    @classmethod
    def from_embeddings(cls, embeddings: np.ndarray) -> 'SafeSolverDistribution':
        """Build S_safe distribution from benign embeddings."""
        embeddings = np.asarray(embeddings)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        # Compute statistics
        centroid = embeddings.mean(axis=0)
        covariance = np.cov(embeddings.T)

        # Handle edge cases
        if covariance.ndim == 0:
            covariance = np.array([[covariance]])

        # Regularize for numerical stability
        covariance += np.eye(covariance.shape[0]) * 1e-6
        covariance_inv = np.linalg.inv(covariance)

        # Norm statistics
        norms = np.linalg.norm(embeddings, axis=1)

        return cls(
            centroid=centroid,
            covariance=covariance,
            covariance_inv=covariance_inv,
            norm_mean=float(norms.mean()),
            norm_std=float(norms.std()) + 1e-6,
            n_samples=embeddings.shape[0],
        )

    def compute_kappa(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Compute κ (compatibility) for embeddings.

        κ = geometric_mean(κ_mahalanobis, κ_norm)

        Args:
            embeddings: [N, embed_dim] or [embed_dim]

        Returns:
            κ values in [0, 1], shape [N] or scalar
        """
        embeddings = np.asarray(embeddings)
        single = embeddings.ndim == 1
        if single:
            embeddings = embeddings.reshape(1, -1)

        # κ₁: Mahalanobis-based compatibility
        # d² = (x - μ)ᵀ Σ⁻¹ (x - μ)
        diff = embeddings - self.centroid
        mahal_sq = np.sum(diff @ self.covariance_inv * diff, axis=1)

        # Convert to κ using exponential decay
        # Scale factor chosen so κ=0.5 at ~2 standard deviations
        scale = self.embed_dim  # Scale by dimensionality
        kappa_mahal = np.exp(-mahal_sq / (2 * scale))

        # κ₃: Norm consistency
        norms = np.linalg.norm(embeddings, axis=1)
        norm_diff = np.abs(norms - self.norm_mean)
        kappa_norm = np.exp(-norm_diff**2 / (2 * self.norm_std**2))

        # Combined κ: geometric mean
        kappa = np.sqrt(kappa_mahal * kappa_norm)

        # Clip to [0, 1]
        kappa = np.clip(kappa, 0, 1)

        return float(kappa[0]) if single else kappa

    def save(self, path: Path):
        """Save distribution to file."""
        np.savez(
            path,
            centroid=self.centroid,
            covariance=self.covariance,
            covariance_inv=self.covariance_inv,
            norm_mean=self.norm_mean,
            norm_std=self.norm_std,
            n_samples=self.n_samples,
        )

    @classmethod
    def load(cls, path: Path) -> 'SafeSolverDistribution':
        """Load distribution from file."""
        data = np.load(path)
        return cls(
            centroid=data['centroid'],
            covariance=data['covariance'],
            covariance_inv=data['covariance_inv'],
            norm_mean=float(data['norm_mean']),
            norm_std=float(data['norm_std']),
            n_samples=int(data['n_samples']),
        )


def load_data(split: str, max_samples: int = None) -> Tuple[List[str], List[bool]]:
    """Load data from unified dataset."""
    path = DATA_DIR / f"unified_{split}.jsonl"
    texts, labels = [], []
    with open(path) as f:
        for i, line in enumerate(f):
            if max_samples and i >= max_samples:
                break
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(row["is_jailbreak"])
    return texts, labels


def extract_embeddings(texts: List[str], extractor, batch_size: int = 32) -> np.ndarray:
    """Extract embeddings using SentenceTransformer."""
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        emb = extractor.extract(batch)
        embeddings.append(emb)
        if (i // batch_size) % 10 == 0:
            print(f"  Extracted {min(i+batch_size, len(texts))}/{len(texts)}")
    return np.vstack(embeddings)


def project_embeddings(
    embeddings: np.ndarray,
    projection: nn.Module,
    batch_size: int = 256,
) -> np.ndarray:
    """Project 384d embeddings to 64d using frozen TextMLP."""
    projection.eval()
    projected = []

    with torch.no_grad():
        for i in range(0, len(embeddings), batch_size):
            batch = torch.tensor(embeddings[i:i+batch_size], dtype=torch.float32)
            proj = projection(batch)
            projected.append(proj.numpy())

    return np.vstack(projected)


def optimize_threshold(
    kappa_values: np.ndarray,
    labels: np.ndarray,
    thresholds: np.ndarray = None,
) -> Tuple[float, Dict]:
    """
    Find optimal κ threshold for classification.

    LOW κ → jailbreak (positive class)
    HIGH κ → benign (negative class)

    Returns:
        best_threshold, best_metrics
    """
    if thresholds is None:
        thresholds = np.arange(0.1, 0.9, 0.05)

    best_f1 = 0
    best_threshold = 0.5
    best_metrics = {}

    for thresh in thresholds:
        # LOW κ = jailbreak
        predictions = kappa_values < thresh

        tp = np.sum(predictions & labels)
        tn = np.sum(~predictions & ~labels)
        fp = np.sum(predictions & ~labels)
        fn = np.sum(~predictions & labels)

        accuracy = (tp + tn) / len(labels)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        if f1 > best_f1:
            best_f1 = f1
            best_threshold = thresh
            best_metrics = {
                "threshold": float(thresh),
                "accuracy": float(accuracy),
                "precision": float(precision),
                "recall": float(recall),
                "f1_score": float(f1),
                "tp": int(tp),
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn),
            }

    return best_threshold, best_metrics


def evaluate(
    kappa_values: np.ndarray,
    labels: np.ndarray,
    threshold: float,
) -> Dict:
    """Evaluate κ-based classification at given threshold."""
    # LOW κ = jailbreak
    predictions = kappa_values < threshold

    tp = np.sum(predictions & labels)
    tn = np.sum(~predictions & ~labels)
    fp = np.sum(predictions & ~labels)
    fn = np.sum(~predictions & labels)

    accuracy = (tp + tn) / len(labels)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "fpr": float(fpr),
        "fnr": float(fnr),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }


def main():
    parser = argparse.ArgumentParser(description="κ-Based Jailbreak Detection")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Fixed threshold (if None, optimize on val set)")
    args = parser.parse_args()

    print("=" * 70)
    print("SWARM-06 H3: κ-BASED JAILBREAK DETECTION")
    print("=" * 70)
    print("\nRSCT Approach: Representation-Solver Compatibility")
    print("  - Build S_safe distribution from benign exemplars")
    print("  - Compute κ = compatibility with safe solver")
    print("  - LOW κ → jailbreak (incompatible)")
    print("  - HIGH κ → benign (compatible)")

    # Load text extractor
    print("\n[1/7] Loading text extractor...")
    from text_adapter import SentenceTransformerExtractor
    extractor = SentenceTransformerExtractor(model_name='all-MiniLM-L6-v2')
    print(f"  Loaded: {extractor.model_name} ({extractor.feature_dim}d)")

    # Load projection (frozen)
    print("\n[2/7] Loading projection model (FROZEN)...")
    projection = TextMLP384to64()
    proj_ckpt = YRSN_CHECKPOINTS / "text_mlp_384to64_trained.pt"
    if proj_ckpt.exists():
        ckpt = torch.load(proj_ckpt, map_location='cpu', weights_only=False)
        projection.load_state_dict(ckpt.get('model_state_dict', ckpt))
        print(f"  Loaded: {proj_ckpt.name}")
    projection.eval()
    for param in projection.parameters():
        param.requires_grad = False

    # Load data
    print("\n[3/7] Loading data...")
    train_texts, train_labels = load_data("train")
    val_texts, val_labels = load_data("val")
    test_texts, test_labels = load_data("test")

    train_labels = np.array(train_labels)
    val_labels = np.array(val_labels)
    test_labels = np.array(test_labels)

    n_benign_train = np.sum(~train_labels)
    n_jailbreak_train = np.sum(train_labels)
    print(f"  Train: {len(train_texts)} ({n_jailbreak_train} jailbreak, {n_benign_train} benign)")
    print(f"  Val:   {len(val_texts)} ({np.sum(val_labels)} jailbreak)")
    print(f"  Test:  {len(test_texts)} ({np.sum(test_labels)} jailbreak)")

    # Extract embeddings
    print("\n[4/7] Extracting embeddings...")
    print("  Training set:")
    train_emb_384 = extract_embeddings(train_texts, extractor)
    print("  Validation set:")
    val_emb_384 = extract_embeddings(val_texts, extractor)
    print("  Test set:")
    test_emb_384 = extract_embeddings(test_texts, extractor)

    # Project to 64d
    print("\n[5/7] Projecting to 64d...")
    train_emb_64 = project_embeddings(train_emb_384, projection)
    val_emb_64 = project_embeddings(val_emb_384, projection)
    test_emb_64 = project_embeddings(test_emb_384, projection)
    print(f"  Shape: {train_emb_64.shape}")

    # Build S_safe distribution from BENIGN training samples
    print("\n[6/7] Building S_safe distribution...")
    benign_mask = ~train_labels
    benign_embeddings = train_emb_64[benign_mask]
    print(f"  Benign samples: {len(benign_embeddings)}")

    s_safe = SafeSolverDistribution.from_embeddings(benign_embeddings)
    print(f"  Centroid norm: {np.linalg.norm(s_safe.centroid):.4f}")
    print(f"  Covariance trace: {np.trace(s_safe.covariance):.4f}")
    print(f"  Norm mean: {s_safe.norm_mean:.4f} ± {s_safe.norm_std:.4f}")

    # Save S_safe
    CHECKPOINTS_DIR.mkdir(exist_ok=True)
    s_safe_path = CHECKPOINTS_DIR / "s_safe_distribution.npz"
    s_safe.save(s_safe_path)
    print(f"  Saved: {s_safe_path}")

    # Compute κ for all sets
    print("\n[7/7] Computing κ values...")
    train_kappa = s_safe.compute_kappa(train_emb_64)
    val_kappa = s_safe.compute_kappa(val_emb_64)
    test_kappa = s_safe.compute_kappa(test_emb_64)

    # Analyze κ distribution by class
    print("\n  κ distribution:")
    print(f"  Train Jailbreak: κ = {train_kappa[train_labels].mean():.4f} ± {train_kappa[train_labels].std():.4f}")
    print(f"  Train Benign:    κ = {train_kappa[~train_labels].mean():.4f} ± {train_kappa[~train_labels].std():.4f}")
    print(f"  Val Jailbreak:   κ = {val_kappa[val_labels].mean():.4f} ± {val_kappa[val_labels].std():.4f}")
    print(f"  Val Benign:      κ = {val_kappa[~val_labels].mean():.4f} ± {val_kappa[~val_labels].std():.4f}")

    # Compute effect size (Cohen's d)
    jb_mean = val_kappa[val_labels].mean()
    jb_std = val_kappa[val_labels].std()
    bn_mean = val_kappa[~val_labels].mean()
    bn_std = val_kappa[~val_labels].std()
    pooled_std = np.sqrt((jb_std**2 + bn_std**2) / 2)
    cohens_d = (bn_mean - jb_mean) / pooled_std if pooled_std > 0 else 0
    print(f"\n  Cohen's d (separation): {cohens_d:.4f}")
    print(f"  Interpretation: {'Large' if abs(cohens_d) > 0.8 else 'Medium' if abs(cohens_d) > 0.5 else 'Small'} effect")

    # Optimize or use fixed threshold
    print("\n" + "=" * 70)
    print("THRESHOLD OPTIMIZATION")
    print("=" * 70)

    if args.threshold is not None:
        best_threshold = args.threshold
        print(f"\n  Using fixed threshold: {best_threshold}")
    else:
        print("\n  Optimizing threshold on validation set...")
        best_threshold, val_opt_metrics = optimize_threshold(val_kappa, val_labels)
        print(f"  Best threshold: {best_threshold:.4f}")
        print(f"  Val F1: {val_opt_metrics['f1_score']:.4f}")
        print(f"  Val Accuracy: {val_opt_metrics['accuracy']:.4f}")

    # Evaluate on all sets
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    train_results = evaluate(train_kappa, train_labels, best_threshold)
    val_results = evaluate(val_kappa, val_labels, best_threshold)
    test_results = evaluate(test_kappa, test_labels, best_threshold)

    print("\nTraining Set:")
    print(f"  Accuracy:  {train_results['accuracy']:.4f}")
    print(f"  F1 Score:  {train_results['f1_score']:.4f}")

    print("\nValidation Set:")
    print(f"  Accuracy:  {val_results['accuracy']:.4f}")
    print(f"  Precision: {val_results['precision']:.4f}")
    print(f"  Recall:    {val_results['recall']:.4f}")
    print(f"  F1 Score:  {val_results['f1_score']:.4f}")

    print("\nTest Set:")
    print(f"  Accuracy:  {test_results['accuracy']:.4f}")
    print(f"  Precision: {test_results['precision']:.4f}")
    print(f"  Recall:    {test_results['recall']:.4f}")
    print(f"  F1 Score:  {test_results['f1_score']:.4f}")
    print(f"  FPR:       {test_results['fpr']:.4f}")
    print(f"  FNR:       {test_results['fnr']:.4f}")

    # Save evidence
    EVIDENCE_DIR.mkdir(exist_ok=True)
    evidence = {
        "hypothesis": "H3",
        "method": "κ-based representation-solver compatibility",
        "statement": "κ-based classifier achieves >90% accuracy on jailbreak detection",
        "theory": {
            "principle": "RSCT κ = D*/D (representation-solver compatibility)",
            "s_safe": "Distribution of embeddings compatible with safe AI interaction",
            "classification": "LOW κ = incompatible = jailbreak, HIGH κ = compatible = benign",
        },
        "s_safe_stats": {
            "n_samples": int(s_safe.n_samples),
            "embed_dim": int(s_safe.embed_dim),
            "centroid_norm": float(np.linalg.norm(s_safe.centroid)),
            "norm_mean": float(s_safe.norm_mean),
            "norm_std": float(s_safe.norm_std),
        },
        "kappa_distribution": {
            "val_jailbreak_mean": float(val_kappa[val_labels].mean()),
            "val_jailbreak_std": float(val_kappa[val_labels].std()),
            "val_benign_mean": float(val_kappa[~val_labels].mean()),
            "val_benign_std": float(val_kappa[~val_labels].std()),
            "cohens_d": float(cohens_d),
        },
        "threshold": float(best_threshold),
        "train_results": train_results,
        "val_results": val_results,
        "test_results": test_results,
        "passed": test_results["accuracy"] > 0.90,
        "timestamp": datetime.now().isoformat(),
    }

    evidence_path = EVIDENCE_DIR / "h3_kappa_detection.json"
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)
    print(f"\nSaved evidence: {evidence_path}")

    # Summary
    print("\n" + "=" * 70)
    print("H3 SUMMARY")
    print("=" * 70)
    print("Target: Accuracy > 90%")
    print(f"Achieved (Test): Accuracy = {test_results['accuracy']:.1%}")
    print(f"Status: {'PASS' if test_results['accuracy'] > 0.90 else 'FAIL'}")
    print("\nMethod: κ-based representation-solver compatibility")
    print(f"Threshold: κ < {best_threshold:.4f} → jailbreak")
    print(f"Cohen's d: {cohens_d:.4f} ({'Large separation' if abs(cohens_d) > 0.8 else 'Needs improvement'})")


if __name__ == "__main__":
    main()
