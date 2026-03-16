#!/usr/bin/env python3
"""
SWARM-06: Ensemble Classifier (Titan + SentenceTransformer)

Combines Bedrock Titan v2 (1024d) with SentenceTransformer (384d)
for 1408d concatenated embeddings.

Hypothesis: Different embedding models capture different patterns.
- Titan: AWS-trained, general purpose
- SentenceTransformer: Semantic similarity focused

Usage:
    python train_ensemble_classifier.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import numpy as np

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, precision_score, recall_score

# Paths
EXPERIMENT_DIR = Path(__file__).parent.parent
DATA_DIR = EXPERIMENT_DIR / "data"
CHECKPOINTS_DIR = EXPERIMENT_DIR / "checkpoints"
EMBEDDINGS_DIR = EXPERIMENT_DIR / "embeddings"
EVIDENCE_DIR = EXPERIMENT_DIR / "evidence"

YRSN_SRC = Path("/Users/rudy/GitHub/yrsn/src")
sys.path.insert(0, str(YRSN_SRC / "yrsn/adapters/models"))


# =============================================================================
# CLASSIFIER
# =============================================================================

class EnsembleClassifier(nn.Module):
    """
    Classifier on concatenated embeddings.

    Architecture: Larger MLP for 1408d input.
    """
    def __init__(self, input_dim: int = 1408, hidden_dims: List[int] = [512, 256, 128, 64]):
        super().__init__()

        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3),
            ])
            prev_dim = hidden_dim

        layers.append(nn.Linear(prev_dim, 1))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x).squeeze(-1)


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(split: str) -> Tuple[List[str], np.ndarray]:
    """Load data from unified dataset."""
    path = DATA_DIR / f"unified_{split}.jsonl"
    texts, labels = [], []
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(row["is_jailbreak"])
    return texts, np.array(labels)


def extract_st_embeddings(texts: List[str], batch_size: int = 32) -> np.ndarray:
    """Extract SentenceTransformer embeddings."""
    from text_adapter import SentenceTransformerExtractor
    extractor = SentenceTransformerExtractor(model_name='all-MiniLM-L6-v2')

    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        emb = extractor.extract(batch)
        embeddings.append(emb)
        if (i // batch_size) % 10 == 0:
            print(f"    ST: {min(i+batch_size, len(texts))}/{len(texts)}")

    return np.vstack(embeddings)


# =============================================================================
# TRAINING
# =============================================================================

def train_classifier(
    classifier: nn.Module,
    train_emb: torch.Tensor,
    train_labels: torch.Tensor,
    val_emb: torch.Tensor,
    val_labels: torch.Tensor,
    epochs: int = 100,
    lr: float = 1e-3,
) -> Tuple[nn.Module, Dict]:
    """Train the ensemble classifier."""

    classifier.train()

    dataset = TensorDataset(train_emb, train_labels.float())
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    optimizer = torch.optim.AdamW(classifier.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    pos_weight = (train_labels == 0).sum() / (train_labels == 1).sum()
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    best_f1 = 0
    best_state = None
    history = {"loss": [], "val_f1": [], "val_acc": []}

    for epoch in range(epochs):
        epoch_loss = 0
        for batch_emb, batch_labels in loader:
            optimizer.zero_grad()
            logits = classifier(batch_emb)
            loss = criterion(logits, batch_labels)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(batch_emb)

        scheduler.step()

        # Validate
        classifier.eval()
        with torch.no_grad():
            val_logits = classifier(val_emb)
            val_probs = torch.sigmoid(val_logits).numpy()
            val_preds = val_probs > 0.5

        val_f1 = f1_score(val_labels.numpy(), val_preds)
        val_acc = accuracy_score(val_labels.numpy(), val_preds)

        history["loss"].append(epoch_loss / len(dataset))
        history["val_f1"].append(val_f1)
        history["val_acc"].append(val_acc)

        if val_f1 > best_f1:
            best_f1 = val_f1
            best_state = classifier.state_dict().copy()

        if (epoch + 1) % 20 == 0:
            print(f"  Epoch {epoch+1}/{epochs}: loss={epoch_loss/len(dataset):.4f}, "
                  f"val_acc={val_acc:.4f}, val_f1={val_f1:.4f}")

        classifier.train()

    if best_state:
        classifier.load_state_dict(best_state)

    return classifier, history


def evaluate(
    classifier: nn.Module,
    embeddings: torch.Tensor,
    labels: np.ndarray,
) -> Dict:
    """Evaluate classifier."""
    classifier.eval()

    with torch.no_grad():
        logits = classifier(embeddings)
        probs = torch.sigmoid(logits).numpy()

    preds = probs > 0.5

    return {
        "accuracy": float(accuracy_score(labels, preds)),
        "precision": float(precision_score(labels, preds)),
        "recall": float(recall_score(labels, preds)),
        "f1_score": float(f1_score(labels, preds)),
        "auc": float(roc_auc_score(labels, probs)),
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("SWARM-06: ENSEMBLE CLASSIFIER (Titan + SentenceTransformer)")
    print("=" * 70)

    # Load Titan embeddings (cached)
    print("\n[1/5] Loading Titan embeddings (1024d)...")
    titan_cache = EMBEDDINGS_DIR / "titan_v2_1024d.npz"

    if not titan_cache.exists():
        print("ERROR: Run train_swarm_titan.py first to generate Titan embeddings")
        return

    titan_data = np.load(titan_cache)
    titan_train = titan_data["train_emb"]
    titan_val = titan_data["val_emb"]
    titan_test = titan_data["test_emb"]
    train_labels = titan_data["train_labels"]
    val_labels = titan_data["val_labels"]
    test_labels = titan_data["test_labels"]

    print(f"  Titan train: {titan_train.shape}")

    # Check for cached ST embeddings
    st_cache = EMBEDDINGS_DIR / "st_384d.npz"

    if st_cache.exists():
        print("\n[2/5] Loading cached SentenceTransformer embeddings (384d)...")
        st_data = np.load(st_cache)
        st_train = st_data["train_emb"]
        st_val = st_data["val_emb"]
        st_test = st_data["test_emb"]
    else:
        print("\n[2/5] Extracting SentenceTransformer embeddings (384d)...")

        train_texts, _ = load_data("train")
        val_texts, _ = load_data("val")
        test_texts, _ = load_data("test")

        print("  Training set:")
        st_train = extract_st_embeddings(train_texts)
        print("  Validation set:")
        st_val = extract_st_embeddings(val_texts)
        print("  Test set:")
        st_test = extract_st_embeddings(test_texts)

        # Cache
        np.savez(st_cache, train_emb=st_train, val_emb=st_val, test_emb=st_test)
        print(f"  Cached to {st_cache}")

    print(f"  ST train: {st_train.shape}")

    # Concatenate embeddings
    print("\n[3/5] Concatenating embeddings...")
    train_emb = np.concatenate([titan_train, st_train], axis=1)
    val_emb = np.concatenate([titan_val, st_val], axis=1)
    test_emb = np.concatenate([titan_test, st_test], axis=1)

    total_dim = train_emb.shape[1]
    print(f"  Combined: {total_dim}d (1024 + 384)")

    # Create classifier
    print(f"\n[4/5] Training classifier ({total_dim}d input)...")
    classifier = EnsembleClassifier(input_dim=total_dim)
    print(f"  Parameters: {sum(p.numel() for p in classifier.parameters()):,}")

    classifier, history = train_classifier(
        classifier=classifier,
        train_emb=torch.tensor(train_emb, dtype=torch.float32),
        train_labels=torch.tensor(train_labels),
        val_emb=torch.tensor(val_emb, dtype=torch.float32),
        val_labels=torch.tensor(val_labels),
        epochs=100,
    )

    # Evaluate
    print("\n[5/5] Evaluating...")
    val_results = evaluate(
        classifier,
        torch.tensor(val_emb, dtype=torch.float32),
        val_labels,
    )
    test_results = evaluate(
        classifier,
        torch.tensor(test_emb, dtype=torch.float32),
        test_labels,
    )

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\nValidation:")
    print(f"  Accuracy:  {val_results['accuracy']:.4f}")
    print(f"  Precision: {val_results['precision']:.4f}")
    print(f"  Recall:    {val_results['recall']:.4f}")
    print(f"  F1:        {val_results['f1_score']:.4f}")
    print(f"  AUC:       {val_results['auc']:.4f}")

    print(f"\nTest:")
    print(f"  Accuracy:  {test_results['accuracy']:.4f}")
    print(f"  Precision: {test_results['precision']:.4f}")
    print(f"  Recall:    {test_results['recall']:.4f}")
    print(f"  F1:        {test_results['f1_score']:.4f}")
    print(f"  AUC:       {test_results['auc']:.4f}")

    # Save
    CHECKPOINTS_DIR.mkdir(exist_ok=True)
    checkpoint_path = CHECKPOINTS_DIR / f"ensemble_titan_st_{total_dim}d.pt"
    torch.save({
        "model_state_dict": classifier.state_dict(),
        "config": {
            "total_dim": total_dim,
            "titan_dim": 1024,
            "st_dim": 384,
        },
        "val_results": val_results,
        "test_results": test_results,
        "timestamp": datetime.now().isoformat(),
    }, checkpoint_path)
    print(f"\nSaved: {checkpoint_path}")

    # Evidence
    EVIDENCE_DIR.mkdir(exist_ok=True)
    evidence = {
        "hypothesis": "H3",
        "method": "Ensemble (Titan v2 1024d + SentenceTransformer 384d)",
        "total_dim": total_dim,
        "val_results": val_results,
        "test_results": test_results,
        "passed": test_results["accuracy"] > 0.90,
        "timestamp": datetime.now().isoformat(),
    }
    evidence_path = EVIDENCE_DIR / "h3_ensemble_titan_st.json"
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY (ENSEMBLE)")
    print("=" * 70)
    print(f"Target: Accuracy > 90%")
    print(f"Achieved: {test_results['accuracy']:.1%}")
    print(f"Status: {'✓ PASS' if test_results['accuracy'] > 0.90 else '✗ NEEDS WORK'}")


if __name__ == "__main__":
    main()
