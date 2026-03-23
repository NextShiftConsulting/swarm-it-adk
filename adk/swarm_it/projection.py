"""
Dimension Projection Layer with Contract Enforcement (Profile B)

Implements P18: Hardware Compression Target Is Explicit and Versioned

This module provides dimension reduction for hardware-efficient deployment
(e.g., 1024d → 64d for memristor crossbars). The projection path is protected
by dimension contracts and mandatory checkpoint validation.

IMPORTANT: This module is ONLY used for Profile B (COMPACT_64_MULTIMODAL).
Profile A (TRACK2_NATIVE_1024) uses native 1024-dim and skips projection.

Reference:
  - FIRST_PRINCIPLES_v3_MODERN.md - PRINCIPLE 18
  - docs/ADR_HARDWARE_COMPRESSION_PROFILES.md
"""

import os
import yaml
import torch
import torch.nn as nn
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Import profile system
try:
    from .profiles import SwarmProfile
except ImportError:
    SwarmProfile = None  # Fallback if profiles not available


@dataclass
class DimensionContract:
    """Dimension contract loaded from YAML."""
    input_dim: int
    output_dim: int
    reason: str
    checkpoint: str
    enabled: bool
    fallback_policy: str

    @classmethod
    def load(cls, contract_path: Optional[Path] = None) -> "DimensionContract":
        """
        Load dimension contract from YAML.

        Args:
            contract_path: Path to dimension_contract.yaml (auto-detects if None)

        Returns:
            DimensionContract instance

        Raises:
            FileNotFoundError: If contract file not found
            ValueError: If contract is invalid or disabled
        """
        if contract_path is None:
            # Auto-detect contract path relative to this file
            contract_path = Path(__file__).parent.parent.parent / "config" / "dimension_contract.yaml"

        if not contract_path.exists():
            raise FileNotFoundError(
                f"P18 VIOLATION: Dimension contract not found at {contract_path}. "
                f"Hardware compression requires explicit dimension contract."
            )

        with open(contract_path, "r") as f:
            contract = yaml.safe_load(f)

        compression = contract.get("compression", {})

        if not compression.get("enabled", False):
            raise ValueError(
                "P18 VIOLATION: Compression disabled in dimension contract. "
                "Cannot proceed without explicit dimension targets."
            )

        return cls(
            input_dim=compression["input"]["dimension"],
            output_dim=compression["output"]["dimension"],
            reason=compression["reason"],
            checkpoint=compression["projection_layer"]["checkpoint"],
            enabled=compression["enabled"],
            fallback_policy=compression["projection_layer"]["fallback_policy"],
        )


class ProjectionLayer(nn.Module):
    """
    Learned dimension projection for hardware compression.

    Enforces P18 compliance:
    - Dimensions match declared contract
    - Checkpoint must exist and be loaded
    - No identity or random fallback in production
    - Fail-fast on dimension mismatch

    Usage:
        >>> projection = get_projection_layer()
        >>> embeddings_64d = projection(embeddings_1024d)
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        checkpoint_path: Optional[Path] = None,
        contract: Optional[DimensionContract] = None,
    ):
        """
        Initialize projection layer.

        Args:
            input_dim: Input dimension (e.g., 1024)
            output_dim: Output dimension (e.g., 64)
            checkpoint_path: Path to trained checkpoint
            contract: Dimension contract (auto-loads if None)

        Raises:
            ValueError: If dimensions don't match contract
            FileNotFoundError: If checkpoint not found
        """
        super().__init__()

        # Load contract if not provided
        if contract is None:
            contract = DimensionContract.load()

        self.contract = contract
        self.input_dim = input_dim
        self.output_dim = output_dim
        self._checkpoint_loaded = False

        # Validate dimensions match contract
        if input_dim != contract.input_dim:
            raise ValueError(
                f"P18 VIOLATION: Input dimension {input_dim} does not match "
                f"contract dimension {contract.input_dim}. "
                f"See config/dimension_contract.yaml"
            )

        if output_dim != contract.output_dim:
            raise ValueError(
                f"P18 VIOLATION: Output dimension {output_dim} does not match "
                f"contract dimension {contract.output_dim}. "
                f"See config/dimension_contract.yaml"
            )

        # Define projection layer
        self.projection = nn.Linear(input_dim, output_dim, bias=True)

        # Load checkpoint if provided
        if checkpoint_path is not None:
            self._load_checkpoint(checkpoint_path)
        else:
            # Enforce no-fallback policy in production
            if contract.fallback_policy == "FAIL_FAST":
                raise ValueError(
                    f"P18 VIOLATION: No checkpoint provided and fallback policy is FAIL_FAST. "
                    f"Production deployment requires trained checkpoint: {contract.checkpoint}"
                )

    def _load_checkpoint(self, checkpoint_path: Path):
        """
        Load trained checkpoint.

        Args:
            checkpoint_path: Path to .pt checkpoint file

        Raises:
            FileNotFoundError: If checkpoint not found
            RuntimeError: If checkpoint is invalid or corrupted
        """
        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"P18 VIOLATION: Projection checkpoint not found at {checkpoint_path}. "
                f"Cannot proceed without trained projection layer."
            )

        try:
            state_dict = torch.load(checkpoint_path, map_location="cpu")

            # Handle wrapped checkpoint format (if exists)
            if "projection" in state_dict:
                state_dict = state_dict["projection"]

            self.projection.load_state_dict(state_dict, strict=True)
            self._checkpoint_loaded = True

        except Exception as e:
            raise RuntimeError(
                f"P18 VIOLATION: Failed to load projection checkpoint from {checkpoint_path}. "
                f"Error: {e}"
            )

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        """
        Project embeddings to target dimension.

        Args:
            embeddings: Input embeddings (batch_size, input_dim)

        Returns:
            Projected embeddings (batch_size, output_dim)

        Raises:
            ValueError: If input dimension doesn't match
        """
        if embeddings.shape[-1] != self.input_dim:
            raise ValueError(
                f"P18 VIOLATION: Input embedding dimension {embeddings.shape[-1]} "
                f"does not match projection input dimension {self.input_dim}"
            )

        return self.projection(embeddings)

    def checkpoint_loaded(self) -> bool:
        """Check if trained checkpoint is loaded."""
        return self._checkpoint_loaded

    def is_trained(self) -> bool:
        """Alias for checkpoint_loaded() - required by tests."""
        return self._checkpoint_loaded

    def get_contract_info(self) -> Dict[str, Any]:
        """Get dimension contract information."""
        return {
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "checkpoint": self.contract.checkpoint,
            "reason": self.contract.reason,
            "checkpoint_loaded": self._checkpoint_loaded,
        }


# Singleton pattern for projection layer
_projection_layer_singleton: Optional[ProjectionLayer] = None


def get_projection_layer(
    checkpoint_path: Optional[Path] = None,
    force_reload: bool = False,
) -> ProjectionLayer:
    """
    Get singleton projection layer instance.

    This ensures startup validation = runtime instance (P18 compliance).

    Args:
        checkpoint_path: Path to trained checkpoint (auto-detects if None)
        force_reload: Force reload projection layer

    Returns:
        ProjectionLayer singleton instance

    Raises:
        FileNotFoundError: If checkpoint not found
        ValueError: If dimension contract invalid
    """
    global _projection_layer_singleton

    if _projection_layer_singleton is None or force_reload:
        # Load dimension contract
        contract = DimensionContract.load()

        # Auto-detect checkpoint path if not provided
        if checkpoint_path is None:
            # Look for checkpoint in checkpoints directory
            checkpoint_dir = Path(__file__).parent.parent.parent / "checkpoints"
            checkpoint_path = checkpoint_dir / contract.checkpoint

            # Fallback: check relative to this file
            if not checkpoint_path.exists():
                checkpoint_path = Path(__file__).parent / "checkpoints" / contract.checkpoint

        # Create projection layer with contract enforcement
        _projection_layer_singleton = ProjectionLayer(
            input_dim=contract.input_dim,
            output_dim=contract.output_dim,
            checkpoint_path=checkpoint_path,
            contract=contract,
        )

    return _projection_layer_singleton


def validate_projection_at_startup() -> Dict[str, Any]:
    """
    Validate projection layer at startup.

    This is called by main.py or app factory to ensure P18 compliance
    before allowing server to start.

    Returns:
        Validation results dict

    Raises:
        Exception: If validation fails (fail-fast)
    """
    try:
        projection = get_projection_layer()

        validation = {
            "status": "PASS",
            "contract": projection.get_contract_info(),
            "checkpoint_loaded": projection.checkpoint_loaded(),
            "input_dim": projection.input_dim,
            "output_dim": projection.output_dim,
        }

        if not projection.checkpoint_loaded():
            validation["status"] = "FAIL"
            validation["error"] = "Projection checkpoint not loaded"
            raise RuntimeError(
                "P18 VIOLATION: Projection checkpoint not loaded at startup. "
                "Cannot start server without trained projection layer."
            )

        return validation

    except Exception as e:
        raise RuntimeError(f"P18 startup validation failed: {e}")


def project_to_target_dim(embeddings: torch.Tensor) -> torch.Tensor:
    """
    Convenience function to project embeddings to target dimension.

    Args:
        embeddings: Input embeddings (batch_size, input_dim)

    Returns:
        Projected embeddings (batch_size, output_dim)
    """
    projection = get_projection_layer()
    return projection(embeddings)
