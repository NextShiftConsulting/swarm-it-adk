#!/usr/bin/env python3
"""
SWARM-06 H3: Multi-Encoder Ensemble Jailbreak Classifier

Multi-modal approach for text: Use multiple embedding models as different "views"
of the same text, then ensemble their predictions.

Different encoders may capture different patterns:
- all-MiniLM-L6-v2: General semantic similarity (384d)
- all-mpnet-base-v2: Higher quality, larger (768d)
- paraphrase-MiniLM-L6-v2: Paraphrase-trained (384d)

Ensemble strategy: Concatenate embeddings + joint classifier

Usage:
    python train_multi_encoder_classifier.py
    python train_multi_encoder_classifier.py --encoders 2

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
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sentence_transformers import SentenceTransformer

# Paths
EXPERIMENT_DIR = Path(__file__).parent.parent
DATA_DIR = EXPERIMENT_DIR / "data"
CHECKPOINTS_DIR = EXPERIMENT_DIR / "checkpoints"
EVIDENCE_DIR = EXPERIMENT_DIR / "evidence"

# Available encoders
ENCODER_CONFIGS = {
    "minilm": ("all-MiniLM-L6-v2", 384),
    "mpnet": ("all-mpnet-base-v2", 768),
    "paraphrase": ("paraphrase-MiniLM-L6-v2", 384),
}


class MultiEncoderClassifier(nn.Module):
    """
    Classifier on concatenated multi-encoder embeddings.
    """
    def __init__(self, input_dim: int, hidden_dims: List[int] = [256, 128, 64]):
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


def extract_multi_embeddings(
    texts: List[str],
    encoder_names: List[str],
    batch_size: int = 32,
) -> np.ndarray:
    """
    Extract embeddings from multiple encoders and concatenate.
    """
    all_embeddings = []

    for name in encoder_names:
        model_name, dim = ENCODER_CONFIGS[name]
        print(f"  Loading {name} ({model_name}, {dim}d)...")
        encoder = SentenceTransformer(model_name)

        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            emb = encoder.encode(batch, show_progress_bar=False)
            embeddings.append(emb)
            if (i // batch_size) % 10 == 0:
                print(f"    Extracted {min(i+batch_size, len(texts))}/{len(texts)}")

        all_embeddings.append(np.vstack(embeddings))

    # Concatenate all encoder outputs
    combined = np.concatenate(all_embeddings, axis=1)
    print(f"  Combined shape: {combined.shape}")
    return combined


def train_classifier(
    classifier: nn.Module,
    train_emb: torch.Tensor,
    train_labels: torch.Tensor,
    val_emb: torch.Tensor,
    val_labels: torch.Tensor,
    epochs: int = 100,
    lr: float = 1e-3,
    batch_size: int = 64,
    device: str = 'cpu',
) -> Tuple[nn.Module, Dict]:
    """Train the multi-encoder classifier."""

    classifier = classifier.to(device)
    train_emb = train_emb.to(device)
    train_labels = train_labels.float().to(device)
    val_emb = val_emb.to(device)
    val_labels_np = val_labels.numpy()

    dataset = TensorDataset(train_emb, train_labels)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(classifier.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    pos_weight = (train_labels == 0).sum() / (train_labels == 1).sum()
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight.to(device))

    best_f1 = 0
    best_state = None
    history = {"loss": [], "val_f1": [], "val_acc": []}

    for epoch in range(epochs):
        classifier.train()
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
            val_logits = classifier(val_emb.to(device))
            val_probs = torch.sigmoid(val_logits).cpu().numpy()
            val_preds = val_probs > 0.5

        val_acc = accuracy_score(val_labels_np, val_preds)
        val_f1 = f1_score(val_labels_np, val_preds)

        history["loss"].append(epoch_loss / len(dataset))
        history["val_f1"].append(val_f1)
        history["val_acc"].append(val_acc)

        if val_f1 > best_f1:
            best_f1 = val_f1
            best_state = classifier.state_dict().copy()

        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}/{epochs}: loss={epoch_loss/len(dataset):.4f}, "
                  f"val_acc={val_acc:.4f}, val_f1={val_f1:.4f}")

    if best_state is not None:
        classifier.load_state_dict(best_state)

    return classifier, history


def evaluate(
    classifier: nn.Module,
    embeddings: torch.Tensor,
    labels: np.ndarray,
    device: str = 'cpu',
) -> Dict:
    """Evaluate the classifier."""
    classifier.eval()

    with torch.no_grad():
        logits = classifier(embeddings.to(device))
        probs = torch.sigmoid(logits).cpu().numpy()

    predictions = probs > 0.5

    tp = np.sum(predictions & labels)
    tn = np.sum(~predictions & ~labels)
    fp = np.sum(predictions & ~labels)
    fn = np.sum(~predictions & labels)

    accuracy = (tp + tn) / len(labels)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    try:
        auc = roc_auc_score(labels, probs)
    except:
        auc = 0.5

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "auc": float(auc),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }


def main():
    parser = argparse.ArgumentParser(description="Multi-Encoder Jailbreak Classifier")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--encoders", type=int, default=3, choices=[1, 2, 3],
                        help="Number of encoders to use")
    args = parser.parse_args()

    encoder_names = ["minilm", "mpnet", "paraphrase"][:args.encoders]
    total_dim = sum(ENCODER_CONFIGS[n][1] for n in encoder_names)

    print("=" * 70)
    print("SWARM-06 H3: MULTI-ENCODER ENSEMBLE CLASSIFIER")
    print("=" * 70)
    print(f"\nEncoders ({args.encoders}):")
    for name in encoder_names:
        model, dim = ENCODER_CONFIGS[name]
        print(f"  - {name}: {model} ({dim}d)")
    print(f"\nCombined embedding dimension: {total_dim}d")

    # Load data
    print("\n[1/5] Loading data...")
    train_texts, train_labels = load_data("train")
    val_texts, val_labels = load_data("val")
    test_texts, test_labels = load_data("test")

    train_labels = np.array(train_labels)
    val_labels = np.array(val_labels)
    test_labels = np.array(test_labels)

    print(f"  Train: {len(train_texts)} ({np.sum(train_labels)} jailbreak)")
    print(f"  Val:   {len(val_texts)} ({np.sum(val_labels)} jailbreak)")
    print(f"  Test:  {len(test_texts)} ({np.sum(test_labels)} jailbreak)")

    # Extract multi-encoder embeddings
    print("\n[2/5] Extracting multi-encoder embeddings...")
    print("  Training set:")
    train_emb = extract_multi_embeddings(train_texts, encoder_names)
    print("  Validation set:")
    val_emb = extract_multi_embeddings(val_texts, encoder_names)
    print("  Test set:")
    test_emb = extract_multi_embeddings(test_texts, encoder_names)

    # Create classifier
    print(f"\n[3/5] Creating classifier ({total_dim}d input)...")
    classifier = MultiEncoderClassifier(
        input_dim=total_dim,
        hidden_dims=[256, 128, 64],
    )
    print(f"  Parameters: {sum(p.numel() for p in classifier.parameters()):,}")

    # Train
    print("\n[4/5] Training...")
    classifier, history = train_classifier(
        classifier=classifier,
        train_emb=torch.tensor(train_emb, dtype=torch.float32),
        train_labels=torch.tensor(train_labels),
        val_emb=torch.tensor(val_emb, dtype=torch.float32),
        val_labels=torch.tensor(val_labels),
        epochs=args.epochs,
        lr=args.lr,
    )

    # Evaluate
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

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

    print("\nValidation Set:")
    print(f"  Accuracy:  {val_results['accuracy']:.4f}")
    print(f"  Precision: {val_results['precision']:.4f}")
    print(f"  Recall:    {val_results['recall']:.4f}")
    print(f"  F1 Score:  {val_results['f1_score']:.4f}")
    print(f"  AUC:       {val_results['auc']:.4f}")

    print("\nTest Set:")
    print(f"  Accuracy:  {test_results['accuracy']:.4f}")
    print(f"  Precision: {test_results['precision']:.4f}")
    print(f"  Recall:    {test_results['recall']:.4f}")
    print(f"  F1 Score:  {test_results['f1_score']:.4f}")
    print(f"  AUC:       {test_results['auc']:.4f}")

    # Save
    CHECKPOINTS_DIR.mkdir(exist_ok=True)
    checkpoint_path = CHECKPOINTS_DIR / f"multi_encoder_{args.encoders}enc.pt"
    torch.save({
        "model_state_dict": classifier.state_dict(),
        "encoder_names": encoder_names,
        "total_dim": total_dim,
        "history": history,
        "val_results": val_results,
        "test_results": test_results,
        "timestamp": datetime.now().isoformat(),
    }, checkpoint_path)
    print(f"\nSaved checkpoint: {checkpoint_path}")

    EVIDENCE_DIR.mkdir(exist_ok=True)
    evidence = {
        "hypothesis": "H3",
        "method": "Multi-encoder ensemble classifier",
        "encoders": encoder_names,
        "total_dim": total_dim,
        "val_results": val_results,
        "test_results": test_results,
        "passed": test_results["accuracy"] > 0.90,
        "timestamp": datetime.now().isoformat(),
    }
    evidence_path = EVIDENCE_DIR / "h3_multi_encoder.json"
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)
    print(f"Saved evidence: {evidence_path}")

    # Summary
    print("\n" + "=" * 70)
    print("H3 SUMMARY (MULTI-ENCODER)")
    print("=" * 70)
    print(f"Target: Accuracy > 90%")
    print(f"Achieved (Test): Accuracy = {test_results['accuracy']:.1%}")
    print(f"F1 Score: {test_results['f1_score']:.4f}")
    print(f"AUC: {test_results['auc']:.4f}")
    print(f"Status: {'PASS' if test_results['accuracy'] > 0.90 else 'NEEDS WORK'}")
    print(f"\nEncoders: {encoder_names}")
    print(f"Combined dimension: {total_dim}d")


if __name__ == "__main__":
    main()
