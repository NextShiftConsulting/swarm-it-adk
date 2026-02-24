"""
Swarm-It Thin Client

Communicates with sidecar via REST API.
"""

import httpx
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List


class GateDecision(str, Enum):
    EXECUTE = "EXECUTE"
    REPAIR = "REPAIR"
    DELEGATE = "DELEGATE"
    BLOCK = "BLOCK"
    REJECT = "REJECT"


class ValidationType(str, Enum):
    TYPE_I = "TYPE_I"
    TYPE_II = "TYPE_II"
    TYPE_III = "TYPE_III"
    TYPE_IV = "TYPE_IV"
    TYPE_V = "TYPE_V"
    TYPE_VI = "TYPE_VI"


@dataclass
class Certificate:
    """RSCT Certificate returned from sidecar."""

    id: str
    timestamp: str
    R: float
    S: float
    N: float
    kappa_gate: float
    sigma: float
    decision: GateDecision
    gate_reached: int
    reason: str
    allowed: bool

    # Multimodal (optional)
    kappa_H: Optional[float] = None
    kappa_L: Optional[float] = None
    kappa_interface: Optional[float] = None
    weak_modality: Optional[str] = None
    is_multimodal: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Certificate":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            R=data["R"],
            S=data["S"],
            N=data["N"],
            kappa_gate=data["kappa_gate"],
            sigma=data["sigma"],
            decision=GateDecision(data["decision"]),
            gate_reached=data["gate_reached"],
            reason=data["reason"],
            allowed=data["allowed"],
            kappa_H=data.get("kappa_H"),
            kappa_L=data.get("kappa_L"),
            kappa_interface=data.get("kappa_interface"),
            weak_modality=data.get("weak_modality"),
            is_multimodal=data.get("is_multimodal", False),
        )


class SwarmIt:
    """
    Swarm-It Client.

    Thin wrapper around sidecar REST API.

    Usage:
        swarm = SwarmIt(url="http://localhost:8080")
        cert = swarm.certify("What is 2+2?")

        if cert.allowed:
            response = my_llm(prompt)
            swarm.validate(cert.id, ValidationType.TYPE_I, score=0.9)
    """

    def __init__(
        self,
        url: str = "http://localhost:8080",
        timeout: float = 30.0,
    ):
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def certify(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        context: Optional[str] = None,
        policy: str = "default",
    ) -> Certificate:
        """
        Request RSCT certification for a prompt.

        Args:
            prompt: The prompt to certify
            model_id: Optional model identifier
            context: Optional context/system prompt
            policy: Certification policy name

        Returns:
            Certificate with gate decision
        """
        response = self._client.post(
            f"{self.base_url}/api/v1/certify",
            json={
                "prompt": prompt,
                "model_id": model_id,
                "context": context,
                "policy": policy,
            },
        )
        response.raise_for_status()
        return Certificate.from_dict(response.json())

    def validate(
        self,
        certificate_id: str,
        validation_type: ValidationType,
        score: float,
        failed: bool = False,
    ) -> Dict[str, Any]:
        """
        Submit post-execution validation feedback.

        Args:
            certificate_id: ID of the certificate being validated
            validation_type: Type I-VI validation
            score: Validation score [0, 1]
            failed: Whether validation failed

        Returns:
            Response with optional threshold adjustment
        """
        response = self._client.post(
            f"{self.base_url}/api/v1/validate",
            json={
                "certificate_id": certificate_id,
                "validation_type": validation_type.value,
                "score": score,
                "failed": failed,
            },
        )
        response.raise_for_status()
        return response.json()

    def audit(
        self,
        format: str = "JSON",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Export certificates for compliance audit.

        Args:
            format: Export format (JSON, SR11-7, CSV)
            limit: Maximum certificates to return

        Returns:
            Audit response with records
        """
        response = self._client.post(
            f"{self.base_url}/api/v1/audit",
            json={"format": format, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

    def get_certificate(self, certificate_id: str) -> Certificate:
        """Get a specific certificate by ID."""
        response = self._client.get(
            f"{self.base_url}/api/v1/certificates/{certificate_id}"
        )
        response.raise_for_status()
        return Certificate.from_dict(response.json())

    def statistics(self) -> Dict[str, Any]:
        """Get sidecar statistics."""
        response = self._client.get(f"{self.base_url}/api/v1/statistics")
        response.raise_for_status()
        return response.json()

    def health(self) -> bool:
        """Check if sidecar is healthy."""
        try:
            response = self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    def close(self) -> None:
        """Close the client."""
        self._client.close()

    def __enter__(self) -> "SwarmIt":
        return self

    def __exit__(self, *args) -> None:
        self.close()


class AsyncSwarmIt:
    """Async version of SwarmIt client."""

    def __init__(
        self,
        url: str = "http://localhost:8080",
        timeout: float = 30.0,
    ):
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def certify(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        context: Optional[str] = None,
        policy: str = "default",
    ) -> Certificate:
        """Async version of certify."""
        response = await self._client.post(
            f"{self.base_url}/api/v1/certify",
            json={
                "prompt": prompt,
                "model_id": model_id,
                "context": context,
                "policy": policy,
            },
        )
        response.raise_for_status()
        return Certificate.from_dict(response.json())

    async def validate(
        self,
        certificate_id: str,
        validation_type: ValidationType,
        score: float,
        failed: bool = False,
    ) -> Dict[str, Any]:
        """Async version of validate."""
        response = await self._client.post(
            f"{self.base_url}/api/v1/validate",
            json={
                "certificate_id": certificate_id,
                "validation_type": validation_type.value,
                "score": score,
                "failed": failed,
            },
        )
        response.raise_for_status()
        return response.json()

    async def health(self) -> bool:
        """Check if sidecar is healthy."""
        try:
            response = await self._client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncSwarmIt":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
