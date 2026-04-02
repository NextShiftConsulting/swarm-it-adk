#!/usr/bin/env python3
"""
SWARM-06 H3: Certificate-Feature Classifier for Jailbreak Detection

RSCT-correct approach: Keep rotor geometry intact, train classifier on certificate features.

Architecture:
    Text → SentenceTransformer (384d) → TextMLP (64d) → HybridSimplexRotor → RSN
                                                                              ↓
                                                              compute_certificate_features()
                                                                              ↓
                                                                    CertificateClassifier
                                                                              ↓
                                                                     is_jailbreak (0/1)

The rotor is FROZEN - it decomposes geometry, the classifier decides.

Features used:
- RSN: R, S, N (3 features)
- T4: simplex_theta, phi_simplex, alpha_t4, omega_t4 (4 features, normalized)
- Certificate: alpha_omega, health_score, entropy (3 features)
- Derived: S-R (manipulation signal), N/R ratio (1 feature)

Total: 12 features → MLP → binary classification

Usage:
    python train_certificate_classifier.py --epochs 100 --lr 1e-3
    python train_certificate_classifier.py --model logistic  # Simple baseline

Reference: DOE_SWARM-06_Jailbreak_Detection_Benchmark.md (H3)
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
from torch.utils.data import DataLoader, TensorDataset
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

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
sys.path.insert(0, str(YRSN_SRC / "yrsn/core/certificates"))


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


class CertificateFeatureClassifier(nn.Module):
    """
    MLP classifier on certificate features.

    Input: 12 certificate features
    Output: Binary (jailbreak probability)
    """
    def __init__(self, input_dim: int = 12, hidden_dims: List[int] = [64, 32]):
        super().__init__()

        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.2),
            ])
            prev_dim = hidden_dim

        layers.append(nn.Linear(prev_dim, 1))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x).squeeze(-1)


def load_training_data(split: str = "train", max_samples: int = None) -> Tuple[List[str], List[bool]]:
    """Load training data."""
    path = DATA_DIR / f"unified_{split}.jsonl"
    texts = []
    labels = []
    with open(path) as f:
        for i, line in enumerate(f):
            if max_samples and i >= max_samples:
                break
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(row["is_jailbreak"])
    return texts, labels


def extract_embeddings(texts: List[str], extractor, batch_size: int = 32) -> np.ndarray:
    """Extract embeddings for all texts."""
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        emb = extractor.extract(batch)
        embeddings.append(emb)
        if (i // batch_size) % 10 == 0:
            print(f"  Extracted {min(i+batch_size, len(texts))}/{len(texts)}")
    return np.vstack(embeddings)


def extract_rsn(
    embeddings: torch.Tensor,
    projection: nn.Module,
    rotor: nn.Module,
    device: str = 'cpu',
    batch_size: int = 256,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract RSN from embeddings using frozen rotor.

    Returns:
        R, S, N arrays
    """
    projection.eval()
    rotor.eval()

    R_all, S_all, N_all = [], [], []

    with torch.no_grad():
        for i in range(0, len(embeddings), batch_size):
            batch = embeddings[i:i+batch_size].to(device)
            emb_64 = projection(batch)
            rsn_out = rotor(emb_64)

            R_all.append(rsn_out['R'].cpu().numpy())
            S_all.append(rsn_out['S'].cpu().numpy())
            N_all.append(rsn_out['N'].cpu().numpy())

    return np.concatenate(R_all), np.concatenate(S_all), np.concatenate(N_all)


def compute_certificate_features(R: np.ndarray, S: np.ndarray, N: np.ndarray) -> np.ndarray:
    """
    Compute full certificate feature vector from RSN.

    Features (12 total):
    0-2: R, S, N (raw simplex)
    3-6: T4 coordinates (normalized to [0,1])
    7: alpha_omega (quality blend)
    8: health_score (1-N)
    9: entropy (-sum p*log(p))
    10: S-R (manipulation signal)
    11: N/(R+0.1) (noise ratio)
    """
    from geometric_utils import compute_t4_coordinates

    n_samples = len(R)
    features = np.zeros((n_samples, 12), dtype=np.float32)

    # Raw RSN (0-2)
    features[:, 0] = R
    features[:, 1] = S
    features[:, 2] = N

    # T4 coordinates (3-6), normalized
    t4 = compute_t4_coordinates(R, S, N)
    features[:, 3] = t4["simplex_theta"] / 360.0  # [0, 1)
    features[:, 4] = t4["phi_simplex"] / 360.0    # [0, 1)
    alpha_t4 = t4.get("alpha_t4", t4.get("alpha", np.zeros(n_samples)))
    omega_t4 = t4.get("omega_t4", t4.get("omega", np.zeros(n_samples)))
    features[:, 5] = alpha_t4 / 180.0             # [0, 1)
    features[:, 6] = omega_t4 / 90.0              # [0, 1]

    # alpha_omega (7) - P14 formula
    omega = np.clip(R * 1.5 - S * 0.5, 0.1, 0.99)
    alpha = R  # alpha = R on normalized simplex
    features[:, 7] = omega * alpha + (1 - omega) * 0.5

    # health_score (8)
    features[:, 8] = 1 - N

    # entropy (9) - RSN distribution entropy
    probs = np.stack([R, S, N], axis=-1)
    probs = np.clip(probs, 1e-10, 1.0)
    entropy = -np.sum(probs * np.log(probs), axis=-1)
    features[:, 9] = entropy / np.log(3)  # Normalize by max entropy

    # S-R manipulation signal (10)
    features[:, 10] = S - R

    # N/(R+0.1) noise ratio (11)
    features[:, 11] = N / (R + 0.1)

    return features


def train_sklearn_classifier(
    train_features: np.ndarray,
    train_labels: np.ndarray,
    val_features: np.ndarray,
    val_labels: np.ndarray,
    model_type: str = "logistic",
) -> Tuple[object, Dict]:
    """Train sklearn classifier on certificate features."""

    # Standardize features
    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(train_features)
    val_scaled = scaler.transform(val_features)

    # Select model
    if model_type == "logistic":
        model = LogisticRegression(max_iter=1000, C=1.0, class_weight='balanced')
    elif model_type == "rf":
        model = RandomForestClassifier(n_estimators=100, max_depth=10, class_weight='balanced')
    elif model_type == "gbm":
        model = GradientBoostingClassifier(n_estimators=100, max_depth=5, learning_rate=0.1)
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Train
    model.fit(train_scaled, train_labels)

    # Evaluate
    val_preds = model.predict(val_scaled)

    results = {
        "accuracy": float(accuracy_score(val_labels, val_preds)),
        "precision": float(precision_score(val_labels, val_preds)),
        "recall": float(recall_score(val_labels, val_preds)),
        "f1_score": float(f1_score(val_labels, val_preds)),
        "model_type": model_type,
    }

    # Feature importance (if available)
    if hasattr(model, 'coef_'):
        feature_names = ["R", "S", "N", "theta_t4", "phi_t4", "alpha_t4", "omega_t4",
                        "alpha_omega", "health", "entropy", "S-R", "N/R"]
        importance = np.abs(model.coef_[0])
        results["feature_importance"] = {
            name: float(imp) for name, imp in zip(feature_names, importance)
        }
    elif hasattr(model, 'feature_importances_'):
        feature_names = ["R", "S", "N", "theta_t4", "phi_t4", "alpha_t4", "omega_t4",
                        "alpha_omega", "health", "entropy", "S-R", "N/R"]
        results["feature_importance"] = {
            name: float(imp) for name, imp in zip(feature_names, model.feature_importances_)
        }

    return (model, scaler), results


def train_mlp_classifier(
    train_features: torch.Tensor,
    train_labels: torch.Tensor,
    val_features: torch.Tensor,
    val_labels: torch.Tensor,
    epochs: int = 100,
    lr: float = 1e-3,
    batch_size: int = 64,
    device: str = 'cpu',
) -> Tuple[nn.Module, Dict]:
    """Train MLP classifier on certificate features."""

    # Standardize features
    mean = train_features.mean(dim=0)
    std = train_features.std(dim=0) + 1e-8
    train_norm = (train_features - mean) / std
    val_norm = (val_features - mean) / std

    # Create model
    classifier = CertificateFeatureClassifier(input_dim=12, hidden_dims=[64, 32])
    classifier = classifier.to(device)

    # Dataset
    dataset = TensorDataset(train_norm.to(device), train_labels.float().to(device))
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Optimizer with weight decay
    optimizer = torch.optim.AdamW(classifier.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    # Class weights for imbalanced data
    pos_weight = (train_labels == 0).sum() / (train_labels == 1).sum()
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight).to(device))

    history = {"loss": [], "accuracy": [], "f1": []}

    for epoch in range(epochs):
        classifier.train()
        epoch_loss = 0

        for batch_features, batch_labels in loader:
            optimizer.zero_grad()
            logits = classifier(batch_features)
            loss = criterion(logits, batch_labels)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(batch_features)

        scheduler.step()

        # Evaluate
        classifier.eval()
        with torch.no_grad():
            val_logits = classifier(val_norm.to(device))
            val_preds = (torch.sigmoid(val_logits) > 0.5).cpu().numpy()

        val_labels_np = val_labels.numpy()
        accuracy = accuracy_score(val_labels_np, val_preds)
        f1 = f1_score(val_labels_np, val_preds)

        history["loss"].append(epoch_loss / len(dataset))
        history["accuracy"].append(accuracy)
        history["f1"].append(f1)

        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}/{epochs}: loss={epoch_loss/len(dataset):.4f}, "
                  f"acc={accuracy:.4f}, f1={f1:.4f}")

    # Final evaluation
    classifier.eval()
    with torch.no_grad():
        val_logits = classifier(val_norm.to(device))
        val_preds = (torch.sigmoid(val_logits) > 0.5).cpu().numpy()

    val_labels_np = val_labels.numpy()

    results = {
        "accuracy": float(accuracy_score(val_labels_np, val_preds)),
        "precision": float(precision_score(val_labels_np, val_preds)),
        "recall": float(recall_score(val_labels_np, val_preds)),
        "f1_score": float(f1_score(val_labels_np, val_preds)),
        "model_type": "mlp",
        "history": history,
        "normalization": {"mean": mean.tolist(), "std": std.tolist()},
    }

    return classifier, results


def main():
    parser = argparse.ArgumentParser(description="Train Certificate Feature Classifier")
    parser.add_argument("--model", type=str, default="mlp",
                        choices=["mlp", "logistic", "rf", "gbm"],
                        help="Classifier type")
    parser.add_argument("--epochs", type=int, default=100, help="MLP epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="MLP learning rate")
    parser.add_argument("--train-size", type=int, default=None, help="Max training samples")
    parser.add_argument("--device", type=str, default="cpu", help="Device")
    args = parser.parse_args()

    print("=" * 70)
    print("SWARM-06 H3: CERTIFICATE FEATURE CLASSIFIER")
    print("=" * 70)
    print("\nRSCT-correct approach:")
    print("  - Rotor FROZEN (preserves geometric semantics)")
    print("  - Classifier trained on 12 certificate features:")
    print("    [R, S, N, theta_t4, phi_t4, alpha_t4, omega_t4,")
    print("     alpha_omega, health, entropy, S-R, N/R]")

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

    # Load rotor (frozen)
    print("\n[3/7] Loading rotor (FROZEN)...")
    from hybrid_rotor import HybridSimplexRotor
    rotor = HybridSimplexRotor(embed_dim=64, subspace_dim=64, hidden_dim=256)
    rotor_ckpt = YRSN_CHECKPOINTS / "trained_rotor_text64.pt"
    if rotor_ckpt.exists():
        ckpt = torch.load(rotor_ckpt, map_location='cpu', weights_only=False)
        rotor.load_state_dict(ckpt.get('model_state_dict', ckpt))
        print(f"  Loaded: {rotor_ckpt.name}")
    rotor.eval()
    for param in rotor.parameters():
        param.requires_grad = False
    print(f"  Rotor parameters: {sum(p.numel() for p in rotor.parameters()):,} (frozen)")

    # Load training data
    print("\n[4/7] Loading training data...")
    train_texts, train_labels = load_training_data("train", max_samples=args.train_size)
    val_texts, val_labels = load_training_data("val")
    test_texts, test_labels = load_training_data("test")
    print(f"  Train: {len(train_texts)} samples ({sum(train_labels)} jailbreak)")
    print(f"  Val:   {len(val_texts)} samples ({sum(val_labels)} jailbreak)")
    print(f"  Test:  {len(test_texts)} samples ({sum(test_labels)} jailbreak)")

    # Extract embeddings
    print("\n[5/7] Extracting embeddings...")
    print("  Training set:")
    train_emb = torch.tensor(extract_embeddings(train_texts, extractor), dtype=torch.float32)
    print("  Validation set:")
    val_emb = torch.tensor(extract_embeddings(val_texts, extractor), dtype=torch.float32)
    print("  Test set:")
    test_emb = torch.tensor(extract_embeddings(test_texts, extractor), dtype=torch.float32)

    # Extract RSN using frozen rotor
    print("\n[6/7] Extracting RSN (frozen rotor)...")
    print("  Training set:")
    train_R, train_S, train_N = extract_rsn(train_emb, projection, rotor, args.device)
    print(f"    R: {train_R.mean():.3f}±{train_R.std():.3f}")
    print(f"    S: {train_S.mean():.3f}±{train_S.std():.3f}")
    print(f"    N: {train_N.mean():.3f}±{train_N.std():.3f}")

    print("  Validation set:")
    val_R, val_S, val_N = extract_rsn(val_emb, projection, rotor, args.device)

    print("  Test set:")
    test_R, test_S, test_N = extract_rsn(test_emb, projection, rotor, args.device)

    # Compute certificate features
    print("\n  Computing certificate features...")
    train_features = compute_certificate_features(train_R, train_S, train_N)
    val_features = compute_certificate_features(val_R, val_S, val_N)
    test_features = compute_certificate_features(test_R, test_S, test_N)
    print(f"  Feature shape: {train_features.shape}")

    # Train classifier
    print(f"\n[7/7] Training {args.model.upper()} classifier...")

    train_labels_arr = np.array(train_labels)
    val_labels_arr = np.array(val_labels)
    test_labels_arr = np.array(test_labels)

    if args.model == "mlp":
        classifier, val_results = train_mlp_classifier(
            torch.tensor(train_features),
            torch.tensor(train_labels_arr),
            torch.tensor(val_features),
            torch.tensor(val_labels_arr),
            epochs=args.epochs,
            lr=args.lr,
            device=args.device,
        )
    else:
        classifier, val_results = train_sklearn_classifier(
            train_features, train_labels_arr,
            val_features, val_labels_arr,
            model_type=args.model,
        )

    # Evaluate on test set
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print("\nValidation Set:")
    print(f"  Accuracy:  {val_results['accuracy']:.4f}")
    print(f"  Precision: {val_results['precision']:.4f}")
    print(f"  Recall:    {val_results['recall']:.4f}")
    print(f"  F1 Score:  {val_results['f1_score']:.4f}")

    # Test set evaluation
    if args.model == "mlp":
        classifier.eval()
        mean = torch.tensor(val_results["normalization"]["mean"])
        std = torch.tensor(val_results["normalization"]["std"])
        test_norm = (torch.tensor(test_features) - mean) / std
        with torch.no_grad():
            test_logits = classifier(test_norm.to(args.device))
            test_preds = (torch.sigmoid(test_logits) > 0.5).cpu().numpy()
    else:
        model, scaler = classifier
        test_scaled = scaler.transform(test_features)
        test_preds = model.predict(test_scaled)

    test_results = {
        "accuracy": float(accuracy_score(test_labels_arr, test_preds)),
        "precision": float(precision_score(test_labels_arr, test_preds)),
        "recall": float(recall_score(test_labels_arr, test_preds)),
        "f1_score": float(f1_score(test_labels_arr, test_preds)),
    }

    print("\nTest Set:")
    print(f"  Accuracy:  {test_results['accuracy']:.4f}")
    print(f"  Precision: {test_results['precision']:.4f}")
    print(f"  Recall:    {test_results['recall']:.4f}")
    print(f"  F1 Score:  {test_results['f1_score']:.4f}")

    # Feature importance
    if "feature_importance" in val_results:
        print("\nFeature Importance:")
        sorted_features = sorted(val_results["feature_importance"].items(),
                                  key=lambda x: abs(x[1]), reverse=True)
        for name, imp in sorted_features:
            print(f"  {name:12s}: {imp:.4f}")

    # Save checkpoint
    CHECKPOINTS_DIR.mkdir(exist_ok=True)
    checkpoint_path = CHECKPOINTS_DIR / f"certificate_classifier_{args.model}.pt"

    save_data = {
        "model_type": args.model,
        "val_results": val_results,
        "test_results": test_results,
        "timestamp": datetime.now().isoformat(),
    }

    if args.model == "mlp":
        save_data["model_state_dict"] = classifier.state_dict()
        save_data["normalization"] = val_results["normalization"]
    else:
        import pickle
        model, scaler = classifier
        save_data["sklearn_model"] = pickle.dumps(model)
        save_data["sklearn_scaler"] = pickle.dumps(scaler)

    torch.save(save_data, checkpoint_path)
    print(f"\nSaved checkpoint: {checkpoint_path}")

    # Save evidence
    EVIDENCE_DIR.mkdir(exist_ok=True)
    h3_evidence = {
        "hypothesis": "H3",
        "statement": "Security classifier achieves >90% accuracy on jailbreak detection",
        "method": "Certificate-feature classifier (rotor frozen, 12 features)",
        "model_type": args.model,
        "features": ["R", "S", "N", "theta_t4", "phi_t4", "alpha_t4", "omega_t4",
                    "alpha_omega", "health", "entropy", "S-R", "N/R"],
        "val_results": val_results,
        "test_results": test_results,
        "passed": test_results["accuracy"] > 0.90,
        "timestamp": datetime.now().isoformat(),
    }

    with open(EVIDENCE_DIR / "h3_certificate_classifier.json", "w") as f:
        json.dump(h3_evidence, f, indent=2)
    print(f"Saved evidence: {EVIDENCE_DIR / 'h3_certificate_classifier.json'}")

    # Summary
    print("\n" + "=" * 70)
    print("H3 SUMMARY")
    print("=" * 70)
    print("Target: Accuracy > 90%")
    print(f"Achieved (Test): Accuracy = {test_results['accuracy']:.1%}")
    print(f"Status: {'PASS' if test_results['accuracy'] > 0.90 else 'FAIL'}")
    print(f"\nMethod: Certificate-feature classifier ({args.model})")
    print("Rotor: FROZEN (preserves RSCT geometry)")


if __name__ == "__main__":
    main()
