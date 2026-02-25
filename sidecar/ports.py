"""
Ports - Interfaces the SDK needs.

Hex arch: SDK defines WHAT it needs, not HOW to get it.
Adapters (configured at runtime) provide implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class EmbeddingPort(ABC):
    """Port: Get embeddings for text."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return embedding vector."""
        pass


class RSNPort(ABC):
    """Port: Compute RSN from embeddings."""

    @abstractmethod
    def compute(self, embeddings: List[float]) -> Dict[str, float]:
        """Return {R, S, N} dict."""
        pass


class CertifyPort(ABC):
    """Port: Full certification."""

    @abstractmethod
    def certify(self, prompt: str) -> Dict[str, Any]:
        """Return certificate."""
        pass
