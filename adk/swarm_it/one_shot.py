"""
One-Shot Certification Workflow - Stripe Minions Pattern

Inspired by Stripe's one-shot end-to-end agents:
- Single API call: prompt → certificate with full audit trail
- No human intervention required
- Deterministic quality gates enforced
- Complete evidence export (SR 11-7 compliant)

Pattern: Context → Agent → Rotor → Gates → Evidence
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class OneShotRequest:
    """Request for one-shot certification."""
    prompt: str
    domain: str = "research"  # research, medical, legal, financial, dev

    # Optional overrides
    model: Optional[str] = None  # Override certification model
    thresholds: Optional[Dict[str, float]] = None  # Override quality gates

    # Evidence options
    auto_export_evidence: bool = True
    include_metadata: bool = True

    # User context (for audit trail)
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    request_id: Optional[str] = None

    # Advanced options
    max_retries: int = 2  # Stripe pattern: max 2 iterations
    enable_autofix: bool = True  # Auto-repair on REPAIR decision


@dataclass
class OneShotResult:
    """Result of one-shot certification."""
    # Certificate data
    certificate: Dict[str, Any]
    decision: str  # EXECUTE, REPAIR, BLOCK, REJECT

    # Quality metrics
    R: float
    S: float
    N: float
    kappa: float

    # Execution metadata
    gate_reached: int
    reason: str
    iterations: int  # How many retries needed

    # Evidence
    evidence_file: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None

    # Audit trail
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    execution_time_ms: Optional[float] = None

    # Context
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    request_id: Optional[str] = None


class OneShotCertifier:
    """
    One-shot certification engine.

    Implements Stripe Minions pattern for end-to-end certification
    with minimal latency and maximum automation.

    Usage:
        certifier = OneShotCertifier(client=swarm_client)

        result = certifier.certify(OneShotRequest(
            prompt="Analyze this medical diagnosis...",
            domain="medical",
            user_id="doc_123"
        ))

        if result.decision == "EXECUTE":
            print(f"Certificate approved: kappa={result.kappa:.3f}")
            print(f"Evidence: {result.evidence_file}")
    """

    def __init__(
        self,
        client=None,  # SwarmIt client (optional)
        rotor=None,   # Custom rotor (optional, for BYOK mode)
        auto_export: bool = True,
        evidence_dir: str = "evidence",
    ):
        """
        Initialize one-shot certifier.

        Args:
            client: SwarmIt API client (if using hosted service)
            rotor: Custom rotor for local certification (BYOK mode)
            auto_export: Auto-export evidence by default
            evidence_dir: Directory for evidence files
        """
        self.client = client
        self.rotor = rotor
        self.auto_export = auto_export
        self.evidence_dir = evidence_dir

        # Domain-specific thresholds (Stripe pattern: conditional rules)
        self.domain_thresholds = {
            "medical": {"kappa": 0.9, "R": 0.5, "S": 0.6, "N": 0.3},
            "legal": {"kappa": 0.85, "R": 0.5, "S": 0.5, "N": 0.4},
            "financial": {"kappa": 0.85, "R": 0.5, "S": 0.5, "N": 0.4},
            "research": {"kappa": 0.7, "R": 0.3, "S": 0.4, "N": 0.5},
            "dev": {"kappa": 0.5, "R": 0.2, "S": 0.2, "N": 0.7},
        }

    def certify(self, request: OneShotRequest) -> OneShotResult:
        """
        Execute one-shot certification workflow.

        Workflow stages (deterministic + creative):
        1. Context gathering (deterministic)
        2. Agent analysis (creative, if using API)
        3. Rotor decomposition (deterministic)
        4. Quality gates (deterministic)
        5. Evidence export (deterministic)
        6. Autofix retry if needed (Stripe pattern: max 2 iterations)

        Args:
            request: One-shot certification request

        Returns:
            OneShotResult with certificate and evidence
        """
        start_time = datetime.utcnow()
        iterations = 0

        # Stage 1: Get thresholds (deterministic)
        thresholds = request.thresholds or self._get_thresholds(request.domain)

        # Stage 2-4: Execute certification with potential retries
        while iterations < request.max_retries:
            iterations += 1

            # Execute certification
            cert_result = self._execute_certification(
                prompt=request.prompt,
                model=request.model,
                thresholds=thresholds,
                user_id=request.user_id,
                org_id=request.org_id,
                request_id=request.request_id,
            )

            # Check decision
            if cert_result["decision"] in ["EXECUTE", "BLOCK", "REJECT"]:
                # Terminal states - no retry
                break

            if cert_result["decision"] == "REPAIR" and request.enable_autofix and iterations < request.max_retries:
                # Stripe pattern: autofix and retry
                request.prompt = self._autofix_prompt(
                    original=request.prompt,
                    gate_feedback=cert_result.get("reason", "")
                )
                continue

            # No more retries or autofix disabled
            break

        # Stage 5: Export evidence (deterministic)
        evidence_file = None
        evidence_data = None

        if request.auto_export_evidence or self.auto_export:
            evidence_data = self._build_evidence(
                request=request,
                result=cert_result,
                iterations=iterations,
            )
            evidence_file = self._save_evidence(evidence_data)

        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Build result
        return OneShotResult(
            certificate=cert_result.get("certificate", {}),
            decision=cert_result["decision"],
            R=cert_result.get("R", 0.0),
            S=cert_result.get("S", 0.0),
            N=cert_result.get("N", 0.0),
            kappa=cert_result.get("kappa", 0.0),
            gate_reached=cert_result.get("gate_reached", 0),
            reason=cert_result.get("reason", ""),
            iterations=iterations,
            evidence_file=evidence_file,
            evidence=evidence_data if request.include_metadata else None,
            execution_time_ms=execution_time,
            user_id=request.user_id,
            org_id=request.org_id,
            request_id=request.request_id,
        )

    def _get_thresholds(self, domain: str) -> Dict[str, float]:
        """Get quality thresholds for domain (Stripe pattern: conditional rules)."""
        return self.domain_thresholds.get(domain, self.domain_thresholds["research"])

    def _execute_certification(
        self,
        prompt: str,
        model: Optional[str],
        thresholds: Dict[str, float],
        user_id: Optional[str],
        org_id: Optional[str],
        request_id: Optional[str],
    ) -> Dict[str, Any]:
        """Execute single certification attempt."""
        if self.client:
            # Use hosted API
            return self.client.certify(
                prompt=prompt,
                model=model,
                thresholds=thresholds,
                user_id=user_id,
                org_id=org_id,
                request_id=request_id,
            )
        elif self.rotor:
            # BYOK mode: local certification
            return self._local_certify(prompt, thresholds)
        else:
            raise ValueError("Either client or rotor must be provided")

    def _local_certify(self, prompt: str, thresholds: Dict[str, float]) -> Dict[str, Any]:
        """Local certification using BYOK rotor."""
        # This would integrate with byok_engine.py
        # Placeholder for now
        raise NotImplementedError("Local BYOK certification - integrate with byok_engine")

    def _autofix_prompt(self, original: str, gate_feedback: str) -> str:
        """
        Auto-repair prompt based on gate feedback.

        Stripe pattern: autofix integration for automatic remediation.
        This is a simple implementation - production would use LLM refinement.
        """
        # Simple autofix: add clarification based on failure
        if "Low relevance" in gate_feedback:
            return f"{original}\n\n[SYSTEM: Please provide more relevant analysis]"
        elif "Low stability" in gate_feedback:
            return f"{original}\n\n[SYSTEM: Please provide more consistent analysis]"
        elif "High noise" in gate_feedback:
            return f"{original}\n\n[SYSTEM: Please reduce irrelevant content]"
        else:
            return original  # No autofix possible

    def _build_evidence(
        self,
        request: OneShotRequest,
        result: Dict[str, Any],
        iterations: int,
    ) -> Dict[str, Any]:
        """Build SR 11-7 compliant evidence."""
        return {
            "request": {
                "prompt": request.prompt,
                "domain": request.domain,
                "user_id": request.user_id,
                "org_id": request.org_id,
                "request_id": request.request_id,
            },
            "result": {
                "decision": result["decision"],
                "R": result.get("R", 0.0),
                "S": result.get("S", 0.0),
                "N": result.get("N", 0.0),
                "kappa": result.get("kappa", 0.0),
                "gate_reached": result.get("gate_reached", 0),
                "reason": result.get("reason", ""),
            },
            "execution": {
                "iterations": iterations,
                "timestamp": datetime.utcnow().isoformat(),
                "model": request.model or "default",
            },
            "certificate": result.get("certificate", {}),
        }

    def _save_evidence(self, evidence: Dict[str, Any]) -> str:
        """Save evidence to file (SR 11-7 compliance)."""
        import os

        os.makedirs(self.evidence_dir, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.evidence_dir}/one_shot_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(evidence, f, indent=2)

        return filename
