"""
Swarm It Core Client

Handles certification requests and gate decisions.
"""

import os
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Callable, List
import httpx


class GateDecision(Enum):
    """RSCT gate decisions."""
    EXECUTE = "EXECUTE"
    REJECT = "REJECT"
    BLOCK = "BLOCK"
    RE_ENCODE = "RE_ENCODE"
    REPAIR = "REPAIR"

    # Legacy compatibility
    PASS_FAST = "PASS_FAST"
    PASS_GUARDED = "PASS_GUARDED"

    @property
    def allowed(self) -> bool:
        """Returns True if execution should proceed."""
        return self in (
            GateDecision.EXECUTE,
            GateDecision.PASS_FAST,
            GateDecision.PASS_GUARDED,
        )


@dataclass
class Certificate:
    """RSCT Certificate returned from certification."""

    id: str
    timestamp: str

    # RSN decomposition (R + S + N = 1)
    R: float  # Relevance
    S: float  # Support (S_sup in RSCT)
    N: float  # Novelty/Noise

    # Quality metrics
    alpha: float  # Purity: R/(R+N)
    kappa: float  # Compatibility (kappa_gate)
    sigma: float  # Turbulence

    # Gate result
    decision: GateDecision
    gate_reached: int
    reason: str

    # Metadata
    policy: str = "default"
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        """Convenience: is execution allowed?"""
        return self.decision.allowed

    @property
    def margin(self) -> float:
        """Safety margin: how far from rejection threshold."""
        # Simplified: higher R and kappa = more margin
        return min(self.R, self.kappa)

    def to_dict(self) -> Dict[str, Any]:
        """Export certificate as dict."""
        return {
            "certificate_id": self.id,
            "timestamp": self.timestamp,
            "R": self.R,
            "S": self.S,
            "N": self.N,
            "alpha": self.alpha,
            "kappa": self.kappa,
            "sigma": self.sigma,
            "gate_decision": self.decision.value,
            "gate_reached": self.gate_reached,
            "reason": self.reason,
            "policy": self.policy,
        }


class SwarmIt:
    """
    Swarm It client for RSCT certification.

    Usage:
        swarm = SwarmIt(api_key="your-key")

        # Certify a prompt
        cert = swarm.certify("What is the capital of France?")

        if cert.allowed:
            # Safe to execute
            response = my_llm(prompt)
        else:
            # Blocked - handle gracefully
            print(f"Blocked: {cert.reason}")
    """

    DEFAULT_BASE_URL = "https://api.swarm-it.dev/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        policy: str = "default",
    ):
        """
        Initialize Swarm It client.

        Args:
            api_key: API key (or set SWARM_IT_API_KEY env var)
            base_url: API endpoint (or set SWARM_IT_BASE_URL env var)
            timeout: Request timeout in seconds
            policy: Default certification policy
        """
        self.api_key = api_key or os.environ.get("SWARM_IT_API_KEY")
        self.base_url = (
            base_url
            or os.environ.get("SWARM_IT_BASE_URL")
            or self.DEFAULT_BASE_URL
        )
        self.timeout = timeout
        self.default_policy = policy

        # HTTP client
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._headers(),
        )

        # Local fallback mode (when API unavailable)
        self._local_mode = False

        # Models cache
        self._models_cache: Optional[List[Dict[str, Any]]] = None

    def _headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def certify(
        self,
        context: str,
        policy: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Certificate:
        """
        Certify a context/prompt for execution readiness.

        Args:
            context: The prompt or context to certify
            policy: Certification policy (uses default if not specified)
            metadata: Optional metadata (user_id, session_id, etc.)

        Returns:
            Certificate with gate decision

        Raises:
            CertificationError: If certification fails
            AuthenticationError: If API key is invalid
        """
        from .exceptions import CertificationError, AuthenticationError

        # Try API first
        if not self._local_mode and self.api_key:
            try:
                response = self._client.post(
                    "/certify",
                    json={
                        "context": context,
                        "policy": policy or self.default_policy,
                        "metadata": metadata or {},
                    },
                )

                if response.status_code == 401:
                    raise AuthenticationError("Invalid API key")

                if response.status_code != 200:
                    raise CertificationError(
                        f"Certification failed: {response.text}"
                    )

                data = response.json()
                return self._parse_certificate(data)

            except httpx.RequestError as e:
                # Fall back to local mode
                self._local_mode = True

        # Local fallback (hash-based, not production-grade)
        return self._local_certify(context, policy or self.default_policy)

    def _parse_certificate(self, data: Dict[str, Any]) -> Certificate:
        """Parse API response into Certificate."""
        # Handle both RSCT naming (S_sup) and simplified (S)
        s_value = data.get("S_sup", data.get("S", 0.0))

        # Parse gate decision
        decision_str = data.get("gate_decision", "EXECUTE")
        try:
            decision = GateDecision(decision_str)
        except ValueError:
            # Map legacy decisions
            if decision_str.startswith("PASS"):
                decision = GateDecision.EXECUTE
            elif decision_str.startswith("REJECT"):
                decision = GateDecision.REJECT
            else:
                decision = GateDecision.BLOCK

        return Certificate(
            id=data.get("certificate_id", ""),
            timestamp=data.get("timestamp", ""),
            R=data.get("R", 0.0),
            S=s_value,
            N=data.get("N", 0.0),
            alpha=data.get("alpha", 0.0),
            kappa=data.get("kappa_gate", data.get("kappa", 0.0)),
            sigma=data.get("sigma", 0.0),
            decision=decision,
            gate_reached=data.get("gate_reached", 0),
            reason=data.get("gate_reason", data.get("reason", "")),
            policy=data.get("policy", "default"),
            raw=data,
        )

    def _local_certify(self, context: str, policy: str) -> Certificate:
        """
        Local fallback certification (hash-based).

        WARNING: This is NOT production-grade. It's for:
        - Testing without API access
        - Development/debugging
        - Graceful degradation

        Production MUST use the API with trained RSCT models.
        """
        import uuid
        from datetime import datetime

        # Hash-based pseudo-RSN (deterministic but not RSCT-compliant)
        h = hashlib.sha256(context.encode()).hexdigest()
        raw_r = int(h[0:8], 16) / 0xFFFFFFFF
        raw_s = int(h[8:16], 16) / 0xFFFFFFFF
        raw_n = int(h[16:24], 16) / 0xFFFFFFFF

        # Normalize to simplex
        total = raw_r + raw_s + raw_n
        R = raw_r / total
        S = raw_s / total
        N = raw_n / total

        # Simple gating logic
        alpha = R / (R + N) if (R + N) > 0 else 0.0
        kappa = 0.5 + 0.3 * R  # Simplified kappa estimate
        sigma = 0.3  # Default turbulence

        # Gate decision
        if N > 0.5:
            decision = GateDecision.REJECT
            reason = f"High noise: N={N:.3f}"
            gate = 1
        elif kappa < 0.4:
            decision = GateDecision.BLOCK
            reason = f"Low compatibility: kappa={kappa:.3f}"
            gate = 3
        else:
            decision = GateDecision.EXECUTE
            reason = "Local mode: passed basic checks"
            gate = 5

        return Certificate(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            R=R,
            S=S,
            N=N,
            alpha=alpha,
            kappa=kappa,
            sigma=sigma,
            decision=decision,
            gate_reached=gate,
            reason=reason,
            policy=policy,
            raw={"_local_mode": True},
        )

    def gate(
        self,
        func: Optional[Callable] = None,
        *,
        policy: Optional[str] = None,
        on_block: Optional[Callable[[Certificate], Any]] = None,
    ):
        """
        Decorator to gate function execution with certification.

        Usage:
            @swarm.gate
            def ask_llm(prompt):
                return openai.chat.completions.create(...)

            # With custom block handler
            @swarm.gate(on_block=lambda cert: "Blocked!")
            def ask_llm(prompt):
                ...

        The first string argument to the function is used as the context.
        """
        from .decorators import _create_gate_decorator

        decorator = _create_gate_decorator(
            self,
            policy=policy,
            on_block=on_block,
        )

        if func is not None:
            return decorator(func)
        return decorator

    def get_models(self) -> List[Dict[str, Any]]:
        """
        Get available certification models (Copilot SDK pattern).

        Returns:
            List of model configurations

        Example:
            >>> swarm = SwarmIt()
            >>> models = swarm.get_models()
            >>> for model in models:
            ...     print(f"{model['id']}: {model['name']}")
            universal64: Universal Rotor (64-dim)
            strict: Strict Policy
            ...
        """
        if self._models_cache:
            return self._models_cache

        # Try API first
        if not self._local_mode and self.api_key:
            try:
                response = self._client.get("/models")
                if response.status_code == 200:
                    self._models_cache = response.json().get("models", [])
                    return self._models_cache
            except httpx.RequestError:
                pass

        # Fall back to local model registry
        from .models import get_models
        self._models_cache = get_models()
        return self._models_cache

    def create_conversation(self, conversation_id: Optional[str] = None):
        """
        Create a multi-turn conversation context (Copilot SDK pattern).

        Args:
            conversation_id: Optional conversation ID

        Returns:
            Conversation instance

        Example:
            >>> swarm = SwarmIt()
            >>> conv = swarm.create_conversation()
            >>> cert1 = conv.send("What is quantum computing?")
            >>> cert2 = conv.send("Can you give an example?")  # Has context
        """
        from .conversation import Conversation
        return Conversation(client=self, conversation_id=conversation_id)

    def close(self):
        """Close HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
