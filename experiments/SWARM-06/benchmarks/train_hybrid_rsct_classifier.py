#!/usr/bin/env python3
"""
SWARM-06 H3: Hybrid RSCT Gates + Specialized Jailbreak Classifier

Architecture:
    Input → RSCT Quality Gates (pre-filter) → Specialized Classifier → Decision

RSCT Gates (what RSCT is good at):
    - Gate 1: N-gate (high noise → reject garbage/incoherent)
    - Gate 2: Coherence gate (low coherence → reject inconsistent)

Specialized Classifier (what RSCT can't do):
    - Trained on RAW embeddings (not RSN - RSN loses discriminative info)
    - Learns jailbreak-specific patterns

Key insight: RSN collapses 64d → 3d simplex, losing information.
The raw embeddings contain patterns a classifier can learn.

Usage:
    python train_hybrid_rsct_classifier.py
    python train_hybrid_rsct_classifier.py --embed-dim 384  # Use raw ST embeddings

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
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

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


class JailbreakClassifier(nn.Module):
    """
    Specialized jailbreak classifier on raw embeddings.

    Architecture: MLP with dropout and batch norm for robustness.
    """
    def __init__(self, input_dim: int = 64, hidden_dims: List[int] = [128, 64, 32]):
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


class RSCTQualityGates:
    """
    RSCT quality gates for pre-filtering.

    Gate 1: N-gate (reject high noise)
    Gate 2: Coherence gate (reject low coherence)
    """

    def __init__(
        self,
        projection: nn.Module,
        rotor: nn.Module,
        n_threshold: float = 0.6,
        coherence_threshold: float = 0.3,
    ):
        self.projection = projection
        self.rotor = rotor
        self.n_threshold = n_threshold
        self.coherence_threshold = coherence_threshold

        self.projection.eval()
        self.rotor.eval()

    def compute_rsn(self, embeddings: torch.Tensor) -> Dict[str, np.ndarray]:
        """Compute RSN values for embeddings."""
        with torch.no_grad():
            emb_64 = self.projection(embeddings)
            rsn = self.rotor(emb_64)
            return {
                'R': rsn['R'].numpy(),
                'S': rsn['S'].numpy(),
                'N': rsn['N'].numpy(),
            }

    def compute_coherence(self, R: np.ndarray, S: np.ndarray, N: np.ndarray) -> np.ndarray:
        """
        Compute coherence from RSN.

        Coherence = 1 - entropy(RSN) / max_entropy
        High coherence = one component dominates (clear signal)
        Low coherence = uniform distribution (confused/adversarial)
        """
        probs = np.stack([R, S, N], axis=-1)
        probs = np.clip(probs, 1e-10, 1.0)
        entropy = -np.sum(probs * np.log(probs), axis=-1)
        max_entropy = np.log(3)  # Uniform distribution
        coherence = 1 - entropy / max_entropy
        return coherence

    def apply_gates(self, embeddings: torch.Tensor) -> Tuple[np.ndarray, Dict]:
        """
        Apply RSCT quality gates.

        Returns:
            gate_passed: Boolean array (True = passed all gates)
            gate_info: Dict with gate details
        """
        rsn = self.compute_rsn(embeddings)
        R, S, N = rsn['R'], rsn['S'], rsn['N']
        coherence = self.compute_coherence(R, S, N)

        # Gate 1: N-gate (reject high noise)
        n_gate_passed = N < self.n_threshold

        # Gate 2: Coherence gate (reject low coherence)
        coherence_gate_passed = coherence > self.coherence_threshold

        # Combined
        all_gates_passed = n_gate_passed & coherence_gate_passed

        return all_gates_passed, {
            'R': R, 'S': S, 'N': N,
            'coherence': coherence,
            'n_gate_passed': n_gate_passed,
            'coherence_gate_passed': coherence_gate_passed,
        }


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
    """Train the specialized jailbreak classifier."""

    classifier = classifier.to(device)
    train_emb = train_emb.to(device)
    train_labels = train_labels.float().to(device)
    val_emb = val_emb.to(device)
    val_labels_np = val_labels.numpy()

    # Dataset
    dataset = TensorDataset(train_emb, train_labels)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Optimizer
    optimizer = torch.optim.AdamW(classifier.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    # Class weights for imbalanced data
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

    # Restore best
    if best_state is not None:
        classifier.load_state_dict(best_state)

    return classifier, history


def evaluate_hybrid(
    gates: RSCTQualityGates,
    classifier: nn.Module,
    embeddings_384: torch.Tensor,
    embeddings_64: torch.Tensor,
    classifier_embeddings: torch.Tensor,  # The embeddings to use for classifier
    labels: np.ndarray,
    device: str = 'cpu',
) -> Dict:
    """
    Evaluate the hybrid pipeline.

    Pipeline:
    1. RSCT gates filter garbage/incoherent
    2. Classifier predicts jailbreak on remaining
    """
    classifier.eval()

    # Apply RSCT gates
    gate_passed, gate_info = gates.apply_gates(embeddings_384)

    # Get classifier predictions for all samples
    with torch.no_grad():
        logits = classifier(classifier_embeddings.to(device))
        probs = torch.sigmoid(logits).cpu().numpy()

    # Hybrid decision:
    # - Failed N-gate → UNSAFE (treat as jailbreak for safety)
    # - Failed coherence gate → UNCERTAIN (flag for review)
    # - Passed gates + classifier says jailbreak → JAILBREAK
    # - Passed gates + classifier says benign → BENIGN

    predictions = np.zeros(len(labels), dtype=bool)
    states = np.empty(len(labels), dtype=object)

    for i in range(len(labels)):
        if not gate_info['n_gate_passed'][i]:
            # Failed N-gate → treat as potential jailbreak (high noise)
            predictions[i] = True
            states[i] = "UNSAFE"
        elif not gate_info['coherence_gate_passed'][i]:
            # Failed coherence → uncertain, but flag as suspicious
            predictions[i] = probs[i] > 0.3  # Lower threshold for suspicious
            states[i] = "UNCERTAIN"
        else:
            # Passed gates → use classifier
            predictions[i] = probs[i] > 0.5
            states[i] = "JAILBREAK" if predictions[i] else "BENIGN"

    # Metrics
    tp = np.sum(predictions & labels)
    tn = np.sum(~predictions & ~labels)
    fp = np.sum(predictions & ~labels)
    fn = np.sum(~predictions & labels)

    accuracy = (tp + tn) / len(labels)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # AUC on classifier probabilities
    try:
        auc = roc_auc_score(labels, probs)
    except:
        auc = 0.5

    # State distribution
    state_dist = {
        "BENIGN": int(np.sum(states == "BENIGN")),
        "JAILBREAK": int(np.sum(states == "JAILBREAK")),
        "UNCERTAIN": int(np.sum(states == "UNCERTAIN")),
        "UNSAFE": int(np.sum(states == "UNSAFE")),
    }

    # Gate statistics
    gate_stats = {
        "n_gate_reject_rate": float(1 - gate_info['n_gate_passed'].mean()),
        "coherence_gate_reject_rate": float(1 - gate_info['coherence_gate_passed'].mean()),
        "total_gate_pass_rate": float(gate_passed.mean()),
    }

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
        "state_distribution": state_dist,
        "gate_stats": gate_stats,
        "rsn_stats": {
            "N_mean": float(gate_info['N'].mean()),
            "coherence_mean": float(gate_info['coherence'].mean()),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Hybrid RSCT + Specialized Classifier")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--n-threshold", type=float, default=0.6, help="N-gate threshold")
    parser.add_argument("--coherence-threshold", type=float, default=0.3, help="Coherence threshold")
    parser.add_argument("--embed-dim", type=int, default=64, choices=[64, 384],
                        help="Embedding dimension for classifier (64=projected, 384=raw)")
    args = parser.parse_args()

    print("=" * 70)
    print("SWARM-06 H3: HYBRID RSCT GATES + SPECIALIZED CLASSIFIER")
    print("=" * 70)
    print("\nArchitecture:")
    print("  Gate 1: N-gate (high noise → UNSAFE)")
    print("  Gate 2: Coherence gate (low coherence → UNCERTAIN)")
    print("  Gate 3: Specialized classifier on raw embeddings")
    print("\nConfig:")
    print(f"  N threshold: {args.n_threshold}")
    print(f"  Coherence threshold: {args.coherence_threshold}")
    print(f"  Classifier input: {args.embed_dim}d embeddings")

    # Load models
    print("\n[1/7] Loading text extractor...")
    from text_adapter import SentenceTransformerExtractor
    extractor = SentenceTransformerExtractor(model_name='all-MiniLM-L6-v2')
    print(f"  Loaded: {extractor.model_name}")

    print("\n[2/7] Loading projection model...")
    projection = TextMLP384to64()
    proj_ckpt = YRSN_CHECKPOINTS / "text_mlp_384to64_trained.pt"
    if proj_ckpt.exists():
        ckpt = torch.load(proj_ckpt, map_location='cpu', weights_only=False)
        projection.load_state_dict(ckpt.get('model_state_dict', ckpt))
    projection.eval()

    print("\n[3/7] Loading rotor...")
    from hybrid_rotor import HybridSimplexRotor
    rotor = HybridSimplexRotor(embed_dim=64, subspace_dim=64, hidden_dim=256)
    rotor_ckpt = YRSN_CHECKPOINTS / "trained_rotor_text64.pt"
    if rotor_ckpt.exists():
        ckpt = torch.load(rotor_ckpt, map_location='cpu', weights_only=False)
        rotor.load_state_dict(ckpt.get('model_state_dict', ckpt))
    rotor.eval()

    # Create RSCT gates
    gates = RSCTQualityGates(
        projection=projection,
        rotor=rotor,
        n_threshold=args.n_threshold,
        coherence_threshold=args.coherence_threshold,
    )

    # Load data
    print("\n[4/7] Loading data...")
    train_texts, train_labels = load_data("train")
    val_texts, val_labels = load_data("val")
    test_texts, test_labels = load_data("test")

    train_labels = np.array(train_labels)
    val_labels = np.array(val_labels)
    test_labels = np.array(test_labels)

    print(f"  Train: {len(train_texts)} ({np.sum(train_labels)} jailbreak)")
    print(f"  Val:   {len(val_texts)} ({np.sum(val_labels)} jailbreak)")
    print(f"  Test:  {len(test_texts)} ({np.sum(test_labels)} jailbreak)")

    # Extract embeddings
    print("\n[5/7] Extracting embeddings...")
    print("  Training:")
    train_emb_384 = extract_embeddings(train_texts, extractor)
    print("  Validation:")
    val_emb_384 = extract_embeddings(val_texts, extractor)
    print("  Test:")
    test_emb_384 = extract_embeddings(test_texts, extractor)

    # Project to 64d
    print("\n  Projecting to 64d...")
    with torch.no_grad():
        train_emb_64 = projection(torch.tensor(train_emb_384, dtype=torch.float32)).numpy()
        val_emb_64 = projection(torch.tensor(val_emb_384, dtype=torch.float32)).numpy()
        test_emb_64 = projection(torch.tensor(test_emb_384, dtype=torch.float32)).numpy()

    # Select embedding dimension for classifier
    if args.embed_dim == 384:
        train_emb = train_emb_384
        val_emb = val_emb_384
        test_emb = test_emb_384
    else:
        train_emb = train_emb_64
        val_emb = val_emb_64
        test_emb = test_emb_64

    # Create and train classifier
    print(f"\n[6/7] Training specialized classifier ({args.embed_dim}d input)...")
    classifier = JailbreakClassifier(
        input_dim=args.embed_dim,
        hidden_dims=[128, 64, 32],
    )
    print(f"  Classifier parameters: {sum(p.numel() for p in classifier.parameters()):,}")

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

    print("\n[7/7] Evaluating hybrid pipeline...")

    val_results = evaluate_hybrid(
        gates=gates,
        classifier=classifier,
        embeddings_384=torch.tensor(val_emb_384, dtype=torch.float32),
        embeddings_64=torch.tensor(val_emb_64, dtype=torch.float32),
        classifier_embeddings=torch.tensor(val_emb, dtype=torch.float32),
        labels=val_labels,
    )

    test_results = evaluate_hybrid(
        gates=gates,
        classifier=classifier,
        embeddings_384=torch.tensor(test_emb_384, dtype=torch.float32),
        embeddings_64=torch.tensor(test_emb_64, dtype=torch.float32),
        classifier_embeddings=torch.tensor(test_emb, dtype=torch.float32),
        labels=test_labels,
    )

    print("\nValidation Set:")
    print(f"  Accuracy:  {val_results['accuracy']:.4f}")
    print(f"  Precision: {val_results['precision']:.4f}")
    print(f"  Recall:    {val_results['recall']:.4f}")
    print(f"  F1 Score:  {val_results['f1_score']:.4f}")
    print(f"  AUC:       {val_results['auc']:.4f}")
    print(f"\n  Gate stats: {val_results['gate_stats']}")
    print(f"  States: {val_results['state_distribution']}")

    print("\nTest Set:")
    print(f"  Accuracy:  {test_results['accuracy']:.4f}")
    print(f"  Precision: {test_results['precision']:.4f}")
    print(f"  Recall:    {test_results['recall']:.4f}")
    print(f"  F1 Score:  {test_results['f1_score']:.4f}")
    print(f"  AUC:       {test_results['auc']:.4f}")
    print(f"\n  Gate stats: {test_results['gate_stats']}")
    print(f"  States: {test_results['state_distribution']}")

    # Save checkpoint
    CHECKPOINTS_DIR.mkdir(exist_ok=True)
    checkpoint_path = CHECKPOINTS_DIR / f"hybrid_classifier_{args.embed_dim}d.pt"
    torch.save({
        "model_state_dict": classifier.state_dict(),
        "config": {
            "embed_dim": args.embed_dim,
            "n_threshold": args.n_threshold,
            "coherence_threshold": args.coherence_threshold,
            "epochs": args.epochs,
            "lr": args.lr,
        },
        "history": history,
        "val_results": val_results,
        "test_results": test_results,
        "timestamp": datetime.now().isoformat(),
    }, checkpoint_path)
    print(f"\nSaved checkpoint: {checkpoint_path}")

    # Save evidence
    EVIDENCE_DIR.mkdir(exist_ok=True)
    evidence = {
        "hypothesis": "H3",
        "method": "Hybrid RSCT gates + specialized classifier",
        "architecture": {
            "gate_1": f"N-gate (threshold={args.n_threshold})",
            "gate_2": f"Coherence gate (threshold={args.coherence_threshold})",
            "classifier": f"MLP on {args.embed_dim}d embeddings",
        },
        "config": {
            "embed_dim": args.embed_dim,
            "n_threshold": args.n_threshold,
            "coherence_threshold": args.coherence_threshold,
            "epochs": args.epochs,
        },
        "val_results": val_results,
        "test_results": test_results,
        "passed": test_results["accuracy"] > 0.90,
        "timestamp": datetime.now().isoformat(),
    }

    evidence_path = EVIDENCE_DIR / "h3_hybrid_rsct_classifier.json"
    with open(evidence_path, "w") as f:
        json.dump(evidence, f, indent=2)
    print(f"Saved evidence: {evidence_path}")

    # Summary
    print("\n" + "=" * 70)
    print("H3 SUMMARY (HYBRID APPROACH)")
    print("=" * 70)
    print("Target: Accuracy > 90%")
    print(f"Achieved (Test): Accuracy = {test_results['accuracy']:.1%}")
    print(f"F1 Score: {test_results['f1_score']:.4f}")
    print(f"AUC: {test_results['auc']:.4f}")
    print(f"Status: {'PASS' if test_results['accuracy'] > 0.90 else 'NEEDS WORK'}")
    print("\nHybrid architecture:")
    print(f"  RSCT gates: N < {args.n_threshold}, coherence > {args.coherence_threshold}")
    print(f"  Classifier: MLP on {args.embed_dim}d embeddings")


if __name__ == "__main__":
    main()
