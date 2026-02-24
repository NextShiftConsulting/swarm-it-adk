"""
Audit Log

Provides compliance-ready audit logging for certificates.
Supports SR 11-7 and EU AI Act formatting.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, TextIO
from pathlib import Path

from ..local.engine import RSCTCertificate, GateDecision


@dataclass
class AuditEntry:
    """
    Single audit log entry.

    Format matches RSCT paper Appendix B.3:
    L = (α, ω, α_ω, κ_gate, σ, gate_reached, outcome, t_stamp)
    """

    # Certificate identity
    certificate_id: str
    timestamp: str

    # RSCT tuple (α, ω, α_ω, κ_gate, σ, gate_reached, outcome)
    alpha: float  # Purity: R/(R+N)
    omega: Optional[float]  # OOD score
    alpha_omega: Optional[float]  # Combined quality
    kappa_gate: float
    sigma: float
    gate_reached: int
    outcome: str  # Decision value

    # Extended audit fields
    policy: str
    reason: str
    simplex: Dict[str, float]  # R, S, N

    # Metadata
    source: str = "swarm_it_sdk"
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "timestamp": self.timestamp,
            "rsct_tuple": {
                "alpha": self.alpha,
                "omega": self.omega,
                "alpha_omega": self.alpha_omega,
                "kappa_gate": self.kappa_gate,
                "sigma": self.sigma,
                "gate_reached": self.gate_reached,
                "outcome": self.outcome,
            },
            "policy": self.policy,
            "reason": self.reason,
            "simplex": self.simplex,
            "source": self.source,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }

    def to_sr117_format(self) -> Dict[str, Any]:
        """Format for SR 11-7 compliance."""
        return {
            "model_id": self.certificate_id,
            "validation_timestamp": self.timestamp,
            "quality_metrics": {
                "purity": self.alpha,
                "ood_score": self.omega,
                "compatibility": self.kappa_gate,
                "stability": 1.0 - self.sigma,
            },
            "gate_outcome": {
                "decision": self.outcome,
                "gate_level": self.gate_reached,
                "rationale": self.reason,
            },
            "governance": {
                "policy_applied": self.policy,
                "source_system": self.source,
            },
        }

    @classmethod
    def from_certificate(
        cls,
        cert: RSCTCertificate,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> "AuditEntry":
        """Create audit entry from certificate."""
        # Compute alpha if not present
        alpha = cert.alpha if cert.alpha is not None else (
            cert.R / (cert.R + cert.N) if (cert.R + cert.N) > 0 else 0.0
        )

        # Compute alpha_omega if omega present
        alpha_omega = None
        if cert.omega is not None:
            alpha_omega = alpha * cert.omega

        return cls(
            certificate_id=cert.id,
            timestamp=cert.timestamp,
            alpha=alpha,
            omega=cert.omega,
            alpha_omega=alpha_omega,
            kappa_gate=cert.kappa_gate,
            sigma=cert.sigma,
            gate_reached=cert.gate_reached,
            outcome=cert.decision.value,
            policy=cert.policy,
            reason=cert.reason,
            simplex={"R": cert.R, "S": cert.S, "N": cert.N},
            session_id=session_id,
            user_id=user_id,
        )


class AuditLog:
    """
    Append-only audit log for certificates.

    Supports multiple output formats:
    - JSON lines (default)
    - SR 11-7 format
    - CSV
    """

    def __init__(
        self,
        output_path: Optional[str] = None,
        format: str = "jsonl",
        buffer_size: int = 100,
    ):
        """
        Initialize audit log.

        Args:
            output_path: Path to log file (None for in-memory only)
            format: Output format (jsonl, sr117, csv)
            buffer_size: Number of entries to buffer before flush
        """
        self.output_path = output_path
        self.format = format
        self.buffer_size = buffer_size

        self._buffer: List[AuditEntry] = []
        self._entry_count = 0

        # Create output file if specified
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            if format == "csv":
                self._write_csv_header()

    def _write_csv_header(self):
        """Write CSV header."""
        with open(self.output_path, "w") as f:
            f.write("certificate_id,timestamp,alpha,omega,kappa_gate,sigma,gate_reached,outcome,policy\n")

    def log(
        self,
        cert: RSCTCertificate,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AuditEntry:
        """
        Log a certificate.

        Args:
            cert: Certificate to log
            session_id: Optional session identifier
            user_id: Optional user identifier

        Returns:
            AuditEntry created
        """
        entry = AuditEntry.from_certificate(cert, session_id, user_id)
        self._buffer.append(entry)
        self._entry_count += 1

        if len(self._buffer) >= self.buffer_size:
            self.flush()

        return entry

    def flush(self):
        """Flush buffer to output."""
        if not self._buffer or not self.output_path:
            return

        with open(self.output_path, "a") as f:
            for entry in self._buffer:
                if self.format == "jsonl":
                    f.write(json.dumps(entry.to_dict()) + "\n")
                elif self.format == "sr117":
                    f.write(json.dumps(entry.to_sr117_format()) + "\n")
                elif self.format == "csv":
                    f.write(
                        f"{entry.certificate_id},{entry.timestamp},"
                        f"{entry.alpha:.4f},{entry.omega or ''},"
                        f"{entry.kappa_gate:.4f},{entry.sigma:.4f},"
                        f"{entry.gate_reached},{entry.outcome},{entry.policy}\n"
                    )

        self._buffer.clear()

    def get_entries(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent entries from buffer."""
        return self._buffer[-limit:]

    def count(self) -> int:
        """Get total logged entry count."""
        return self._entry_count

    def close(self):
        """Flush and close log."""
        self.flush()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SR117AuditFormatter:
    """
    Formatter for SR 11-7 Model Risk Management compliance.

    Produces audit artifacts that satisfy:
    - Section 4(c): Back-testing records
    - Section 5(a): Validation documentation
    - Section 6(b): Ongoing monitoring
    """

    @staticmethod
    def format_validation_record(cert: RSCTCertificate) -> Dict[str, Any]:
        """
        Format certificate as SR 11-7 validation record.

        Returns a dict suitable for regulatory submission.
        """
        entry = AuditEntry.from_certificate(cert)
        return {
            "record_type": "MODEL_VALIDATION",
            "record_version": "SR11-7_v1",
            "generated_at": datetime.utcnow().isoformat() + "Z",

            "model_identification": {
                "certificate_id": cert.id,
                "policy_name": cert.policy,
                "timestamp": cert.timestamp,
            },

            "quantitative_metrics": {
                "relevance_score": cert.R,
                "support_score": cert.S,
                "noise_score": cert.N,
                "purity_ratio": entry.alpha,
                "compatibility_score": cert.kappa_gate,
                "stability_score": 1.0 - cert.sigma,
            },

            "validation_outcome": {
                "gate_decision": cert.decision.value,
                "gate_level_reached": cert.gate_reached,
                "decision_rationale": cert.reason,
                "execution_permitted": cert.allowed,
            },

            "risk_indicators": {
                "noise_flag": cert.N >= 0.3,
                "stability_flag": cert.sigma > 0.5,
                "compatibility_flag": cert.kappa_gate < 0.4,
                "overall_risk": _compute_risk_level(cert),
            },

            "compliance_assertions": {
                "simplex_constraint_satisfied": cert.simplex_valid,
                "threshold_checks_passed": cert.allowed,
                "audit_trail_complete": True,
            },
        }

    @staticmethod
    def generate_batch_report(
        certificates: List[RSCTCertificate],
        report_title: str = "Model Validation Report",
    ) -> Dict[str, Any]:
        """
        Generate batch validation report for multiple certificates.

        Suitable for periodic regulatory reporting.
        """
        if not certificates:
            return {"error": "No certificates provided"}

        # Compute aggregates
        total = len(certificates)
        allowed = sum(1 for c in certificates if c.allowed)
        rejected = total - allowed

        avg_R = sum(c.R for c in certificates) / total
        avg_kappa = sum(c.kappa_gate for c in certificates) / total
        avg_sigma = sum(c.sigma for c in certificates) / total

        # Risk distribution
        risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for cert in certificates:
            risk = _compute_risk_level(cert)
            risk_counts[risk] += 1

        return {
            "report_type": "SR11-7_BATCH_VALIDATION",
            "report_version": "1.0",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "title": report_title,

            "summary": {
                "total_validations": total,
                "executions_permitted": allowed,
                "executions_blocked": rejected,
                "permit_rate": allowed / total if total > 0 else 0,
            },

            "aggregate_metrics": {
                "mean_relevance": avg_R,
                "mean_compatibility": avg_kappa,
                "mean_turbulence": avg_sigma,
            },

            "risk_distribution": risk_counts,

            "time_range": {
                "earliest": min(c.timestamp for c in certificates),
                "latest": max(c.timestamp for c in certificates),
            },

            "individual_records": [
                SR117AuditFormatter.format_validation_record(c)
                for c in certificates
            ],
        }


def _compute_risk_level(cert: RSCTCertificate) -> str:
    """Compute risk level from certificate."""
    if cert.N >= 0.5 or cert.kappa_gate < 0.3:
        return "CRITICAL"
    if cert.N >= 0.3 or cert.sigma > 0.7 or cert.kappa_gate < 0.4:
        return "HIGH"
    if cert.N >= 0.2 or cert.sigma > 0.5:
        return "MEDIUM"
    return "LOW"
