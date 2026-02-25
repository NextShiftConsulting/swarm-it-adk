"""
RSCT Engine - Core certification logic.

This wraps yrsn core or provides standalone computation.
Uses pattern detection to identify problematic inputs.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from collections import deque

from .patterns import get_detector, PatternMatch

# Try to import yrsn for real RSCT computation
try:
    from yrsn.core.decomposition import HybridSimplexRotor
    from yrsn.core.certificate import YRSNCertificate
    YRSN_AVAILABLE = True
except ImportError:
    YRSN_AVAILABLE = False


class RSCTEngine:
    """
    RSCT Certification Engine.

    Computes R, S, N decomposition and kappa-gate decisions.
    Uses pattern detection for injection/spam/gibberish.
    Optionally uses yrsn core for real RSCT computation.
    """

    # Default thresholds
    DEFAULT_THRESHOLDS = {
        "kappa_threshold": 0.7,
        "N_threshold": 0.5,
        "sigma_threshold": 0.7,
        "R_min": 0.3,
        "S_min": 0.4,
    }

    # Validation failure rate thresholds
    FAILURE_THRESHOLDS = {
        "TYPE_I": 0.10,
        "TYPE_II": 0.05,
        "TYPE_III": 0.02,
        "TYPE_IV": 0.10,
        "TYPE_V": 0.10,
        "TYPE_VI": 0.10,
    }

    def __init__(self, use_yrsn: bool = True):
        """
        Initialize RSCT engine.

        Args:
            use_yrsn: Whether to use yrsn core if available
        """
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        self.validation_history: deque = deque(maxlen=100)
        self.type_counts: Dict[str, int] = {}
        self.type_failures: Dict[str, int] = {}

        # Pattern detector
        self.pattern_detector = get_detector()

        # yrsn integration
        self.use_yrsn = use_yrsn and YRSN_AVAILABLE
        self.rotor = None
        if self.use_yrsn:
            try:
                self.rotor = HybridSimplexRotor(embed_dim=64)
            except Exception:
                self.use_yrsn = False

    def certify(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        context: Optional[str] = None,
        policy: Optional[str] = "default",
    ) -> Dict[str, Any]:
        """
        Generate RSCT certificate for prompt.

        Uses pattern detection + heuristics (or yrsn if available).
        """
        # Generate certificate ID
        cert_id = self._generate_id(prompt)
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Detect problematic patterns
        matches = self.pattern_detector.detect(prompt)
        noise_boost = self.pattern_detector.get_noise_boost(matches)
        relevance_factor = self.pattern_detector.get_relevance_factor(matches)

        # Compute RSN decomposition
        if self.use_yrsn and self.rotor:
            R, S, N = self._compute_rsn_yrsn(prompt, context)
        else:
            R, S, N = self._compute_rsn_heuristic(prompt, context)

        # Apply pattern-based adjustments
        R = R * relevance_factor
        N = min(1.0, N + noise_boost)

        # Re-normalize to simplex
        total = R + S + N
        if total > 0:
            R, S, N = R / total, S / total, N / total

        # Compute kappa (compatibility score)
        kappa_gate = self._compute_kappa(R, S, N)

        # Compute sigma (stability)
        sigma = self._compute_sigma(R, S, N)

        # Determine gate decision
        decision, gate_reached, reason = self._gate_decision(
            R, S, N, kappa_gate, sigma, matches
        )

        # Check if multimodal
        is_multimodal = self._detect_multimodal(prompt, context)
        kappa_H = kappa_L = kappa_interface = weak_modality = None

        if is_multimodal:
            kappa_H, kappa_L, kappa_interface = self._compute_multimodal_kappas(
                R, S, N
            )
            weak_modality = self._identify_weak_modality(
                kappa_H, kappa_L, kappa_interface
            )
            kappa_gate = min(kappa_H, kappa_L, kappa_interface)

        # Build pattern info
        pattern_flags = [m.category for m in matches[:3]] if matches else []

        return {
            "id": cert_id,
            "timestamp": timestamp,
            "R": round(R, 4),
            "S": round(S, 4),
            "N": round(N, 4),
            "kappa_gate": round(kappa_gate, 4),
            "sigma": round(sigma, 4),
            "decision": decision,
            "gate_reached": gate_reached,
            "reason": reason,
            "allowed": decision in ("EXECUTE", "REPAIR", "DELEGATE"),
            "kappa_H": round(kappa_H, 4) if kappa_H else None,
            "kappa_L": round(kappa_L, 4) if kappa_L else None,
            "kappa_interface": round(kappa_interface, 4) if kappa_interface else None,
            "weak_modality": weak_modality,
            "is_multimodal": is_multimodal,
            "pattern_flags": pattern_flags,
            "using_yrsn": self.use_yrsn,
        }

    def _generate_id(self, prompt: str) -> str:
        """Generate unique certificate ID."""
        timestamp = datetime.utcnow().isoformat()
        content = f"{timestamp}:{prompt[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_rsn_yrsn(
        self, prompt: str, context: Optional[str]
    ) -> Tuple[float, float, float]:
        """
        Compute RSN using yrsn's HybridSimplexRotor.

        Requires embeddings - falls back to heuristic if not available.
        """
        # TODO: Get embeddings from configured LLM
        # For now, fall back to heuristic
        return self._compute_rsn_heuristic(prompt, context)

    def _compute_rsn_heuristic(
        self, prompt: str, context: Optional[str]
    ) -> Tuple[float, float, float]:
        """
        Compute R, S, N using heuristics.

        This is a fallback when yrsn/embeddings not available.
        """
        prompt_len = len(prompt)
        word_count = len(prompt.split())

        # Base relevance from structure
        if word_count == 0:
            R = 0.1
        elif word_count < 3:
            R = 0.2
        elif word_count < 10:
            R = 0.4
        elif word_count < 50:
            R = 0.6
        else:
            R = 0.7

        # Question words boost relevance
        question_words = ['what', 'how', 'why', 'when', 'where', 'who', 'which', 'explain', 'describe']
        if any(prompt.lower().startswith(qw) for qw in question_words):
            R = min(1.0, R + 0.15)

        # Support from context
        if context:
            context_len = len(context)
            if context_len > 500:
                S = 0.5
            elif context_len > 100:
                S = 0.35
            else:
                S = 0.25
        else:
            S = 0.2

        # Noise from length/structure issues
        if word_count == 0:
            N = 0.7
        elif word_count < 3:
            N = 0.5
        elif word_count > 500:
            N = 0.4
        else:
            N = 0.2

        # Normalize to simplex
        total = R + S + N
        return R / total, S / total, N / total

    def _compute_kappa(self, R: float, S: float, N: float) -> float:
        """
        Compute kappa (compatibility score).

        kappa = R / (R + N) - measures signal vs noise
        """
        if R + N == 0:
            return 0.5
        return R / (R + N)

    def _compute_sigma(self, R: float, S: float, N: float) -> float:
        """
        Compute sigma (stability score).

        Based on variance of RSN components.
        """
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
        matches: List[PatternMatch],
    ) -> Tuple[str, int, str]:
        """
        5-gate decision logic with pattern awareness.

        Returns (decision, gate_reached, reason)
        """
        # Gate 0: Severe pattern detection (pre-gate)
        if matches and matches[0].score >= 0.9:
            category = matches[0].category
            if category in ('jailbreak', 'xss', 'code_injection'):
                return "REJECT", 0, f"Dangerous pattern detected: {category}"

        # Gate 1: Noise check
        if N >= self.thresholds["N_threshold"]:
            if matches:
                return "REJECT", 1, f"High noise (N={N:.2f}) + pattern: {matches[0].category}"
            return "REJECT", 1, f"Noise too high: N={N:.2f} >= {self.thresholds['N_threshold']}"

        # Gate 2: Relevance check
        if R < self.thresholds["R_min"]:
            return "BLOCK", 2, f"Relevance too low: R={R:.2f} < {self.thresholds['R_min']}"

        # Gate 3: Stability check
        if sigma > self.thresholds["sigma_threshold"]:
            return "DELEGATE", 3, f"Unstable: sigma={sigma:.2f} > {self.thresholds['sigma_threshold']}"

        # Gate 4: Kappa check
        if kappa < self.thresholds["kappa_threshold"]:
            if matches:
                return "REPAIR", 4, f"Low compatibility (κ={kappa:.2f}) + {matches[0].category}"
            return "REPAIR", 4, f"Low compatibility: kappa={kappa:.2f} < {self.thresholds['kappa_threshold']}"

        # Gate 5: All checks passed
        return "EXECUTE", 5, "All gates passed"

    def _detect_multimodal(
        self, prompt: str, context: Optional[str]
    ) -> bool:
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
    ) -> Tuple[float, float, float]:
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

    def record_validation(
        self,
        certificate_id: str,
        validation_type: str,
        score: float,
        failed: bool,
    ) -> Optional[Dict[str, Any]]:
        """Record validation feedback."""
        self.validation_history.append({
            "certificate_id": certificate_id,
            "type": validation_type,
            "score": score,
            "failed": failed,
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.type_counts[validation_type] = self.type_counts.get(validation_type, 0) + 1
        if failed:
            self.type_failures[validation_type] = self.type_failures.get(validation_type, 0) + 1

        return self._check_threshold_adjustment(validation_type)

    def _check_threshold_adjustment(
        self, validation_type: str
    ) -> Optional[Dict[str, Any]]:
        """Check if threshold adjustment is needed."""
        count = self.type_counts.get(validation_type, 0)
        if count < 10:
            return None

        failure_rate = self.type_failures.get(validation_type, 0) / count
        threshold = self.FAILURE_THRESHOLDS.get(validation_type, 0.10)

        if failure_rate > threshold:
            return {
                "type": validation_type,
                "failure_rate": failure_rate,
                "threshold": threshold,
                "recommendation": "tighten",
            }
        return None

    def get_thresholds(self) -> Dict[str, float]:
        """Get current thresholds."""
        return self.thresholds.copy()

    def set_threshold(self, key: str, value: float) -> None:
        """Set a threshold value."""
        self.thresholds[key] = value

    def get_failure_rates(self) -> Dict[str, float]:
        """Get current failure rates by validation type."""
        rates = {}
        for vtype, count in self.type_counts.items():
            if count > 0:
                rates[vtype] = self.type_failures.get(vtype, 0) / count
        return rates

    def format_sr117(self, cert: Dict[str, Any]) -> Dict[str, Any]:
        """Format certificate for SR 11-7 compliance."""
        return {
            "record_type": "MODEL_VALIDATION",
            "certificate_id": cert.get("id"),
            "timestamp": cert.get("timestamp"),
            "quantitative_metrics": {
                "R": cert.get("R"),
                "S": cert.get("S"),
                "N": cert.get("N"),
                "kappa_gate": cert.get("kappa_gate"),
                "sigma": cert.get("sigma"),
            },
            "gate_outcome": cert.get("decision"),
            "gate_reached": cert.get("gate_reached"),
            "pattern_flags": cert.get("pattern_flags", []),
            "risk_indicators": {
                "noise_level": "HIGH" if cert.get("N", 0) > 0.4 else "NORMAL",
                "stability": "UNSTABLE" if cert.get("sigma", 0) > 0.7 else "STABLE",
                "patterns_detected": len(cert.get("pattern_flags", [])) > 0,
            },
        }
