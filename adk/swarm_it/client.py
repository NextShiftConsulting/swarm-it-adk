"""
Swarm It Core Client

P18 Compliance: Credentials via swarm-it-auth when available.

Handles certification requests and gate decisions.
"""

import os
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
import httpx

from ._compat import GateDecision

# P18 v3.0 - Unified credential access
try:
    from swarm_auth import get_credential as _get_credential
except ImportError:
    # Fallback to environment variables
    def _get_credential(key: str, default: Optional[str] = None) -> Optional[str]:
        return os.environ.get(key, default)


@dataclass
class RSCTModeDetail:
    """RSCT mode taxonomy detail."""
    group: int  # 0=proceed, 1=encoding, 2=dynamics, 3=semantic, 4=execution
    type: int   # Subtype within group
    name: str   # Human-readable name
    description: str  # Trigger condition


@dataclass
class Certificate:
    """RSCT Certificate returned from certification."""

    id: str
    timestamp: str

    # RSN decomposition (R + S_sup + N = 1)
    R: float  # Relevance
    S_sup: float  # Support (S_sup in RSCT)
    N: float  # Novelty/Noise

    # Quality metrics
    alpha: float  # Purity: R/(R+N)
    kappa_coupling: float  # Compatibility (kappa_compat)
    sigma: float  # Turbulence

    # Gate result
    decision: GateDecision
    gate_reached: int
    reason: str

    # RSCT mode (from API - authoritative)
    rsct_mode: Optional[str] = None
    rsct_mode_detail: Optional[RSCTModeDetail] = None

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
        # Simplified: higher R and kappa_coupling = more margin
        return min(self.R, self.kappa_coupling)

    def to_dict(self) -> Dict[str, Any]:
        """Export certificate as dict."""
        result = {
            "certificate_id": self.id,
            "timestamp": self.timestamp,
            "R": self.R,
            "S": self.S_sup,
            "N": self.N,
            "alpha": self.alpha,
            "kappa_coupling": self.kappa_coupling,
            "sigma": self.sigma,
            "gate_decision": self.decision.value,
            "gate_reached": self.gate_reached,
            "reason": self.reason,
            "policy": self.policy,
            "rsct_mode": self.rsct_mode,
        }
        if self.rsct_mode_detail:
            result["rsct_mode_detail"] = {
                "group": self.rsct_mode_detail.group,
                "type": self.rsct_mode_detail.type,
                "name": self.rsct_mode_detail.name,
                "description": self.rsct_mode_detail.description,
            }
        return result


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
            api_key: API key (or via swarm-it-auth SWARM_IT_API_KEY)
            base_url: API endpoint (or via SWARM_IT_BASE_URL)
            timeout: Request timeout in seconds
            policy: Default certification policy
        """
        # P18 compliant: credentials via swarm-it-auth
        self.api_key = api_key or _get_credential("SWARM_IT_API_KEY")
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

        # Routing advisory namespaces
        from swarm_it.breakpoint import BreakpointNamespace, ProfilesNamespace
        self.breakpoint = BreakpointNamespace(self._client, self.base_url)
        self.profiles = ProfilesNamespace(self._client, self.base_url)

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

            except httpx.RequestError:
                # Fall back to local mode
                self._local_mode = True

        # Local fallback (hash-based, not production-grade)
        return self._local_certify(context, policy or self.default_policy)

    def certify_pair(
        self,
        premise: str,
        hypothesis: str,
        policy: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Certificate:
        """
        Certify a premise-hypothesis pair (output certification).

        Uses /certify/pair with text fallback — the server encodes both
        texts and runs them through the trained S017 edge head.

        For output certification: premise=input prompt, hypothesis=LLM output.

        Args:
            premise: The input/reference text (e.g., user prompt)
            hypothesis: The output text to certify (e.g., LLM response)
            policy: Certification policy (uses default if not specified)
            metadata: Optional metadata

        Returns:
            Certificate with gate decision

        Raises:
            CertificationError: If certification fails
            AuthenticationError: If API key is invalid
        """
        from .exceptions import CertificationError, AuthenticationError

        if not self._local_mode and self.api_key:
            try:
                response = self._client.post(
                    "/certify/pair",
                    json={
                        "premise_text": premise,
                        "hypothesis_text": hypothesis,
                        "policy": policy or self.default_policy,
                    },
                )

                if response.status_code == 401:
                    raise AuthenticationError("Invalid API key")

                if response.status_code != 200:
                    raise CertificationError(
                        f"Pair certification failed: {response.text}"
                    )

                data = response.json()
                return self._parse_certificate(data)

            except httpx.RequestError:
                self._local_mode = True

        # Local fallback: certify the hypothesis text
        # (pair semantics degrade to unary in local mode)
        return self._local_certify(hypothesis, policy or self.default_policy)

    def certify_batch(
        self,
        items: List[Dict[str, Any]],
        continue_on_error: bool = True,
        max_parallel: int = 10,
    ) -> Dict[str, Any]:
        """
        Certify multiple items in a single API call.

        Args:
            items: List of items to certify, each with:
                - id: Client-provided ID for correlation
                - prompt: Text to certify
                - context: Optional context
                - policy: Optional policy override
            continue_on_error: Continue if individual items fail
            max_parallel: Max parallel certifications (1-50)

        Returns:
            Dict with:
                - certificates: List of {id, certificate, error}
                - stats: {total, succeeded, failed, duration_ms}

        Example:
            >>> items = [
            ...     {"id": "msg_1", "prompt": "First message"},
            ...     {"id": "msg_2", "prompt": "Second message"},
            ... ]
            >>> result = swarm.certify_batch(items)
            >>> for cert_result in result["certificates"]:
            ...     if cert_result.get("error"):
            ...         print(f"Failed: {cert_result['error']}")
            ...     else:
            ...         print(f"Certified: {cert_result['certificate'].decision}")
        """
        from .exceptions import CertificationError, AuthenticationError

        if not items:
            return {
                "certificates": [],
                "stats": {"total": 0, "succeeded": 0, "failed": 0, "duration_ms": 0},
            }

        # API call
        if not self._local_mode and self.api_key:
            try:
                response = self._client.post(
                    "/certify/batch",
                    json={
                        "items": items,
                        "options": {
                            "continue_on_error": continue_on_error,
                            "max_parallel": max_parallel,
                        },
                    },
                )

                if response.status_code == 401:
                    raise AuthenticationError("Invalid API key")

                if response.status_code != 200:
                    raise CertificationError(
                        f"Batch certification failed: {response.text}"
                    )

                data = response.json()

                # Parse certificates
                parsed_certs = []
                for cert_result in data.get("certificates", []):
                    if cert_result.get("certificate"):
                        parsed_certs.append({
                            "id": cert_result["id"],
                            "certificate": self._parse_certificate(cert_result["certificate"]),
                        })
                    else:
                        parsed_certs.append({
                            "id": cert_result["id"],
                            "error": cert_result.get("error", "Unknown error"),
                        })

                return {
                    "certificates": parsed_certs,
                    "stats": data.get("stats", {}),
                }

            except httpx.RequestError:
                self._local_mode = True

        # Local fallback: loop through items
        start = time.perf_counter()
        results = []
        succeeded = 0
        failed = 0

        for item in items:
            try:
                cert = self._local_certify(
                    item.get("prompt", ""),
                    item.get("policy", self.default_policy),
                )
                results.append({"id": item["id"], "certificate": cert})
                succeeded += 1
            except Exception as e:
                if continue_on_error:
                    results.append({"id": item["id"], "error": str(e)})
                    failed += 1
                else:
                    raise

        duration_ms = (time.perf_counter() - start) * 1000

        return {
            "certificates": results,
            "stats": {
                "total": len(items),
                "succeeded": succeeded,
                "failed": failed,
                "duration_ms": round(duration_ms, 2),
            },
        }

    def certify_swarm(
        self,
        swarm_id: str,
        agents: List[Dict[str, Any]],
        topology: Optional[Dict[str, Any]] = None,
        task_encoding: Optional[str] = None,
        policy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Certify an entire swarm's output.

        Args:
            swarm_id: Unique swarm identifier
            agents: List of agent outputs, each with:
                - agent_id: Unique agent identifier
                - context: What the agent was asked to do
                - output: What the agent produced
                - role: Optional agent role
            topology: Optional swarm topology:
                - type: "dag", "star", "mesh", "pipeline"
                - edges: [{from, to}, ...]
            task_encoding: Swarm-level task description
            policy: Certification policy

        Returns:
            Dict with:
                - swarm_id: The swarm ID
                - swarm_certificate: Aggregate swarm certificate
                - agent_certificates: Per-agent certificates
                - interface_scores: Compatibility between agents
                - timestamp: ISO timestamp

        Example:
            >>> result = swarm.certify_swarm(
            ...     swarm_id="my-swarm",
            ...     agents=[
            ...         {"agent_id": "a1", "context": "...", "output": "..."},
            ...         {"agent_id": "a2", "context": "...", "output": "..."},
            ...     ],
            ...     topology={"type": "pipeline", "edges": [{"from": "a1", "to": "a2"}]},
            ... )
            >>> print(f"Swarm decision: {result['swarm_certificate']['decision']}")
            >>> print(f"Consensus: {result['swarm_certificate']['consensus']}")
        """
        from .exceptions import CertificationError, AuthenticationError

        if not agents:
            raise CertificationError("At least one agent required")

        # API call
        if not self._local_mode and self.api_key:
            try:
                request_body = {"agents": agents}
                if topology:
                    request_body["topology"] = topology
                if task_encoding:
                    request_body["task_encoding"] = task_encoding
                if policy:
                    request_body["policy"] = policy

                response = self._client.post(
                    f"/swarms/{swarm_id}/certify",
                    json=request_body,
                )

                if response.status_code == 401:
                    raise AuthenticationError("Invalid API key")

                if response.status_code != 200:
                    raise CertificationError(
                        f"Swarm certification failed: {response.text}"
                    )

                return response.json()

            except httpx.RequestError:
                self._local_mode = True

        # Local fallback: certify each agent and aggregate
        from datetime import datetime

        agent_certs = []
        min_kappa = 1.0
        weakest_link = None
        total_r, total_s, total_n = 0.0, 0.0, 0.0

        for agent in agents:
            cert = self._local_certify(
                agent.get("output", ""),
                policy or self.default_policy,
            )
            agent_cert = {
                "agent_id": agent["agent_id"],
                "R": cert.R,
                "S": cert.S_sup,
                "N": cert.N,
                "kappa_coupling": cert.kappa_coupling,
                "decision": cert.decision.value,
                "rsct_mode": cert.rsct_mode,
            }
            agent_certs.append(agent_cert)

            total_r += cert.R
            total_s += cert.S_sup
            total_n += cert.N

            if cert.kappa_coupling < min_kappa:
                min_kappa = cert.kappa_coupling
                weakest_link = agent["agent_id"]

        n_agents = len(agents)
        avg_r = total_r / n_agents
        avg_s = total_s / n_agents
        avg_n = total_n / n_agents

        # Determine swarm decision from weakest link
        if min_kappa >= 0.7:
            swarm_decision = "EXECUTE"
        elif min_kappa >= 0.4:
            swarm_decision = "REPAIR"
        else:
            swarm_decision = "BLOCK"

        return {
            "swarm_id": swarm_id,
            "swarm_certificate": {
                "R": round(avg_r, 4),
                "S": round(avg_s, 4),
                "N": round(avg_n, 4),
                "kappa_coupling": round(min_kappa, 4),
                "decision": swarm_decision,
                "rsct_mode": "0.0" if swarm_decision == "EXECUTE" else "4.1",
                "consensus": 1.0,  # Local mode doesn't compute real consensus
                "weakest_link": weakest_link,
            },
            "agent_certificates": agent_certs,
            "interface_scores": [],  # Local mode doesn't compute interfaces
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def _parse_certificate(self, data: Dict[str, Any]) -> Certificate:
        """Parse API response into Certificate."""
        # Handle both RSCT naming (S_sup) and simplified (S)
        s_value = data.get("S_sup", data.get("S", 0.0))

        # Parse gate decision
        decision_str = data.get("gate_decision", data.get("decision", "EXECUTE"))
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

        # Parse rsct_mode (authoritative from API)
        rsct_mode = data.get("rsct_mode")
        rsct_mode_detail = None
        if data.get("rsct_mode_detail"):
            detail = data["rsct_mode_detail"]
            rsct_mode_detail = RSCTModeDetail(
                group=detail.get("group", 0),
                type=detail.get("type", 0),
                name=detail.get("name", ""),
                description=detail.get("description", ""),
            )

        return Certificate(
            id=data.get("certificate_id", data.get("id", "")),
            timestamp=data.get("timestamp", ""),
            R=data.get("R", 0.0),
            S_sup=s_value,
            N=data.get("N", 0.0),
            alpha=data.get("alpha", 0.0),
            kappa_coupling=data.get("kappa_compat", data.get("kappa", 0.0)),
            sigma=data.get("sigma", 0.0),
            decision=decision,
            gate_reached=data.get("gate_reached", 0),
            reason=data.get("gate_reason", data.get("reason", "")),
            rsct_mode=rsct_mode,
            rsct_mode_detail=rsct_mode_detail,
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
        Gate evaluation delegates to yrsn-controlplane SequentialGatekeeper.
        """
        import uuid
        from datetime import datetime

        from yrsn_controlplane import SequentialGatekeeper

        from ._compat import from_gatekeeper_result, to_certificate_estimate

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

        # Compute derived signals
        alpha = R / (R + N) if (R + N) > 0 else 0.0
        kappa = 0.5 + 0.3 * R  # Simplified kappa estimate
        sigma = 0.3  # Default turbulence

        # Delegate gate evaluation to controlplane
        cert_estimate = to_certificate_estimate(
            R=R, S_sup=S, N=N, kappa_compat=kappa, sigma=sigma, alpha=alpha,
        )
        gk_result = SequentialGatekeeper().evaluate(cert_estimate)
        decision = from_gatekeeper_result(gk_result)

        from .local.engine import _gate_identifier_to_int
        gate = _gate_identifier_to_int(gk_result.gate_reached)
        reason = f"Local mode: {gk_result.decision.value} at {gk_result.gate_reached.value}"

        return Certificate(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            R=R,
            S_sup=S,
            N=N,
            alpha=alpha,
            kappa_coupling=kappa,
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
