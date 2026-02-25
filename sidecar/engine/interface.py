"""
SGCI Interface - Clean boundary between sidecar and yrsn core.

First Principles:
- Sidecar is domain-agnostic (like Tendermint)
- Sidecar handles: API, pre-screening, metrics, multi-language access
- yrsn core handles: RSN computation, certificate generation, domain semantics

The sidecar NEVER computes R, S, N values. It delegates to yrsn.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum


class PreScreenResult(Enum):
    """Result of sidecar pre-screening (like Tendermint CheckTx)."""
    PASS = "pass"           # Continue to yrsn
    REJECT = "reject"       # Don't even call yrsn - obvious attack
    WARN = "warn"           # Pass to yrsn but flag patterns


@dataclass
class PreScreenOutput:
    """Output from sidecar pre-screening."""
    result: PreScreenResult
    patterns: List[str]         # Detected pattern categories
    max_severity: float         # 0-1, highest pattern score
    reason: Optional[str] = None


@dataclass
class CertifyRequest:
    """
    Request to certify a prompt.

    Sidecar accepts this, does pre-screening, then passes to yrsn.
    """
    prompt: str
    embeddings: Optional[List[float]] = None  # User-provided embeddings
    context: Optional[str] = None
    model_id: Optional[str] = None
    policy: str = "default"

    # Sidecar adds this after pre-screening
    pre_screen: Optional[PreScreenOutput] = None


@dataclass
class CertifyResponse:
    """
    Response from yrsn core.

    Sidecar passes this through, only adding metrics/observability.
    """
    # Certificate ID and metadata
    id: str
    timestamp: str

    # RSN simplex (computed by yrsn, NOT sidecar)
    R: float
    S: float
    N: float

    # Gate scores (computed by yrsn)
    kappa_gate: float
    sigma: float

    # Decision (made by yrsn)
    decision: str
    gate_reached: int
    reason: str
    allowed: bool

    # Multimodal (computed by yrsn)
    kappa_H: Optional[float] = None
    kappa_L: Optional[float] = None
    kappa_interface: Optional[float] = None
    weak_modality: Optional[str] = None
    is_multimodal: bool = False

    # Sidecar annotations (added by sidecar, not yrsn)
    pattern_flags: List[str] = None
    pre_screen_severity: Optional[float] = None


class YRSNAdapter(ABC):
    """
    Abstract interface to yrsn core.

    Sidecar calls this. Implementations:
    - LocalYRSNAdapter: Direct Python import (same process)
    - RemoteYRSNAdapter: HTTP/gRPC call to yrsn service
    - MockYRSNAdapter: For testing
    """

    @abstractmethod
    def certify(self, request: CertifyRequest) -> CertifyResponse:
        """
        Certify a prompt using yrsn core.

        The sidecar has already done pre-screening. This method:
        1. Gets embeddings if not provided
        2. Calls yrsn's RSN computation
        3. Returns the certificate

        Raises:
            EmbeddingsRequired: If embeddings needed but not available
            YRSNError: If yrsn computation fails
        """
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Check yrsn core health."""
        pass


class EmbeddingsRequired(Exception):
    """Raised when embeddings are required but not provided."""
    pass


class YRSNError(Exception):
    """Raised when yrsn core fails."""
    pass
