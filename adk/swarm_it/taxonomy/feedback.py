"""
Validation Feedback Loop

Calibrates RSCT pre-execution thresholds based on Type I-VI
post-execution validation failure rates.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from collections import deque


class ValidationType(Enum):
    """Type I-VI validation types."""

    TYPE_I = "type_I"  # Groundedness
    TYPE_II = "type_II"  # Contradiction
    TYPE_III = "type_III"  # Inversion
    TYPE_IV = "type_IV"  # Drift
    TYPE_V = "type_V"  # Reasoning
    TYPE_VI = "type_VI"  # Domain


@dataclass
class FeedbackEvent:
    """Record of a validation feedback event."""

    timestamp: str
    certificate_id: str
    validation_type: ValidationType
    score: float
    failed: bool
    adjustment_applied: Optional[str] = None
    adjustment_delta: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "certificate_id": self.certificate_id,
            "validation_type": self.validation_type.value,
            "score": self.score,
            "failed": self.failed,
            "adjustment_applied": self.adjustment_applied,
            "adjustment_delta": self.adjustment_delta,
        }


@dataclass
class ThresholdAdjustment:
    """Recommended threshold adjustment."""

    parameter: str  # e.g., "N_threshold", "kappa_L_threshold"
    current_value: float
    recommended_value: float
    delta: float
    reason: str
    trigger_type: ValidationType
    confidence: float


class ValidationFeedbackLoop:
    """
    Calibrate RSCT thresholds based on Type I-VI detection rates.

    Feedback mapping:
        Type I high  → Tighten N threshold (reduce noise tolerance)
        Type II high → Tighten κ_L threshold (require better low-level)
        Type III high → Tighten c threshold (require better consensus)
        Type IV high → Tighten σ_thr (reduce turbulence tolerance)
        Type V high  → Tighten σ_thr (reduce turbulence tolerance)
        Type VI high → Tighten ω threshold (stricter OOD detection)

    Usage:
        loop = ValidationFeedbackLoop()

        # Record validation results
        loop.record(
            certificate_id="cert-123",
            validation_type=ValidationType.TYPE_II,
            score=0.85,
            failed=True
        )

        # Get recommended adjustments
        adjustments = loop.compute_adjustments()
        for adj in adjustments:
            print(f"Adjust {adj.parameter} by {adj.delta}")
    """

    # Default thresholds for triggering adjustments
    FAILURE_RATE_THRESHOLDS = {
        ValidationType.TYPE_I: 0.10,  # >10% unsupported claims
        ValidationType.TYPE_II: 0.05,  # >5% contradictions (critical)
        ValidationType.TYPE_III: 0.02,  # >2% inversions (very critical)
        ValidationType.TYPE_IV: 0.10,  # >10% drift
        ValidationType.TYPE_V: 0.10,  # >10% reasoning failures
        ValidationType.TYPE_VI: 0.10,  # >10% domain mismatch
    }

    # Default adjustment deltas
    ADJUSTMENT_DELTAS = {
        ValidationType.TYPE_I: ("N_threshold", -0.05),  # Reduce N tolerance
        ValidationType.TYPE_II: ("kappa_L_threshold", +0.05),  # Increase κ_L requirement
        ValidationType.TYPE_III: ("c_threshold", +0.05),  # Increase consensus requirement
        ValidationType.TYPE_IV: ("sigma_thr", -0.05),  # Reduce σ tolerance
        ValidationType.TYPE_V: ("sigma_thr", -0.05),  # Reduce σ tolerance
        ValidationType.TYPE_VI: ("omega_threshold", +0.05),  # Increase ω requirement
    }

    def __init__(
        self,
        window_size: int = 100,
        min_samples: int = 10,
        auto_apply: bool = False,
    ):
        """
        Initialize feedback loop.

        Args:
            window_size: Number of recent validations to track
            min_samples: Minimum samples before computing adjustments
            auto_apply: Whether to automatically apply adjustments
        """
        self.window_size = window_size
        self.min_samples = min_samples
        self.auto_apply = auto_apply

        # Validation history
        self.history: deque = deque(maxlen=window_size)

        # Per-type failure counts
        self.type_counts: Dict[ValidationType, int] = {t: 0 for t in ValidationType}
        self.type_failures: Dict[ValidationType, int] = {t: 0 for t in ValidationType}

        # Current threshold values (can be updated externally)
        self.thresholds: Dict[str, float] = {
            "N_threshold": 0.5,
            "kappa_L_threshold": 0.4,
            "c_threshold": 0.4,
            "sigma_thr": 0.7,
            "omega_threshold": 0.3,
        }

        # Applied adjustments history
        self.adjustment_history: List[ThresholdAdjustment] = []

    def record(
        self,
        certificate_id: str,
        validation_type: ValidationType,
        score: float,
        failed: bool,
    ) -> FeedbackEvent:
        """
        Record a validation result.

        Args:
            certificate_id: ID of the certified request
            validation_type: Which Type (I-VI) validation was run
            score: Validation score (interpretation varies by type)
            failed: Whether validation failed

        Returns:
            FeedbackEvent record
        """
        event = FeedbackEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            certificate_id=certificate_id,
            validation_type=validation_type,
            score=score,
            failed=failed,
        )

        self.history.append(event)
        self.type_counts[validation_type] += 1
        if failed:
            self.type_failures[validation_type] += 1

        # Auto-apply if enabled
        if self.auto_apply:
            adjustments = self.compute_adjustments()
            for adj in adjustments:
                self._apply_adjustment(adj, event)

        return event

    def compute_adjustments(self) -> List[ThresholdAdjustment]:
        """
        Compute recommended threshold adjustments based on failure rates.

        Returns:
            List of ThresholdAdjustment recommendations
        """
        if len(self.history) < self.min_samples:
            return []

        adjustments = []

        for vtype in ValidationType:
            count = self.type_counts[vtype]
            if count < self.min_samples // 2:
                continue  # Not enough samples for this type

            failure_rate = self.type_failures[vtype] / count
            threshold = self.FAILURE_RATE_THRESHOLDS[vtype]

            if failure_rate > threshold:
                param, delta = self.ADJUSTMENT_DELTAS[vtype]
                current = self.thresholds.get(param, 0.5)

                adjustments.append(ThresholdAdjustment(
                    parameter=param,
                    current_value=current,
                    recommended_value=current + delta,
                    delta=delta,
                    reason=f"{vtype.value} failure rate {failure_rate:.1%} > {threshold:.1%}",
                    trigger_type=vtype,
                    confidence=min(1.0, failure_rate / threshold),
                ))

        return adjustments

    def _apply_adjustment(
        self,
        adjustment: ThresholdAdjustment,
        event: FeedbackEvent,
    ) -> None:
        """Apply a threshold adjustment."""
        self.thresholds[adjustment.parameter] = adjustment.recommended_value
        event.adjustment_applied = adjustment.parameter
        event.adjustment_delta = adjustment.delta
        self.adjustment_history.append(adjustment)

    def get_failure_rates(self) -> Dict[str, float]:
        """Get current failure rates by type."""
        rates = {}
        for vtype in ValidationType:
            count = self.type_counts[vtype]
            if count > 0:
                rates[vtype.value] = self.type_failures[vtype] / count
            else:
                rates[vtype.value] = 0.0
        return rates

    def get_statistics(self) -> Dict[str, Any]:
        """Get feedback loop statistics."""
        return {
            "total_validations": len(self.history),
            "failure_rates": self.get_failure_rates(),
            "current_thresholds": self.thresholds.copy(),
            "adjustments_applied": len(self.adjustment_history),
            "auto_apply": self.auto_apply,
        }

    def reset(self) -> None:
        """Reset all counters and history."""
        self.history.clear()
        self.type_counts = {t: 0 for t in ValidationType}
        self.type_failures = {t: 0 for t in ValidationType}
        self.adjustment_history.clear()

    def set_threshold(self, parameter: str, value: float) -> None:
        """Manually set a threshold value."""
        self.thresholds[parameter] = value

    def get_threshold(self, parameter: str) -> float:
        """Get current threshold value."""
        return self.thresholds.get(parameter, 0.5)
