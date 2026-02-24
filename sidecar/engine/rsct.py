"""
RSCT Engine - Core certification logic.

This wraps yrsn core or provides standalone computation.
"""

import hashlib
import math
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import deque


class RSCTEngine:
    """
    RSCT Certification Engine.

    Computes R, S, N decomposition and kappa-gate decisions.
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

    def __init__(self):
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()
        self.validation_history: deque = deque(maxlen=100)
        self.type_counts: Dict[str, int] = {}
        self.type_failures: Dict[str, int] = {}

    def certify(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        context: Optional[str] = None,
        policy: Optional[str] = "default",
    ) -> Dict[str, Any]:
        """
        Generate RSCT certificate for prompt.

        This is a lightweight heuristic implementation.
        Production should use yrsn core with trained rotors.
        """
        # Generate certificate ID
        cert_id = self._generate_id(prompt)
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Compute RSN decomposition (heuristic for now)
        R, S, N = self._compute_rsn(prompt, context)

        # Compute kappa (compatibility score)
        kappa_gate = self._compute_kappa(R, S, N)

        # Compute sigma (stability)
        sigma = self._compute_sigma(R, S, N)

        # Determine gate decision
        decision, gate_reached, reason = self._gate_decision(
            R, S, N, kappa_gate, sigma
        )

        # Check if multimodal (if context suggests multiple modalities)
        is_multimodal = self._detect_multimodal(prompt, context)
        kappa_H = kappa_L = kappa_interface = weak_modality = None

        if is_multimodal:
            kappa_H, kappa_L, kappa_interface = self._compute_multimodal_kappas(
                R, S, N
            )
            weak_modality = self._identify_weak_modality(
                kappa_H, kappa_L, kappa_interface
            )
            # kappa_gate is min of all
            kappa_gate = min(kappa_H, kappa_L, kappa_interface)

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
        }

    def _generate_id(self, prompt: str) -> str:
        """Generate unique certificate ID."""
        timestamp = datetime.utcnow().isoformat()
        content = f"{timestamp}:{prompt[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_rsn(
        self, prompt: str, context: Optional[str]
    ) -> tuple[float, float, float]:
        """
        Compute R, S, N decomposition.

        Heuristic implementation - production uses trained rotors.
        """
        # Simple heuristics based on prompt characteristics
        prompt_len = len(prompt)
        word_count = len(prompt.split())

        # Relevance: longer, more structured prompts tend to be more relevant
        R = min(0.9, 0.3 + (word_count / 100) * 0.4)

        # Support: presence of context increases support
        if context:
            S = min(0.8, 0.4 + len(context) / 1000 * 0.3)
        else:
            S = 0.3

        # Noise: very short or very long prompts have more noise
        if word_count < 5:
            N = 0.4
        elif word_count > 500:
            N = 0.3
        else:
            N = 0.2

        # Normalize to simplex (R + S + N = 1)
        total = R + S + N
        R, S, N = R / total, S / total, N / total

        return R, S, N

    def _compute_kappa(self, R: float, S: float, N: float) -> float:
        """
        Compute kappa (compatibility score).

        kappa = R / (R + N) when S is neutral
        """
        if R + N == 0:
            return 0.5
        return R / (R + N)

    def _compute_sigma(self, R: float, S: float, N: float) -> float:
        """
        Compute sigma (stability score).

        Lower sigma = more stable.
        """
        # Variance-based stability
        mean = (R + S + N) / 3
        variance = ((R - mean) ** 2 + (S - mean) ** 2 + (N - mean) ** 2) / 3
        return min(1.0, math.sqrt(variance) * 2)

    def _gate_decision(
        self, R: float, S: float, N: float, kappa: float, sigma: float
    ) -> tuple[str, int, str]:
        """
        5-gate decision logic.

        Returns (decision, gate_reached, reason)
        """
        # Gate 1: Noise check
        if N >= self.thresholds["N_threshold"]:
            return "REJECT", 1, f"Noise too high: N={N:.2f} >= {self.thresholds['N_threshold']}"

        # Gate 2: Relevance check
        if R < self.thresholds["R_min"]:
            return "BLOCK", 2, f"Relevance too low: R={R:.2f} < {self.thresholds['R_min']}"

        # Gate 3: Stability check
        if sigma > self.thresholds["sigma_threshold"]:
            return "DELEGATE", 3, f"Unstable: sigma={sigma:.2f} > {self.thresholds['sigma_threshold']}"

        # Gate 4: Kappa check
        if kappa < self.thresholds["kappa_threshold"]:
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
    ) -> tuple[float, float, float]:
        """
        Compute per-modality kappa scores.

        Returns (kappa_H, kappa_L, kappa_interface)
        """
        # Heuristic: distribute around base kappa with some variance
        base_kappa = self._compute_kappa(R, S, N)

        # Add slight variation for each modality
        kappa_H = min(1.0, base_kappa * 1.1)  # Text usually stronger
        kappa_L = max(0.1, base_kappa * 0.9)  # Vision slightly weaker
        kappa_interface = base_kappa  # Interface at base

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

        # Check if all are equal
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
        """
        Record validation feedback.

        Returns threshold adjustment if triggered.
        """
        self.validation_history.append({
            "certificate_id": certificate_id,
            "type": validation_type,
            "score": score,
            "failed": failed,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Update counts
        self.type_counts[validation_type] = self.type_counts.get(validation_type, 0) + 1
        if failed:
            self.type_failures[validation_type] = self.type_failures.get(validation_type, 0) + 1

        # Check if adjustment needed
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
            # Recommend tightening
            adjustment = {
                "type": validation_type,
                "failure_rate": failure_rate,
                "threshold": threshold,
                "recommendation": "tighten",
            }
            return adjustment

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
            "risk_indicators": {
                "noise_level": "HIGH" if cert.get("N", 0) > 0.4 else "NORMAL",
                "stability": "UNSTABLE" if cert.get("sigma", 0) > 0.7 else "STABLE",
            },
        }
