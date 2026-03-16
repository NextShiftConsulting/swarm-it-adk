#!/usr/bin/env python3
"""
SWARM-06: Swarm-Based Parallel Training with Bedrock Titan Embeddings

Uses MIMO agents to coordinate parallel embedding extraction via Bedrock Titan v2.

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │                 MIMO Coordinator Agent                   │
    │  (shards data, dispatches to workers, aggregates)        │
    ├─────────────────────────────────────────────────────────┤
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
    │  │Worker 1 │  │Worker 2 │  │Worker 3 │  │Worker N │    │
    │  │Shard 0  │  │Shard 1  │  │Shard 2  │  │Shard N  │    │
    │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘    │
    │       └───────────────┬─────────────────────┘          │
    │                       ▼                                 │
    │           Bedrock Titan v2 Embeddings                   │
    │           (configurable: 256/512/1024/1536d)            │
    └─────────────────────────────────────────────────────────┘

Usage:
    python train_swarm_titan.py --workers 5 --embed-dim 1024
    python train_swarm_titan.py --workers 10 --embed-dim 512 --batch-size 100

Reference: MIMO LangGraph Swarm Architecture (CLAUDE.md)
"""

import json
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import logging

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

# Paths
EXPERIMENT_DIR = Path(__file__).parent.parent
DATA_DIR = EXPERIMENT_DIR / "data"
CHECKPOINTS_DIR = EXPERIMENT_DIR / "checkpoints"
EVIDENCE_DIR = EXPERIMENT_DIR / "evidence"
EMBEDDINGS_DIR = EXPERIMENT_DIR / "embeddings"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# BEDROCK TITAN v2 EMBEDDINGS
# =============================================================================

class TitanEmbedder:
    """
    Bedrock Titan Embeddings v2 with configurable dimensions.

    Supports: 256, 512, 1024, 1536 dimensions
    """

    SUPPORTED_DIMS = [256, 512, 1024, 1536]
    MODEL_ID = "amazon.titan-embed-text-v2:0"

    def __init__(self, embed_dim: int = 1024, region: str = "us-west-2"):
        if embed_dim not in self.SUPPORTED_DIMS:
            raise ValueError(f"embed_dim must be one of {self.SUPPORTED_DIMS}")

        self.embed_dim = embed_dim
        self.region = region
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            # Use config_manager per P17
            try:
                sys.path.insert(0, str(Path("/Users/rudy/GitHub/yrsn/src")))
                from yrsn.keys.config_manager import get_config
                config = get_config()
                session = boto3.Session(
                    aws_access_key_id=config.aws_access_key_id,
                    aws_secret_access_key=config.aws_secret_access_key,
                    region_name=self.region,
                )
            except Exception:
                # Fallback to default credentials
                session = boto3.Session(region_name=self.region)

            self._client = session.client("bedrock-runtime")
        return self._client

    def embed(self, text: str) -> np.ndarray:
        """Embed single text."""
        # Titan v2 has 8192 token limit (~6k chars safely)
        if len(text) > 6000:
            text = text[:6000]

        body = {
            "inputText": text,
            "dimensions": self.embed_dim,
            "normalize": True,
        }

        response = self.client.invoke_model(
            modelId=self.MODEL_ID,
            body=json.dumps(body),
        )

        response_body = json.loads(response["body"].read())
        return np.array(response_body["embedding"])

    def embed_batch(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """Embed batch of texts (sequential, for comparison)."""
        embeddings = []
        for i, text in enumerate(texts):
            emb = self.embed(text)
            embeddings.append(emb)
            if show_progress and (i + 1) % 100 == 0:
                logger.info(f"  Embedded {i+1}/{len(texts)}")
        return np.array(embeddings)


# =============================================================================
# PARALLEL WORKER (for swarm)
# =============================================================================

def embed_shard(
    shard_id: int,
    texts: List[str],
    embed_dim: int,
    region: str,
) -> Tuple[int, np.ndarray]:
    """
    Worker function to embed a shard of texts.

    Each worker creates its own Titan client for parallel processing.
    """
    logger.info(f"Worker {shard_id}: Starting ({len(texts)} texts, {embed_dim}d)")

    embedder = TitanEmbedder(embed_dim=embed_dim, region=region)
    embeddings = embedder.embed_batch(texts, show_progress=False)

    logger.info(f"Worker {shard_id}: Complete")
    return shard_id, embeddings


class SwarmEmbedder:
    """
    Swarm-based parallel embedding using multiple workers.
    """

    def __init__(
        self,
        n_workers: int = 5,
        embed_dim: int = 1024,
        region: str = "us-west-2",
    ):
        self.n_workers = n_workers
        self.embed_dim = embed_dim
        self.region = region

    def embed_parallel(self, texts: List[str]) -> np.ndarray:
        """
        Embed texts in parallel using worker swarm.
        """
        # Shard data
        shard_size = len(texts) // self.n_workers
        shards = []
        for i in range(self.n_workers):
            start = i * shard_size
            end = start + shard_size if i < self.n_workers - 1 else len(texts)
            shards.append(texts[start:end])

        logger.info(f"Sharded {len(texts)} texts into {self.n_workers} shards")

        # Process in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=self.n_workers) as executor:
            futures = {
                executor.submit(
                    embed_shard,
                    shard_id=i,
                    texts=shard,
                    embed_dim=self.embed_dim,
                    region=self.region,
                ): i
                for i, shard in enumerate(shards)
            }

            for future in as_completed(futures):
                shard_id, embeddings = future.result()
                results[shard_id] = embeddings

        # Reassemble in order
        all_embeddings = [results[i] for i in range(self.n_workers)]
        return np.vstack(all_embeddings)


# =============================================================================
# CLASSIFIER
# =============================================================================

class JailbreakClassifier(nn.Module):
    """MLP classifier for jailbreak detection."""

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


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(split: str) -> Tuple[List[str], List[bool]]:
    """Load data from unified dataset."""
    path = DATA_DIR / f"unified_{split}.jsonl"
    texts, labels = [], []
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            texts.append(row["text"])
            labels.append(row["is_jailbreak"])
    return texts, labels


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
    """Train the classifier."""

    classifier.train()

    dataset = TensorDataset(train_emb, train_labels.float())
    loader = DataLoader(dataset, batch_size=64, shuffle=True)

    optimizer = torch.optim.AdamW(classifier.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    pos_weight = (train_labels == 0).sum() / (train_labels == 1).sum()
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    best_f1 = 0
    best_state = None
    history = {"loss": [], "val_f1": []}

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
        history["loss"].append(epoch_loss / len(dataset))
        history["val_f1"].append(val_f1)

        if val_f1 > best_f1:
            best_f1 = val_f1
            best_state = classifier.state_dict().copy()

        if (epoch + 1) % 20 == 0:
            logger.info(f"  Epoch {epoch+1}/{epochs}: loss={epoch_loss/len(dataset):.4f}, val_f1={val_f1:.4f}")

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
        "f1_score": float(f1_score(labels, preds)),
        "auc": float(roc_auc_score(labels, probs)),
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Swarm Titan Jailbreak Classifier")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel workers")
    parser.add_argument("--embed-dim", type=int, default=1024, choices=[256, 512, 1024, 1536])
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--region", type=str, default="us-west-2")
    parser.add_argument("--use-cached", action="store_true", help="Use cached embeddings if available")
    args = parser.parse_args()

    print("=" * 70)
    print("SWARM-06: SWARM TITAN JAILBREAK CLASSIFIER")
    print("=" * 70)
    print(f"\nConfig:")
    print(f"  Workers: {args.workers}")
    print(f"  Embed dim: {args.embed_dim}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Region: {args.region}")

    # Check for cached embeddings
    EMBEDDINGS_DIR.mkdir(exist_ok=True)
    cache_path = EMBEDDINGS_DIR / f"titan_v2_{args.embed_dim}d.npz"

    if args.use_cached and cache_path.exists():
        print(f"\n[1/4] Loading cached embeddings from {cache_path}")
        data = np.load(cache_path)
        train_emb = data["train_emb"]
        val_emb = data["val_emb"]
        test_emb = data["test_emb"]
        train_labels = data["train_labels"]
        val_labels = data["val_labels"]
        test_labels = data["test_labels"]
    else:
        # Load data
        print("\n[1/4] Loading data...")
        train_texts, train_labels = load_data("train")
        val_texts, val_labels = load_data("val")
        test_texts, test_labels = load_data("test")

        train_labels = np.array(train_labels)
        val_labels = np.array(val_labels)
        test_labels = np.array(test_labels)

        print(f"  Train: {len(train_texts)} ({np.sum(train_labels)} jailbreak)")
        print(f"  Val:   {len(val_texts)} ({np.sum(val_labels)} jailbreak)")
        print(f"  Test:  {len(test_texts)} ({np.sum(test_labels)} jailbreak)")

        # Parallel embedding extraction
        print(f"\n[2/4] Extracting embeddings (swarm: {args.workers} workers)...")
        swarm = SwarmEmbedder(
            n_workers=args.workers,
            embed_dim=args.embed_dim,
            region=args.region,
        )

        print("  Training set:")
        train_emb = swarm.embed_parallel(train_texts)
        print("  Validation set:")
        val_emb = swarm.embed_parallel(val_texts)
        print("  Test set:")
        test_emb = swarm.embed_parallel(test_texts)

        # Cache embeddings
        print(f"\n  Caching embeddings to {cache_path}")
        np.savez(
            cache_path,
            train_emb=train_emb,
            val_emb=val_emb,
            test_emb=test_emb,
            train_labels=train_labels,
            val_labels=val_labels,
            test_labels=test_labels,
        )

    # Create classifier
    print(f"\n[3/4] Training classifier ({args.embed_dim}d input)...")
    classifier = JailbreakClassifier(input_dim=args.embed_dim)
    print(f"  Parameters: {sum(p.numel() for p in classifier.parameters()):,}")

    classifier, history = train_classifier(
        classifier=classifier,
        train_emb=torch.tensor(train_emb, dtype=torch.float32),
        train_labels=torch.tensor(train_labels),
        val_emb=torch.tensor(val_emb, dtype=torch.float32),
        val_labels=torch.tensor(val_labels),
        epochs=args.epochs,
    )

    # Evaluate
    print("\n[4/4] Evaluating...")
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
    print(f"\nValidation: acc={val_results['accuracy']:.4f}, f1={val_results['f1_score']:.4f}, auc={val_results['auc']:.4f}")
    print(f"Test:       acc={test_results['accuracy']:.4f}, f1={test_results['f1_score']:.4f}, auc={test_results['auc']:.4f}")

    # Save
    CHECKPOINTS_DIR.mkdir(exist_ok=True)
    checkpoint_path = CHECKPOINTS_DIR / f"swarm_titan_{args.embed_dim}d.pt"
    torch.save({
        "model_state_dict": classifier.state_dict(),
        "config": {
            "embed_dim": args.embed_dim,
            "model": "amazon.titan-embed-text-v2:0",
            "workers": args.workers,
        },
        "val_results": val_results,
        "test_results": test_results,
        "timestamp": datetime.now().isoformat(),
    }, checkpoint_path)
    print(f"\nSaved: {checkpoint_path}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY (SWARM TITAN)")
    print("=" * 70)
    print(f"Target: Accuracy > 90%")
    print(f"Achieved: {test_results['accuracy']:.1%}")
    print(f"Status: {'PASS' if test_results['accuracy'] > 0.90 else 'NEEDS WORK'}")


if __name__ == "__main__":
    main()
