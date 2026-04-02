#!/usr/bin/env python3
"""
SWARM-06: Train 128d Text Rotor for RSN Decomposition

Trains HybridSimplexRotor on 128d text embeddings (output of TextProjection128).
This enables full 128d pipeline for DyTopo semantic routing.

Usage:
    python train_rotor_128d.py
    python train_rotor_128d.py --epochs 100 --lr 1e-3
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

# Paths
EXPERIMENT_DIR = Path(__file__).parent.parent
CHECKPOINTS_DIR = EXPERIMENT_DIR / "checkpoints"
EMBEDDINGS_DIR = EXPERIMENT_DIR / "embeddings"
YRSN_SRC = Path("/Users/rudy/GitHub/yrsn/src")
YRSN_CHECKPOINTS = Path("/Users/rudy/GitHub/yrsn/checkpoints")

sys.path.insert(0, str(YRSN_SRC))
sys.path.insert(0, str(YRSN_SRC / "yrsn/core/decomposition"))


# =============================================================================
# LOAD 128D PROJECTION MODEL
# =============================================================================

class TextProjection128(nn.Module):
    """384d → 128d projection (must match train_projection_128d.py)."""
    def __init__(self):
        super().__init__()
        self.alpha = nn.Parameter(torch.tensor(0.5))
        self.fc1 = nn.Linear(384, 256)
        self.ln1 = nn.LayerNorm(256)
        self.fc2 = nn.Linear(256, 192)
        self.ln2 = nn.LayerNorm(192)
        self.fc3 = nn.Linear(192, 128)
        self.skip = nn.Linear(384, 128)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.ln1(self.fc1(x)))
        h = torch.relu(self.ln2(self.fc2(h)))
        h = self.fc3(h)
        s = self.skip(x)
        return self.alpha * h + (1 - self.alpha) * s


def load_projection() -> TextProjection128:
    """Load trained 128d projection."""
    proj_path = YRSN_CHECKPOINTS / "text_mlp_384to128_trained.pt"
    if not proj_path.exists():
        proj_path = CHECKPOINTS_DIR / "text_mlp_384to128_trained.pt"

    projection = TextProjection128()
    ckpt = torch.load(proj_path, map_location='cpu', weights_only=False)
    projection.load_state_dict(ckpt.get('model_state_dict', ckpt))
    projection.eval()
    return projection


# =============================================================================
# ROTOR TRAINING
# =============================================================================

def load_embeddings_128d(projection: nn.Module) -> Tuple[torch.Tensor, ...]:
    """Load 384d embeddings and project to 128d."""
    st_cache = EMBEDDINGS_DIR / "st_384d.npz"
    titan_cache = EMBEDDINGS_DIR / "titan_v2_1024d.npz"

    st_data = np.load(st_cache)
    titan_data = np.load(titan_cache)

    # Load 384d embeddings
    train_384 = torch.tensor(st_data["train_emb"], dtype=torch.float32)
    val_384 = torch.tensor(st_data["val_emb"], dtype=torch.float32)
    test_384 = torch.tensor(st_data["test_emb"], dtype=torch.float32)

    # Project to 128d
    with torch.no_grad():
        train_128 = projection(train_384)
        val_128 = projection(val_384)
        test_128 = projection(test_384)

    # Labels
    train_labels = torch.tensor(titan_data["train_labels"], dtype=torch.float32)
    val_labels = torch.tensor(titan_data["val_labels"], dtype=torch.float32)
    test_labels = torch.tensor(titan_data["test_labels"], dtype=torch.float32)

    return train_128, val_128, test_128, train_labels, val_labels, test_labels


def simplex_loss(R: torch.Tensor, S: torch.Tensor, N: torch.Tensor) -> torch.Tensor:
    """Simplex constraint loss: R + S + N = 1."""
    total = R + S + N
    return F.mse_loss(total, torch.ones_like(total))


def entropy_regularization(R: torch.Tensor, S: torch.Tensor, N: torch.Tensor) -> torch.Tensor:
    """Encourage non-degenerate decompositions (avoid all mass on one component)."""
    probs = torch.stack([R, S, N], dim=-1)
    probs = probs.clamp(min=1e-8)
    entropy = -(probs * probs.log()).sum(dim=-1).mean()
    max_entropy = np.log(3)
    return -(entropy / max_entropy)  # Negative because we want to maximize entropy


def contrastive_rsn_loss(
    rsn: Dict[str, torch.Tensor],
    labels: torch.Tensor,
    margin: float = 0.5,
) -> torch.Tensor:
    """
    Contrastive loss on RSN values.

    Jailbreaks should have higher N (noise) than benign.
    Benign should have higher R (relevance) than jailbreaks.
    """
    R, S, N = rsn['R'], rsn['S'], rsn['N']

    jailbreak_mask = labels == 1
    benign_mask = labels == 0

    if jailbreak_mask.sum() == 0 or benign_mask.sum() == 0:
        return torch.tensor(0.0, device=R.device, requires_grad=True)

    # Jailbreaks should have higher N
    jailbreak_N = N[jailbreak_mask].mean()
    benign_N = N[benign_mask].mean()
    n_loss = F.relu(margin - (jailbreak_N - benign_N))

    # Benign should have higher R
    benign_R = R[benign_mask].mean()
    jailbreak_R = R[jailbreak_mask].mean()
    r_loss = F.relu(margin - (benign_R - jailbreak_R))

    return n_loss + r_loss


def train_epoch(
    rotor: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    lambda_simplex: float = 1.0,
    lambda_entropy: float = 0.1,
    lambda_contrastive: float = 0.5,
) -> Dict[str, float]:
    """Train one epoch."""
    rotor.train()

    total_loss = 0
    total_simplex = 0
    total_entropy = 0
    total_contrastive = 0
    n_batches = 0

    for batch_x, batch_y in loader:
        optimizer.zero_grad()

        # Forward
        rsn = rotor(batch_x)
        R, S, N = rsn['R'], rsn['S'], rsn['N']

        # Losses
        loss_simplex = simplex_loss(R, S, N)
        loss_entropy = entropy_regularization(R, S, N)
        loss_contrastive = contrastive_rsn_loss(rsn, batch_y)

        loss = (
            lambda_simplex * loss_simplex +
            lambda_entropy * loss_entropy +
            lambda_contrastive * loss_contrastive
        )

        loss.backward()
        torch.nn.utils.clip_grad_norm_(rotor.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()
        total_simplex += loss_simplex.item()
        total_entropy += loss_entropy.item()
        total_contrastive += loss_contrastive.item()
        n_batches += 1

    return {
        "loss": total_loss / n_batches,
        "simplex": total_simplex / n_batches,
        "entropy": total_entropy / n_batches,
        "contrastive": total_contrastive / n_batches,
    }


def evaluate(rotor: nn.Module, embeddings: torch.Tensor, labels: np.ndarray) -> Dict[str, float]:
    """Evaluate rotor."""
    rotor.eval()

    with torch.no_grad():
        rsn = rotor(embeddings)
        R, S, N = rsn['R'], rsn['S'], rsn['N']

        # Simplex compliance
        total = R + S + N
        simplex_error = (total - 1.0).abs().mean().item()

        # Average RSN by class
        jailbreak_mask = labels == 1
        benign_mask = labels == 0

        metrics = {
            "simplex_error": simplex_error,
            "mean_R": R.mean().item(),
            "mean_S": S.mean().item(),
            "mean_N": N.mean().item(),
        }

        if jailbreak_mask.sum() > 0:
            metrics["jailbreak_N"] = N[jailbreak_mask].mean().item()
            metrics["jailbreak_R"] = R[jailbreak_mask].mean().item()
        if benign_mask.sum() > 0:
            metrics["benign_N"] = N[benign_mask].mean().item()
            metrics["benign_R"] = R[benign_mask].mean().item()

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train 128d rotor")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lambda-simplex", type=float, default=1.0)
    parser.add_argument("--lambda-entropy", type=float, default=0.1)
    parser.add_argument("--lambda-contrastive", type=float, default=0.5)
    args = parser.parse_args()

    print("=" * 70)
    print("SWARM-06: Train 128d Text Rotor")
    print("=" * 70)

    # Load projection
    print("\n[1/5] Loading 128d projection...")
    projection = load_projection()
    print("  Projection loaded")

    # Load and project data
    print("\n[2/5] Loading and projecting embeddings...")
    train_128, val_128, test_128, train_labels, val_labels, test_labels = load_embeddings_128d(projection)
    print(f"  Train: {train_128.shape}")
    print(f"  Val: {val_128.shape}")
    print(f"  Test: {test_128.shape}")

    # Create rotor
    print("\n[3/5] Creating HybridSimplexRotor...")
    from hybrid_rotor import HybridSimplexRotor
    rotor = HybridSimplexRotor(embed_dim=128, subspace_dim=128, hidden_dim=256)
    print(f"  Params: {sum(p.numel() for p in rotor.parameters()):,}")

    # Training setup
    dataset = TensorDataset(train_128, train_labels)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(rotor.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    # Training
    print("\n[4/5] Training...")
    best_simplex_error = float('inf')
    best_state = None

    for epoch in range(args.epochs):
        metrics = train_epoch(
            rotor, loader, optimizer,
            args.lambda_simplex, args.lambda_entropy, args.lambda_contrastive
        )
        scheduler.step()

        # Evaluate
        val_metrics = evaluate(rotor, val_128, val_labels.numpy())

        if val_metrics["simplex_error"] < best_simplex_error:
            best_simplex_error = val_metrics["simplex_error"]
            best_state = rotor.state_dict().copy()

        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}/{args.epochs}: "
                  f"loss={metrics['loss']:.4f}, "
                  f"simplex={val_metrics['simplex_error']:.6f}, "
                  f"benign_R={val_metrics.get('benign_R', 0):.3f}, "
                  f"jailbreak_N={val_metrics.get('jailbreak_N', 0):.3f}")

    # Restore best
    rotor.load_state_dict(best_state)

    # Final evaluation
    print("\n[5/5] Final evaluation...")
    val_metrics = evaluate(rotor, val_128, val_labels.numpy())
    test_metrics = evaluate(rotor, test_128, test_labels.numpy())

    print("\n  Validation:")
    print(f"    Simplex error: {val_metrics['simplex_error']:.6f}")
    print(f"    Benign R: {val_metrics.get('benign_R', 0):.3f}, N: {val_metrics.get('benign_N', 0):.3f}")
    print(f"    Jailbreak R: {val_metrics.get('jailbreak_R', 0):.3f}, N: {val_metrics.get('jailbreak_N', 0):.3f}")

    print("\n  Test:")
    print(f"    Simplex error: {test_metrics['simplex_error']:.6f}")
    print(f"    Benign R: {test_metrics.get('benign_R', 0):.3f}, N: {test_metrics.get('benign_N', 0):.3f}")
    print(f"    Jailbreak R: {test_metrics.get('jailbreak_R', 0):.3f}, N: {test_metrics.get('jailbreak_N', 0):.3f}")

    # Save
    CHECKPOINTS_DIR.mkdir(exist_ok=True)

    # Local checkpoint
    local_path = CHECKPOINTS_DIR / "trained_rotor_text128.pt"
    torch.save({
        "model_state_dict": rotor.state_dict(),
        "config": {
            "embed_dim": 128,
            "subspace_dim": 128,
            "hidden_dim": 256,
        },
        "test_metrics": test_metrics,
        "timestamp": datetime.now().isoformat(),
    }, local_path)
    print(f"\n  Saved: {local_path}")

    # YRSN checkpoint (universal naming)
    yrsn_path = YRSN_CHECKPOINTS / "trained_rotor_universal128.pt"
    torch.save({
        "model_state_dict": rotor.state_dict(),
    }, yrsn_path)
    print(f"  Saved: {yrsn_path}")

    # Summary
    print("\n" + "=" * 70)
    print("128d ROTOR TRAINING COMPLETE")
    print("=" * 70)
    print("\nRotor: 128d → RSN (R, S, N)")
    print(f"Simplex compliance: {test_metrics['simplex_error']:.6f} error")
    print("\nDyTopo RSN semantics:")
    print("  Benign prompts: Higher R (relevance), Lower N")
    print("  Jailbreaks: Higher N (noise), Lower R")


if __name__ == "__main__":
    main()
