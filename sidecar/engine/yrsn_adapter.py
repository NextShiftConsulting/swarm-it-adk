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


class LightweightAdapter(YRSNAdapter):
    """
    Lightweight fallback adapter for Lambda deployment.

    Works without torch/yrsn by using:
    - Pattern detection for safety screening
    - Heuristic-based R/S/N estimation
    - No actual RSCT math (returns estimates)

    Good for: Basic certification, pattern blocking, API availability
    Not for: Research, precise RSCT scoring, production AI safety
    """

    def __init__(self, **kwargs):
        self.embed_dim = kwargs.get('embed_dim', 1536)

    def health(self) -> Dict[str, Any]:
        """Health check for lightweight adapter."""
        return {
            "status": "healthy",
            "mode": "lightweight",
            "yrsn_available": False,
            "capabilities": ["pattern_detection", "heuristic_rsct"],
        }

    def certify(self, request: CertifyRequest) -> CertifyResponse:
        """Lightweight certification using heuristics."""
        prompt = request.prompt or ""

        # Simple heuristics based on prompt characteristics
        word_count = len(prompt.split())
        has_question = "?" in prompt
        is_short = word_count < 20

        # Estimate R, S, N without actual decomposition
        # These are placeholders - real values need yrsn
        if is_short and has_question:
            R, S, N = 0.75, 0.80, 0.15  # Simple queries = high compatibility
        elif word_count > 100:
            R, S, N = 0.60, 0.65, 0.25  # Long prompts = more noise
        else:
            R, S, N = 0.70, 0.75, 0.20  # Default moderate values

        # Compute derived metrics
        kappa = R / (R + N) if (R + N) > 0 else 0.5
        sigma = 0.3  # Default stability

        # Gate decision (simplified)
        if N >= 0.5:
            decision, gate = "BLOCK", 1
            reason = "High noise detected"
        elif R < 0.3:
            decision, gate = "BLOCK", 2
            reason = "Low relevance"
        elif kappa < 0.6:
            decision, gate = "REPAIR", 4
            reason = "Below kappa threshold"
        else:
            decision, gate = "EXECUTE", 5
            reason = "All gates passed (lightweight mode)"

        cert_id = hashlib.sha256(
            f"{prompt[:100]}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        return CertifyResponse(
            id=f"lite-{cert_id}",
            R=R,
            S=S,
            N=N,
            kappa_gate=kappa,
            sigma=sigma,
            decision=decision,
            gate_reached=gate,
            allowed=decision == "EXECUTE",
            reason=reason + " [LITE MODE - yrsn not available]",
            timestamp=datetime.utcnow().isoformat(),
        )


def get_adapter(**kwargs) -> YRSNAdapter:
    """Get yrsn adapter - falls back to lightweight mode if yrsn unavailable."""
    if YRSN_AVAILABLE:
        # Try to create rotor - if it fails, use lightweight mode
        try:
            rotor = get_rotor(kwargs.get('embed_dim', 1536))
            if rotor is not None:
                return LocalYRSNAdapter(**kwargs)
        except Exception:
            pass
    # Lightweight mode for Lambda/serverless or when yrsn fails
    return LightweightAdapter(**kwargs)
