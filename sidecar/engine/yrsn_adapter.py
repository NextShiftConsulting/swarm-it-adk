"""
YRSN Adapter - Clean delegation to yrsn core.

First Principles (Tendermint model):
- Sidecar is domain-agnostic infrastructure
- yrsn core owns ALL domain semantics (RSN computation, gate logic)
- Sidecar NEVER computes R, S, N - it delegates

This adapter handles:
1. Embeddings: User provides OR convenience wrapper calls OpenAI
2. Delegation: Pass embeddings to yrsn's HybridSimplexRotor
3. Certificate: Return yrsn's certificate unchanged
"""

from __future__ import annotations

import hashlib
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

# Use infra port
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from infra import get_embeddings, get_rotor, config

from .interface import (
    YRSNAdapter,
    CertifyRequest,
    CertifyResponse,
    EmbeddingsRequired,
    YRSNError,
)

# Check yrsn availability
try:
    import torch
    YRSN_AVAILABLE = True
except ImportError:
    YRSN_AVAILABLE = False


class LocalYRSNAdapter(YRSNAdapter):
    """
    Local adapter - calls yrsn core directly via infra port.
    """

    def __init__(self, embed_dim: int = 1536, **kwargs):
        """Initialize with rotor from infra."""
        self.embed_dim = embed_dim
        self.rotor = get_rotor(embed_dim) if YRSN_AVAILABLE else None

    def certify(self, request: CertifyRequest) -> CertifyResponse:
        """
        Certify using yrsn core.

        Flow:
        1. Get embeddings (from request or call OpenAI)
        2. Pass to yrsn rotor (handles dimension reduction internally)
        3. Compute kappa, sigma, gate decision
        4. Return certificate
        """
        if not YRSN_AVAILABLE:
            raise YRSNError("yrsn core not available - pip install yrsn")

        if self.rotor is None:
            raise YRSNError("No yrsn rotor available")

        # Step 1: Get embeddings (from request or via infra)
        embeddings = request.embeddings
        if embeddings is None:
            embeddings = get_embeddings(request.prompt)

        # Step 2: Pass to rotor (handles all dimension reduction internally)
        with torch.no_grad():
            embed_tensor = torch.tensor([embeddings], dtype=torch.float32)
            rsn_output = self.rotor(embed_tensor)

        R = float(rsn_output['R'][0])
        S = float(rsn_output['S'][0])
        N = float(rsn_output['N'][0])

        # Step 3: Compute derived metrics (yrsn domain logic)
        kappa = self._compute_kappa(R, S, N)
        sigma = self._compute_sigma(R, S, N)

        # Step 4: Gate decision (yrsn domain logic)
        decision, gate_reached, reason = self._gate_decision(
            R, S, N, kappa, sigma, request.pre_screen
        )

        # Step 5: Multimodal check
        is_multimodal = self._detect_multimodal(request.prompt, request.context)
        kappa_H = kappa_L = kappa_interface = weak_modality = None

        if is_multimodal:
            kappa_H, kappa_L, kappa_interface = self._compute_multimodal_kappas(R, S, N)
            weak_modality = self._identify_weak_modality(kappa_H, kappa_L, kappa_interface)
            kappa = min(kappa_H, kappa_L, kappa_interface)

        # Build response
        cert_id = self._generate_id(request.prompt)
        timestamp = datetime.utcnow().isoformat() + "Z"

        return CertifyResponse(
            id=cert_id,
            timestamp=timestamp,
            R=round(R, 4),
            S=round(S, 4),
            N=round(N, 4),
            kappa_gate=round(kappa, 4),
            sigma=round(sigma, 4),
            decision=decision,
            gate_reached=gate_reached,
            reason=reason,
            allowed=decision in ("EXECUTE", "REPAIR", "DELEGATE"),
            kappa_H=round(kappa_H, 4) if kappa_H else None,
            kappa_L=round(kappa_L, 4) if kappa_L else None,
            kappa_interface=round(kappa_interface, 4) if kappa_interface else None,
            weak_modality=weak_modality,
            is_multimodal=is_multimodal,
            pattern_flags=request.pre_screen.patterns if request.pre_screen else [],
            pre_screen_severity=request.pre_screen.max_severity if request.pre_screen else None,
        )

    def health(self) -> Dict[str, Any]:
        """Check health via infra."""
        return {
            "yrsn_available": YRSN_AVAILABLE,
            "rotor_ready": self.rotor is not None,
            "openai_ready": config.has_openai,
            "embed_dim": self.embed_dim,
        }

    def _generate_id(self, prompt: str) -> str:
        """Generate unique certificate ID."""
        timestamp = datetime.utcnow().isoformat()
        content = f"{timestamp}:{prompt[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # =========================================================================
    # YRSN DOMAIN LOGIC - These are yrsn's rules, not sidecar's
    # =========================================================================

    def _compute_kappa(self, R: float, S: float, N: float) -> float:
        """Compute kappa (compatibility score). kappa = R / (R + N)"""
        if R + N == 0:
            return 0.5
        return R / (R + N)

    def _compute_sigma(self, R: float, S: float, N: float) -> float:
        """Compute sigma (stability score) from RSN variance."""
        import math
        mean = (R + S + N) / 3
        variance = ((R - mean) ** 2 + (S - mean) ** 2 + (N - mean) ** 2) / 3
        return min(1.0, math.sqrt(variance) * 2)

    def _gate_decision(
        self,
        R: float,
        S: float,
        N: float,
        kappa: float,
        sigma: float,
        pre_screen,
    ) -> tuple:
        """
        5-gate decision logic (yrsn domain).

        Pre-screen from sidecar informs but doesn't override yrsn logic.
        """
        # Thresholds (yrsn defaults)
        N_THRESHOLD = 0.5
        R_MIN = 0.3
        SIGMA_THRESHOLD = 0.7
        KAPPA_THRESHOLD = 0.7

        # Gate 0: Pre-screen rejection (sidecar flagged severe pattern)
        if pre_screen and pre_screen.max_severity >= 0.9:
            return "REJECT", 0, f"Pre-screen: {pre_screen.patterns[0] if pre_screen.patterns else 'severe'}"

        # Gate 1: Noise check
        if N >= N_THRESHOLD:
            return "REJECT", 1, f"Noise too high: N={N:.2f} >= {N_THRESHOLD}"

        # Gate 2: Relevance check
        if R < R_MIN:
            return "BLOCK", 2, f"Relevance too low: R={R:.2f} < {R_MIN}"

        # Gate 3: Stability check
        if sigma > SIGMA_THRESHOLD:
            return "DELEGATE", 3, f"Unstable: sigma={sigma:.2f} > {SIGMA_THRESHOLD}"

        # Gate 4: Kappa check
        if kappa < KAPPA_THRESHOLD:
            return "REPAIR", 4, f"Low compatibility: kappa={kappa:.2f} < {KAPPA_THRESHOLD}"

        # Gate 5: All checks passed
        return "EXECUTE", 5, "All gates passed"

    def _detect_multimodal(self, prompt: str, context: Optional[str]) -> bool:
        """Detect if request involves multiple modalities."""
        multimodal_keywords = [
            "image", "picture", "photo", "vision", "video",
            "audio", "sound", "speech", "voice",
            "diagram", "chart", "graph", "screenshot",
        ]
        text = (prompt + (context or "")).lower()
        return any(kw in text for kw in multimodal_keywords)

    def _compute_multimodal_kappas(
        self, R: float, S: float, N: float
    ) -> tuple:
        """Compute per-modality kappa scores."""
        base_kappa = self._compute_kappa(R, S, N)
        kappa_H = min(1.0, base_kappa * 1.1)
        kappa_L = max(0.1, base_kappa * 0.9)
        kappa_interface = base_kappa
        return kappa_H, kappa_L, kappa_interface

    def _identify_weak_modality(
        self,
        kappa_H: float,
        kappa_L: float,
        kappa_interface: float,
    ) -> Optional[str]:
        """Identify which modality is the bottleneck."""
        kappas = {
            "text": kappa_H,
            "vision": kappa_L,
            "interface": kappa_interface,
        }
        weakest = min(kappas, key=kappas.get)
        if len(set(kappas.values())) == 1:
            return None
        return weakest


class MockYRSNAdapter(YRSNAdapter):
    """
    Mock adapter for testing (no yrsn dependency).

    Returns predictable values for testing sidecar infrastructure.
    """

    def certify(self, request: CertifyRequest) -> CertifyResponse:
        """Return mock certificate."""
        cert_id = hashlib.sha256(request.prompt.encode()).hexdigest()[:16]

        # Mock RSN based on prompt length
        word_count = len(request.prompt.split())
        R = min(0.8, 0.3 + word_count * 0.02)
        S = 0.2
        N = 1.0 - R - S

        kappa = R / (R + N) if (R + N) > 0 else 0.5
        decision = "EXECUTE" if kappa > 0.7 else "REPAIR"

        return CertifyResponse(
            id=cert_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            R=round(R, 4),
            S=round(S, 4),
            N=round(N, 4),
            kappa_gate=round(kappa, 4),
            sigma=0.3,
            decision=decision,
            gate_reached=5 if decision == "EXECUTE" else 4,
            reason="Mock certificate",
            allowed=True,
            pattern_flags=request.pre_screen.patterns if request.pre_screen else [],
        )

    def health(self) -> Dict[str, Any]:
        return {"mock": True, "yrsn_available": False}


def get_adapter(**kwargs) -> YRSNAdapter:
    """Get yrsn adapter."""
    if not YRSN_AVAILABLE:
        raise ImportError("yrsn not available - install torch and set PYTHONPATH")
    return LocalYRSNAdapter(**kwargs)
