#!/usr/bin/env python3
"""
SWARM-06 H3: κ-Proxy v1 with Intent-Conditioned Safe Manifolds

REVISED per reviewer feedback:
- Intent-conditioned manifolds (not single centroid)
- κ_local (nearest intent) + κ_global (overall)
- σ (perturbation stability)
- 4-state classification: ADMISSIBLE, INCOMPATIBLE, UNCERTAIN, UNSAFE

Key insight: Low κ = incompatibility with modeled safe solver
(NOT automatic maliciousness - could be distributional mismatch)

Usage:
    python train_kappa_v1_intent_manifolds.py
    python train_kappa_v1_intent_manifolds.py --n-clusters 8

Reference: PROPOSAL_KAPPA_JAILBREAK_DETECTION_v2.md
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

import torch
import torch.nn as nn

# Paths
EXPERIMENT_DIR = Path(__file__).parent.parent
DATA_DIR = EXPERIMENT_DIR / "data"
CHECKPOINTS_DIR = EXPERIMENT_DIR / "checkpoints"
EVIDENCE_DIR = EXPERIMENT_DIR / "evidence"

YRSN_SRC = Path("/Users/rudy/GitHub/yrsn/src")
YRSN_CHECKPOINTS = Path("/Users/rudy/GitHub/yrsn/checkpoints")

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


class IntentManifold:
    """Single intent manifold (cluster of safe embeddings)."""

    def __init__(
        self,
        centroid: np.ndarray,
        covariance_inv: np.ndarray,
        scale: float,
        n_samples: int,
        intent_id: int,
    ):
        self.centroid = centroid
        self.covariance_inv = covariance_inv
        self.scale = scale
        self.n_samples = n_samples
        self.intent_id = intent_id

    @classmethod
    def from_embeddings(cls, embeddings: np.ndarray, intent_id: int) -> 'IntentManifold':
        """Build manifold from cluster embeddings."""
        centroid = embeddings.mean(axis=0)
        covariance = np.cov(embeddings.T)

        if covariance.ndim == 0:
            covariance = np.array([[covariance]])

        # Regularize
        covariance += np.eye(covariance.shape[0]) * 1e-4
        covariance_inv = np.linalg.inv(covariance)

        # Scale factor for Mahalanobis → κ conversion
        scale = embeddings.shape[1]  # embed_dim

        return cls(
            centroid=centroid,
            covariance_inv=covariance_inv,
            scale=scale,
            n_samples=embeddings.shape[0],
            intent_id=intent_id,
        )

    def compute_kappa(self, embeddings: np.ndarray) -> np.ndarray:
        """Compute κ (compatibility) for embeddings."""
        embeddings = np.asarray(embeddings)
        single = embeddings.ndim == 1
        if single:
            embeddings = embeddings.reshape(1, -1)

        diff = embeddings - self.centroid
        mahal_sq = np.sum(diff @ self.covariance_inv * diff, axis=1)
        kappa = np.exp(-mahal_sq / (2 * self.scale))
        kappa = np.clip(kappa, 0, 1)

        return float(kappa[0]) if single else kappa


class IntentConditionedSafeManifolds:
    """
    Collection of intent-conditioned safe manifolds.

    Each manifold represents a cluster of benign embeddings with similar "intent".
    """

    def __init__(self, manifolds: List[IntentManifold], global_manifold: IntentManifold):
        self.manifolds = manifolds
        self.global_manifold = global_manifold
        self.n_intents = len(manifolds)

    @classmethod
    def from_embeddings(
        cls,
        embeddings: np.ndarray,
        n_clusters: int = 5,
    ) -> 'IntentConditionedSafeManifolds':
        """Build intent manifolds by clustering benign embeddings."""
        print(f"  Clustering into {n_clusters} intent manifolds...")

        # K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        # Evaluate clustering quality
        if len(set(labels)) > 1:
            silhouette = silhouette_score(embeddings, labels)
            print(f"  Silhouette score: {silhouette:.4f}")

        # Build per-cluster manifolds
        manifolds = []
        for i in range(n_clusters):
            cluster_mask = labels == i
            cluster_emb = embeddings[cluster_mask]
            if len(cluster_emb) > 10:  # Minimum samples
                manifold = IntentManifold.from_embeddings(cluster_emb, intent_id=i)
                manifolds.append(manifold)
                print(f"    Intent {i}: {len(cluster_emb)} samples")

        # Build global manifold
        global_manifold = IntentManifold.from_embeddings(embeddings, intent_id=-1)

        return cls(manifolds, global_manifold)

    def compute_kappa_local(self, embeddings: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute κ_local (best matching intent manifold).

        Returns:
            kappa_local: Maximum κ across all intents
            best_intent: Index of best matching intent
        """
        embeddings = np.asarray(embeddings)
        single = embeddings.ndim == 1
        if single:
            embeddings = embeddings.reshape(1, -1)

        # Compute κ for each manifold
        kappa_all = np.stack([m.compute_kappa(embeddings) for m in self.manifolds], axis=1)

        # Best match
        kappa_local = kappa_all.max(axis=1)
        best_intent = kappa_all.argmax(axis=1)

        if single:
            return float(kappa_local[0]), int(best_intent[0])
        return kappa_local, best_intent

    def compute_kappa_global(self, embeddings: np.ndarray) -> np.ndarray:
        """Compute κ_global (overall safe distance)."""
        return self.global_manifold.compute_kappa(embeddings)

    def save(self, path: Path):
        """Save manifolds to file."""
        data = {
            "n_intents": self.n_intents,
            "global_centroid": self.global_manifold.centroid,
            "global_cov_inv": self.global_manifold.covariance_inv,
            "global_scale": self.global_manifold.scale,
            "global_n_samples": self.global_manifold.n_samples,
        }
        for i, m in enumerate(self.manifolds):
            data[f"intent_{i}_centroid"] = m.centroid
            data[f"intent_{i}_cov_inv"] = m.covariance_inv
            data[f"intent_{i}_scale"] = m.scale
            data[f"intent_{i}_n_samples"] = m.n_samples
        np.savez(path, **data)


def compute_sigma(
    embeddings: np.ndarray,
    manifolds: IntentConditionedSafeManifolds,
    noise_scale: float = 0.05,
    n_perturbations: int = 5,
) -> np.ndarray:
    """
    Compute σ (perturbation stability) via noise injection.

    σ = std(κ_local) under small perturbations

    High σ indicates brittle/adversarial geometry.
    """
    embeddings = np.asarray(embeddings)
    single = embeddings.ndim == 1
    if single:
        embeddings = embeddings.reshape(1, -1)

    sigmas = []
    for emb in embeddings:
        kappa_samples = []
        for _ in range(n_perturbations):
            # Add Gaussian noise (simulates paraphrase)
            noise = np.random.randn(*emb.shape) * noise_scale
            perturbed = emb + noise
            perturbed = perturbed / (np.linalg.norm(perturbed) + 1e-8) * np.linalg.norm(emb)
            kappa_local, _ = manifolds.compute_kappa_local(perturbed)
            kappa_samples.append(kappa_local)
        sigmas.append(np.std(kappa_samples))

    sigmas = np.array(sigmas)
    return float(sigmas[0]) if single else sigmas


def classify_4state(
    kappa_local: np.ndarray,
    kappa_global: np.ndarray,
    sigma: np.ndarray,
    theta_high: float = 0.6,
    theta_low: float = 0.3,
    sigma_thresh: float = 0.15,
) -> np.ndarray:
    """
    4-state classification: ADMISSIBLE, INCOMPATIBLE, UNCERTAIN, UNSAFE

    Rules:
    - ADMISSIBLE: κ_local > theta_high AND σ < sigma_thresh
    - UNSAFE: σ > sigma_thresh (brittle geometry)
    - INCOMPATIBLE: κ_local < theta_low
    - UNCERTAIN: otherwise
    """
    n = len(kappa_local)
    states = np.empty(n, dtype=object)

    for i in range(n):
        if sigma[i] > sigma_thresh:
            states[i] = "UNSAFE"
        elif kappa_local[i] < theta_low:
            states[i] = "INCOMPATIBLE"
        elif kappa_local[i] > theta_high and sigma[i] < sigma_thresh:
            states[i] = "ADMISSIBLE"
        else:
            states[i] = "UNCERTAIN"

    return states


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
    """Project 384d embeddings to 64d."""
    projection.eval()
    projected = []
    with torch.no_grad():
        for i in range(0, len(embeddings), batch_size):
            batch = torch.tensor(embeddings[i:i+batch_size], dtype=torch.float32)
            proj = projection(batch)
            projected.append(proj.numpy())
    return np.vstack(projected)


def evaluate_4state(
    states: np.ndarray,
    labels: np.ndarray,
) -> Dict:
    """
    Evaluate 4-state classification.

    Ground truth mapping:
    - Jailbreak → should be INCOMPATIBLE or UNSAFE
    - Benign → should be ADMISSIBLE (UNCERTAIN is acceptable)
    """
    # Binary mapping for metrics
    # Jailbreak = positive class
    # INCOMPATIBLE or UNSAFE → predicted positive
    pred_positive = (states == "INCOMPATIBLE") | (states == "UNSAFE")

    tp = np.sum(pred_positive & labels)
    tn = np.sum(~pred_positive & ~labels)
    fp = np.sum(pred_positive & ~labels)
    fn = np.sum(~pred_positive & labels)

    accuracy = (tp + tn) / len(labels)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # State distribution
    state_dist = {
        "ADMISSIBLE": int(np.sum(states == "ADMISSIBLE")),
        "INCOMPATIBLE": int(np.sum(states == "INCOMPATIBLE")),
        "UNCERTAIN": int(np.sum(states == "UNCERTAIN")),
        "UNSAFE": int(np.sum(states == "UNSAFE")),
    }

    # Per-class state distribution
    jb_states = {s: int(np.sum((states == s) & labels)) for s in state_dist}
    bn_states = {s: int(np.sum((states == s) & ~labels)) for s in state_dist}

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "state_distribution": state_dist,
        "jailbreak_states": jb_states,
        "benign_states": bn_states,
    }


def main():
    parser = argparse.ArgumentParser(description="κ-Proxy v1 with Intent Manifolds")
    parser.add_argument("--n-clusters", type=int, default=5, help="Number of intent clusters")
    parser.add_argument("--theta-high", type=float, default=0.6, help="ADMISSIBLE threshold")
    parser.add_argument("--theta-low", type=float, default=0.3, help="INCOMPATIBLE threshold")
    parser.add_argument("--sigma-thresh", type=float, default=0.15, help="UNSAFE σ threshold")
    args = parser.parse_args()

    print("=" * 70)
    print("SWARM-06 H3: κ-PROXY v1 WITH INTENT-CONDITIONED MANIFOLDS")
    print("=" * 70)
    print("\nRevised approach per reviewer feedback:")
    print("  - Intent-conditioned manifolds (not single centroid)")
    print("  - κ_local (nearest intent) + κ_global (overall)")
    print("  - σ (perturbation stability)")
    print("  - 4-state: ADMISSIBLE, INCOMPATIBLE, UNCERTAIN, UNSAFE")

    # Load models
    print("\n[1/8] Loading text extractor...")
    from text_adapter import SentenceTransformerExtractor
    extractor = SentenceTransformerExtractor(model_name='all-MiniLM-L6-v2')
    print(f"  Loaded: {extractor.model_name}")

    print("\n[2/8] Loading projection model...")
    projection = TextMLP384to64()
    proj_ckpt = YRSN_CHECKPOINTS / "text_mlp_384to64_trained.pt"
    if proj_ckpt.exists():
        ckpt = torch.load(proj_ckpt, map_location='cpu', weights_only=False)
        projection.load_state_dict(ckpt.get('model_state_dict', ckpt))
    projection.eval()

    # Load data
    print("\n[3/8] Loading data...")
    train_texts, train_labels = load_data("train")
    val_texts, val_labels = load_data("val")
    test_texts, test_labels = load_data("test")
    train_labels = np.array(train_labels)
    val_labels = np.array(val_labels)
    test_labels = np.array(test_labels)
    print(f"  Train: {len(train_texts)} ({np.sum(train_labels)} jailbreak)")
    print(f"  Val:   {len(val_texts)} ({np.sum(val_labels)} jailbreak)")
    print(f"  Test:  {len(test_texts)} ({np.sum(test_labels)} jailbreak)")

    # Extract and project
    print("\n[4/8] Extracting embeddings...")
    print("  Training:")
    train_emb = project_embeddings(extract_embeddings(train_texts, extractor), projection)
    print("  Validation:")
    val_emb = project_embeddings(extract_embeddings(val_texts, extractor), projection)
    print("  Test:")
    test_emb = project_embeddings(extract_embeddings(test_texts, extractor), projection)

    # Build intent manifolds from benign
    print("\n[5/8] Building intent-conditioned manifolds...")
    benign_emb = train_emb[~train_labels]
    manifolds = IntentConditionedSafeManifolds.from_embeddings(
        benign_emb, n_clusters=args.n_clusters
    )

    CHECKPOINTS_DIR.mkdir(exist_ok=True)
    manifolds.save(CHECKPOINTS_DIR / "intent_manifolds.npz")
    print(f"  Saved: {CHECKPOINTS_DIR / 'intent_manifolds.npz'}")

    # Compute κ values
    print("\n[6/8] Computing κ_local, κ_global, σ...")
    print("  Validation set:")
    val_kappa_local, val_best_intent = manifolds.compute_kappa_local(val_emb)
    val_kappa_global = manifolds.compute_kappa_global(val_emb)
    print("  Computing σ (this may take a moment)...")
    val_sigma = compute_sigma(val_emb, manifolds)

    print("  Test set:")
    test_kappa_local, test_best_intent = manifolds.compute_kappa_local(test_emb)
    test_kappa_global = manifolds.compute_kappa_global(test_emb)
    print("  Computing σ...")
    test_sigma = compute_sigma(test_emb, manifolds)

    # Analyze distributions
    print("\n  κ_local distribution:")
    print(f"  Val Jailbreak: κ = {val_kappa_local[val_labels].mean():.4f} ± {val_kappa_local[val_labels].std():.4f}")
    print(f"  Val Benign:    κ = {val_kappa_local[~val_labels].mean():.4f} ± {val_kappa_local[~val_labels].std():.4f}")

    print("\n  σ distribution:")
    print(f"  Val Jailbreak: σ = {val_sigma[val_labels].mean():.4f} ± {val_sigma[val_labels].std():.4f}")
    print(f"  Val Benign:    σ = {val_sigma[~val_labels].mean():.4f} ± {val_sigma[~val_labels].std():.4f}")

    # Cohen's d for κ_local
    jb_mean, jb_std = val_kappa_local[val_labels].mean(), val_kappa_local[val_labels].std()
    bn_mean, bn_std = val_kappa_local[~val_labels].mean(), val_kappa_local[~val_labels].std()
    pooled_std = np.sqrt((jb_std**2 + bn_std**2) / 2)
    cohens_d = (bn_mean - jb_mean) / pooled_std if pooled_std > 0 else 0
    print(f"\n  Cohen's d (κ_local separation): {cohens_d:.4f}")

    # 4-state classification
    print("\n[7/8] 4-state classification...")
    val_states = classify_4state(
        val_kappa_local, val_kappa_global, val_sigma,
        theta_high=args.theta_high, theta_low=args.theta_low,
        sigma_thresh=args.sigma_thresh,
    )
    test_states = classify_4state(
        test_kappa_local, test_kappa_global, test_sigma,
        theta_high=args.theta_high, theta_low=args.theta_low,
        sigma_thresh=args.sigma_thresh,
    )

    # Evaluate
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    val_results = evaluate_4state(val_states, val_labels)
    test_results = evaluate_4state(test_states, test_labels)

    print("\nValidation Set:")
    print(f"  Accuracy:  {val_results['accuracy']:.4f}")
    print(f"  Precision: {val_results['precision']:.4f}")
    print(f"  Recall:    {val_results['recall']:.4f}")
    print(f"  F1 Score:  {val_results['f1_score']:.4f}")
    print(f"\n  State distribution: {val_results['state_distribution']}")
    print(f"  Jailbreak states:   {val_results['jailbreak_states']}")
    print(f"  Benign states:      {val_results['benign_states']}")

    print("\nTest Set:")
    print(f"  Accuracy:  {test_results['accuracy']:.4f}")
    print(f"  Precision: {test_results['precision']:.4f}")
    print(f"  Recall:    {test_results['recall']:.4f}")
    print(f"  F1 Score:  {test_results['f1_score']:.4f}")
    print(f"\n  State distribution: {test_results['state_distribution']}")
    print(f"  Jailbreak states:   {test_results['jailbreak_states']}")
    print(f"  Benign states:      {test_results['benign_states']}")

    # Save evidence
    EVIDENCE_DIR.mkdir(exist_ok=True)
    evidence = {
        "hypothesis": "H3",
        "method": "κ-proxy v1 with intent-conditioned manifolds",
        "version": "v1 (revised per reviewer feedback)",
        "config": {
            "n_clusters": args.n_clusters,
            "theta_high": args.theta_high,
            "theta_low": args.theta_low,
            "sigma_thresh": args.sigma_thresh,
        },
        "kappa_distribution": {
            "val_jailbreak_mean": float(val_kappa_local[val_labels].mean()),
            "val_benign_mean": float(val_kappa_local[~val_labels].mean()),
            "cohens_d": float(cohens_d),
        },
        "sigma_distribution": {
            "val_jailbreak_mean": float(val_sigma[val_labels].mean()),
            "val_benign_mean": float(val_sigma[~val_labels].mean()),
        },
        "val_results": val_results,
        "test_results": test_results,
        "passed": test_results["accuracy"] > 0.85,  # Revised target
        "timestamp": datetime.now().isoformat(),
    }

    evidence_path = EVIDENCE_DIR / "h3_kappa_v1_intent_manifolds.json"
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)
    print(f"\nSaved evidence: {evidence_path}")

    # Summary
    print("\n" + "=" * 70)
    print("H3 SUMMARY (κ-Proxy v1)")
    print("=" * 70)
    print("Target: Accuracy > 85% (revised)")
    print(f"Achieved (Test): Accuracy = {test_results['accuracy']:.1%}")
    print(f"Status: {'PASS' if test_results['accuracy'] > 0.85 else 'NEEDS FURTHER WORK'}")
    print(f"\nMethod: Intent-conditioned safe manifolds ({args.n_clusters} intents)")
    print(f"Cohen's d: {cohens_d:.4f}")
    print("4-state classification with σ-based UNSAFE detection")


if __name__ == "__main__":
    main()
