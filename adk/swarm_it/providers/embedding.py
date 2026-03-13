"""
Embedding Providers and Kappa Viability Checker for swarm-it-adk

Provides embedding extraction and kappa viability checking for geometric
operations on embeddings (rotors, merging, etc.).

Key Concepts:
- kappa (κ) = dim / stable_rank - over-parameterization ratio
- κ >= 50 required for rotors to have "room to rotate"
- When κ < 50, capacity expansion needed: k = min(ceil(65/κ), 5)

Usage:
    from swarm_it.providers.embedding import (
        SentenceTransformerProvider,
        KappaViabilityChecker,
        check_kappa,
    )

    # Get embeddings
    provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
    embeddings = provider.embed(texts)

    # Check kappa viability
    result = check_kappa(embeddings)
    print(f"κ = {result.kappa:.2f}, viable: {result.is_viable}")
    print(f"Recommended expansion: k = {result.recommended_k}")

References:
    - Adila et al., "Grow, Don't Overwrite" (arXiv:2603.08647)
    - SWARM-03: Phase 1 proof of kappa formula
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Union, Optional
import numpy as np

# Optional torch support
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@dataclass
class KappaResult:
    """Result of kappa viability check."""
    kappa: float
    stable_rank: float
    dim: int
    is_viable: bool  # kappa >= threshold (default 50)
    recommended_k: int  # Expansion factor: k = min(ceil(65/κ), 5)
    kappa_after_expansion: float  # κ * k
    threshold: float = 50.0

    def __repr__(self) -> str:
        status = "VIABLE" if self.is_viable else "CHOKED"
        return (
            f"KappaResult(κ={self.kappa:.2f} [{status}], "
            f"stable_rank={self.stable_rank:.2f}, dim={self.dim}, "
            f"k={self.recommended_k} → κ={self.kappa_after_expansion:.2f})"
        )


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Embedding dimension."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier."""
        pass

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for texts.

        Args:
            texts: List of text strings

        Returns:
            np.ndarray of shape [len(texts), dim]
        """
        pass


class SentenceTransformerProvider(EmbeddingProvider):
    """
    Embedding provider using sentence-transformers.

    Supported models:
        - all-MiniLM-L6-v2 (384-dim, fast)
        - all-MiniLM-L12-v2 (384-dim, deeper)
        - all-mpnet-base-v2 (768-dim, accurate)
        - paraphrase-MiniLM-L6-v2 (384-dim, paraphrase)
        - multi-qa-MiniLM-L6-cos-v1 (384-dim, QA)

    Usage:
        provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
        embeddings = provider.embed(["Hello world", "Goodbye world"])
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        """
        Initialize provider.

        Args:
            model_name: sentence-transformers model name
            device: torch device (cpu, cuda, mps)
        """
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name, device=device)
            self._model_name = model_name
            self._device = device
        except ImportError:
            raise ImportError(
                "sentence-transformers required. "
                "Install with: pip install sentence-transformers"
            )

    @property
    def dim(self) -> int:
        return self._model.get_sentence_embedding_dimension()

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.astype(np.float32)


def compute_stable_rank(embeddings: np.ndarray) -> float:
    """
    Compute stable rank from embeddings.

    stable_rank = trace(Cov) / max_eigenvalue(Cov)

    This measures the effective dimensionality of the embedding space.
    Lower stable_rank means more concentrated variance (fewer effective dims).

    Args:
        embeddings: Array of shape [n_samples, dim]

    Returns:
        Stable rank (float >= 1.0)
    """
    if len(embeddings) < 2:
        return 1.0

    # Center embeddings
    centered = embeddings - embeddings.mean(axis=0)

    # Compute covariance matrix
    cov = centered.T @ centered / (len(embeddings) - 1)

    # Eigenvalues
    eigenvalues = np.linalg.eigvalsh(cov)
    eigenvalues = np.maximum(eigenvalues, 1e-10)

    # Stable rank = trace / max eigenvalue
    stable_rank = eigenvalues.sum() / eigenvalues.max()

    return float(stable_rank)


def compute_kappa(
    embeddings: np.ndarray,
    threshold: float = 50.0,
) -> KappaResult:
    """
    Compute kappa viability for embeddings.

    κ = dim / stable_rank

    When κ < threshold, geometric operations (rotors, merging) may fail.
    Use recommended_k to expand capacity via Adila et al.'s method.

    Args:
        embeddings: Array of shape [n_samples, dim]
        threshold: Minimum κ for viability (default 50.0)

    Returns:
        KappaResult with viability info and expansion recommendation
    """
    dim = embeddings.shape[1]
    stable_rank = compute_stable_rank(embeddings)
    kappa = dim / stable_rank

    # Our formula: k = min(ceil(65/κ), 5)
    if kappa >= threshold:
        recommended_k = 1
    else:
        recommended_k = min(math.ceil(65 / kappa), 5)

    kappa_after = kappa * recommended_k
    is_viable = kappa >= threshold

    return KappaResult(
        kappa=kappa,
        stable_rank=stable_rank,
        dim=dim,
        is_viable=is_viable,
        recommended_k=recommended_k,
        kappa_after_expansion=kappa_after,
        threshold=threshold,
    )


def check_kappa(
    embeddings: Union[np.ndarray, "torch.Tensor", List[List[float]]],
    threshold: float = 50.0,
) -> KappaResult:
    """
    Check kappa viability for embeddings (convenience function).

    Accepts numpy arrays, torch tensors, or nested lists.

    Args:
        embeddings: Embeddings in various formats
        threshold: Minimum κ for viability

    Returns:
        KappaResult

    Example:
        >>> result = check_kappa(embeddings)
        >>> if not result.is_viable:
        ...     print(f"Expand by k={result.recommended_k}")
    """
    # Convert to numpy
    if HAS_TORCH and isinstance(embeddings, torch.Tensor):
        embeddings = embeddings.cpu().numpy()
    elif isinstance(embeddings, list):
        embeddings = np.array(embeddings)

    return compute_kappa(embeddings, threshold)


class KappaViabilityChecker:
    """
    Checker for kappa viability with configurable thresholds.

    Useful for pre-flight checks before geometric operations.

    Usage:
        checker = KappaViabilityChecker(threshold=50.0)

        # Check single batch
        result = checker.check(embeddings)
        if not result.is_viable:
            print(f"Need expansion: k={result.recommended_k}")

        # Check provider
        provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
        result = checker.check_provider(provider, sample_texts)
    """

    def __init__(
        self,
        threshold: float = 50.0,
        max_k: int = 5,
    ):
        """
        Initialize checker.

        Args:
            threshold: Minimum κ for viability
            max_k: Maximum expansion factor
        """
        self.threshold = threshold
        self.max_k = max_k

    def check(
        self,
        embeddings: Union[np.ndarray, "torch.Tensor", List[List[float]]],
    ) -> KappaResult:
        """Check kappa viability for embeddings."""
        return check_kappa(embeddings, self.threshold)

    def check_provider(
        self,
        provider: EmbeddingProvider,
        sample_texts: List[str],
    ) -> KappaResult:
        """
        Check kappa viability for an embedding provider.

        Args:
            provider: Embedding provider to check
            sample_texts: Sample texts to embed (recommend 100+)

        Returns:
            KappaResult for the provider
        """
        embeddings = provider.embed(sample_texts)
        return self.check(embeddings)

    def optimal_k(self, kappa: float) -> int:
        """
        Compute optimal expansion factor k.

        Formula: k = min(ceil(65/κ), max_k)

        Args:
            kappa: Current kappa value

        Returns:
            Recommended k (1 if already viable)
        """
        if kappa >= self.threshold:
            return 1
        return min(math.ceil(65 / kappa), self.max_k)


# Convenience exports
__all__ = [
    # Providers
    "EmbeddingProvider",
    "SentenceTransformerProvider",

    # Kappa checking
    "KappaViabilityChecker",
    "KappaResult",
    "compute_kappa",
    "compute_stable_rank",
    "check_kappa",
]
