#!/usr/bin/env python3
"""
SWARM-06: Train 384d → 128d Text Projection

Trains projection layer for DyTopo 128d support.
Uses contrastive learning to preserve semantic structure.

Training Objectives:
1. Reconstruction: Preserve information from 384d
2. Contrastive: Same-class samples closer, different-class samples farther
3. RSN-alignment: Prepare for downstream RSN decomposition

Output:
    checkpoints/text_mlp_384to128_trained.pt

Usage:
    python train_projection_128d.py
    python train_projection_128d.py --epochs 200 --lr 1e-3
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score

# Paths
EXPERIMENT_DIR = Path(__file__).parent.parent
DATA_DIR = EXPERIMENT_DIR / "data"
CHECKPOINTS_DIR = EXPERIMENT_DIR / "checkpoints"
EMBEDDINGS_DIR = EXPERIMENT_DIR / "embeddings"
YRSN_CHECKPOINTS = Path("/Users/rudy/GitHub/yrsn/checkpoints")

YRSN_SRC = Path("/Users/rudy/GitHub/yrsn/src")
sys.path.insert(0, str(YRSN_SRC / "yrsn/adapters/models"))


# =============================================================================
# 128d PROJECTION MODEL
# =============================================================================

class TextProjection128(nn.Module):
    """
    384d → 128d projection with skip connection.

    Architecture matches YRSN pattern but expanded for 128d output.
    """
    def __init__(self):
        super().__init__()
        self.alpha = nn.Parameter(torch.tensor(0.5))

        # Main path: 384 → 256 → 192 → 128
        self.fc1 = nn.Linear(384, 256)
        self.ln1 = nn.LayerNorm(256)
        self.fc2 = nn.Linear(256, 192)
        self.ln2 = nn.LayerNorm(192)
        self.fc3 = nn.Linear(192, 128)

        # Skip connection: 384 → 128
        self.skip = nn.Linear(384, 128)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Main path with residual
        h = torch.relu(self.ln1(self.fc1(x)))
        h = torch.relu(self.ln2(self.fc2(h)))
        h = self.fc3(h)

        # Skip connection
        s = self.skip(x)

        # Learned combination
        return self.alpha * h + (1 - self.alpha) * s


class ProjectionDecoder(nn.Module):
    """128d → 384d decoder for reconstruction loss."""
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(128, 192)
        self.ln1 = nn.LayerNorm(192)
        self.fc2 = nn.Linear(192, 256)
        self.ln2 = nn.LayerNorm(256)
        self.fc3 = nn.Linear(256, 384)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.ln1(self.fc1(x)))
        h = torch.relu(self.ln2(self.fc2(h)))
        return self.fc3(h)


class ContrastiveProjectionModel(nn.Module):
    """
    Full model for contrastive projection training.

    Components:
    - Encoder: 384d → 128d projection
    - Decoder: 128d → 384d reconstruction
    - Classifier: 128d → 1 (jailbreak detection)
    """
    def __init__(self):
        super().__init__()
        self.encoder = TextProjection128()
        self.decoder = ProjectionDecoder()
        self.classifier = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        # Encode to 128d
        z = self.encoder(x)

        # Decode back to 384d
        x_recon = self.decoder(z)

        # Classify
        logits = self.classifier(z).squeeze(-1)

        return {
            "z": z,
            "x_recon": x_recon,
            "logits": logits,
        }


# =============================================================================
# LOSSES
# =============================================================================

def reconstruction_loss(x: torch.Tensor, x_recon: torch.Tensor) -> torch.Tensor:
    """MSE reconstruction loss."""
    return F.mse_loss(x_recon, x)


def contrastive_loss(
    z: torch.Tensor,
    labels: torch.Tensor,
    temperature: float = 0.5,
) -> torch.Tensor:
    """
    Supervised contrastive loss.

    Same-class samples should be closer, different-class farther.
    """
    # Normalize embeddings
    z_norm = F.normalize(z, dim=1)

    # Compute similarity matrix
    sim_matrix = torch.mm(z_norm, z_norm.t()) / temperature

    # Create mask for same-class pairs
    labels_col = labels.unsqueeze(1)
    mask_same = (labels_col == labels_col.t()).float()

    # Create diagonal mask (no in-place operations)
    batch_size = z.size(0)
    diag_mask = 1.0 - torch.eye(batch_size, device=z.device)

    # Apply masks
    mask_same = mask_same * diag_mask

    # For each sample, compute loss
    exp_sim = torch.exp(sim_matrix) * diag_mask

    # Positive pairs (same class)
    pos_sim = (exp_sim * mask_same).sum(dim=1)

    # All pairs (denominator)
    all_sim = exp_sim.sum(dim=1)

    # Avoid division by zero
    pos_count = mask_same.sum(dim=1)

    # Loss: -log(pos / all)
    loss = -torch.log((pos_sim / (all_sim + 1e-8)).clamp(min=1e-8))

    # Only compute for samples with positive pairs
    valid_mask = pos_count > 0
    if valid_mask.sum() > 0:
        return loss[valid_mask].mean()
    return torch.tensor(0.0, device=z.device, requires_grad=True)


def classification_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    pos_weight: torch.Tensor,
) -> torch.Tensor:
    """BCE loss for jailbreak classification."""
    return F.binary_cross_entropy_with_logits(
        logits, labels.float(), pos_weight=pos_weight
    )


# =============================================================================
# DATA
# =============================================================================

def load_embeddings() -> Tuple[np.ndarray, ...]:
    """Load cached 384d embeddings."""
    st_cache = EMBEDDINGS_DIR / "st_384d.npz"
    titan_cache = EMBEDDINGS_DIR / "titan_v2_1024d.npz"  # For labels

    if not st_cache.exists():
        raise FileNotFoundError(
            "Run train_ensemble_classifier.py first to generate ST embeddings"
        )

    st_data = np.load(st_cache)
    titan_data = np.load(titan_cache)

    return (
        st_data["train_emb"],
        st_data["val_emb"],
        st_data["test_emb"],
        titan_data["train_labels"],
        titan_data["val_labels"],
        titan_data["test_labels"],
    )


# =============================================================================
# TRAINING
# =============================================================================

def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    pos_weight: torch.Tensor,
    lambda_recon: float = 1.0,
    lambda_contrast: float = 0.5,
    lambda_class: float = 1.0,
) -> Dict[str, float]:
    """Train one epoch."""
    model.train()

    total_loss = 0
    total_recon = 0
    total_contrast = 0
    total_class = 0
    n_batches = 0

    for batch_x, batch_y in loader:
        optimizer.zero_grad()

        # Forward
        outputs = model(batch_x)

        # Compute losses
        loss_recon = reconstruction_loss(batch_x, outputs["x_recon"])
        loss_contrast = contrastive_loss(outputs["z"], batch_y)
        loss_class = classification_loss(outputs["logits"], batch_y, pos_weight)

        # Combined loss
        loss = (
            lambda_recon * loss_recon +
            lambda_contrast * loss_contrast +
            lambda_class * loss_class
        )

        # Backward
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()
        total_recon += loss_recon.item()
        total_contrast += loss_contrast.item()
        total_class += loss_class.item()
        n_batches += 1

    return {
        "loss": total_loss / n_batches,
        "recon": total_recon / n_batches,
        "contrast": total_contrast / n_batches,
        "class": total_class / n_batches,
    }


def evaluate(
    model: nn.Module,
    embeddings: torch.Tensor,
    labels: np.ndarray,
) -> Dict[str, float]:
    """Evaluate model."""
    model.eval()

    with torch.no_grad():
        outputs = model(embeddings)
        probs = torch.sigmoid(outputs["logits"]).numpy()
        preds = probs > 0.5

        recon_loss = reconstruction_loss(embeddings, outputs["x_recon"]).item()

    acc = accuracy_score(labels, preds)

    return {
        "accuracy": acc,
        "recon_loss": recon_loss,
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Train 128d projection")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lambda-recon", type=float, default=1.0)
    parser.add_argument("--lambda-contrast", type=float, default=0.5)
    parser.add_argument("--lambda-class", type=float, default=1.0)
    args = parser.parse_args()

    print("=" * 70)
    print("SWARM-06: Train 384d → 128d Projection")
    print("=" * 70)
    print("\nConfig:")
    print(f"  Epochs: {args.epochs}")
    print(f"  LR: {args.lr}")
    print(f"  λ_recon: {args.lambda_recon}")
    print(f"  λ_contrast: {args.lambda_contrast}")
    print(f"  λ_class: {args.lambda_class}")

    # Load data
    print("\n[1/4] Loading embeddings...")
    train_emb, val_emb, test_emb, train_labels, val_labels, test_labels = load_embeddings()

    print(f"  Train: {train_emb.shape}")
    print(f"  Val: {val_emb.shape}")
    print(f"  Test: {test_emb.shape}")

    # Convert to tensors
    train_tensor = torch.tensor(train_emb, dtype=torch.float32)
    train_labels_tensor = torch.tensor(train_labels, dtype=torch.float32)
    val_tensor = torch.tensor(val_emb, dtype=torch.float32)
    test_tensor = torch.tensor(test_emb, dtype=torch.float32)

    # Create model
    print("\n[2/4] Creating model...")
    model = ContrastiveProjectionModel()
    print(f"  Encoder params: {sum(p.numel() for p in model.encoder.parameters()):,}")
    print(f"  Total params: {sum(p.numel() for p in model.parameters()):,}")

    # Training setup
    dataset = TensorDataset(train_tensor, train_labels_tensor)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    pos_weight = (train_labels_tensor == 0).sum() / (train_labels_tensor == 1).sum()

    # Training
    print("\n[3/4] Training...")
    best_acc = 0
    best_state = None

    for epoch in range(args.epochs):
        metrics = train_epoch(
            model, loader, optimizer, pos_weight,
            args.lambda_recon, args.lambda_contrast, args.lambda_class
        )
        scheduler.step()

        # Evaluate
        val_metrics = evaluate(model, val_tensor, val_labels)

        if val_metrics["accuracy"] > best_acc:
            best_acc = val_metrics["accuracy"]
            best_state = model.encoder.state_dict().copy()

        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}/{args.epochs}: "
                  f"loss={metrics['loss']:.4f}, "
                  f"recon={metrics['recon']:.4f}, "
                  f"val_acc={val_metrics['accuracy']:.4f}")

    # Restore best
    model.encoder.load_state_dict(best_state)

    # Final evaluation
    print("\n[4/4] Final evaluation...")
    val_metrics = evaluate(model, val_tensor, val_labels)
    test_metrics = evaluate(model, test_tensor, test_labels)

    print(f"\n  Validation: acc={val_metrics['accuracy']:.4f}, recon={val_metrics['recon_loss']:.4f}")
    print(f"  Test:       acc={test_metrics['accuracy']:.4f}, recon={test_metrics['recon_loss']:.4f}")

    # Save encoder weights
    CHECKPOINTS_DIR.mkdir(exist_ok=True)

    # Local checkpoint
    local_path = CHECKPOINTS_DIR / "text_mlp_384to128_trained.pt"
    torch.save({
        "model_state_dict": model.encoder.state_dict(),
        "config": {
            "input_dim": 384,
            "output_dim": 128,
            "lambda_recon": args.lambda_recon,
            "lambda_contrast": args.lambda_contrast,
            "lambda_class": args.lambda_class,
        },
        "val_accuracy": val_metrics["accuracy"],
        "test_accuracy": test_metrics["accuracy"],
        "timestamp": datetime.now().isoformat(),
    }, local_path)
    print(f"\n  Saved: {local_path}")

    # Copy to YRSN checkpoints for DyTopo integration
    yrsn_path = YRSN_CHECKPOINTS / "text_mlp_384to128_trained.pt"
    torch.save({
        "model_state_dict": model.encoder.state_dict(),
    }, yrsn_path)
    print(f"  Saved: {yrsn_path}")

    # Summary
    print("\n" + "=" * 70)
    print("128d PROJECTION TRAINING COMPLETE")
    print("=" * 70)
    print("\nEncoder: 384d → 128d")
    print(f"Test accuracy: {test_metrics['accuracy']:.1%}")
    print(f"Reconstruction loss: {test_metrics['recon_loss']:.4f}")
    print("\nIntegration with yrsn.config.rotor_config:")
    print("  # Set dimension via environment:")
    print("  export ROTOR_DIMENSION=128")
    print("")
    print("  # DyTopo router auto-loads weights:")
    print("  from yrsn.config.rotor_config import ROTOR_DIMENSION")
    print("  router = DyTopoRouter.create()  # Uses ROTOR_DIMENSION")


if __name__ == "__main__":
    main()
