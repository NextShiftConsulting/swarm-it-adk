"""
BYOK (Bring Your Own Key) Engine - Copilot SDK Pattern
Local RSCT certification using customer's LLM credentials.

P18 Compliance: Credentials via swarm-it-auth when available.
"""

import os
import torch
import hashlib
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from yrsn_controlplane import SequentialGatekeeper

from ._compat import to_certificate_estimate
from ._config_bridge import thresholds_to_config

# P18 v3.0 - Unified credential access
try:
    from swarm_auth import get_credential as _get_credential
except ImportError:
    # Fallback to environment variables
    def _get_credential(key: str, default: Optional[str] = None) -> Optional[str]:
        return os.environ.get(key, default)


class BYOKEngine:
    """
    Local RSCT engine using customer's embedding provider.

    Inspired by GitHub Copilot SDK's BYOK mode.

    Users can run RSCT certification without swarm-it subscription
    by bringing their own OpenAI/MIMO/Bedrock API keys.

    Usage:
        >>> engine = BYOKEngine(
        ...     provider="openai",
        ...     api_key=os.environ["OPENAI_API_KEY"],
        ...     embedding_model="text-embedding-3-small"
        ... )
        >>> cert = engine.certify("What is quantum computing?")
        >>> print(cert["decision"])
        EXECUTE
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        embedding_model: str = "text-embedding-3-small",
        rotor_checkpoint: str = "rotor_64_universal_titan_v1.pt",
        thresholds: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize BYOK engine.

        Args:
            provider: "openai", "mimo", or "bedrock"
            api_key: Provider API key
            embedding_model: Embedding model name
            rotor_checkpoint: Path to yrsn rotor checkpoint
            thresholds: Custom thresholds (uses defaults if None)
        """
        self.provider = provider
        self.api_key = api_key
        self.embedding_model = embedding_model
        self.rotor_checkpoint = rotor_checkpoint

        # Default thresholds (universal64 policy)
        self.thresholds = thresholds or {
            "kappa": 0.7,
            "R": 0.3,
            "S": 0.4,
            "N": 0.5,
        }

        # Controlplane gatekeeper (canonical gate logic)
        self._gatekeeper = SequentialGatekeeper(thresholds_to_config(self.thresholds))

        # Initialize embedding client
        self.embed_client = self._init_embedding_client()

        # Initialize yrsn rotor (lazy load)
        self.rotor = None

    def _init_embedding_client(self):
        """Initialize embedding provider client."""
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self.api_key)

        elif self.provider == "mimo":
            from openai import OpenAI
            return OpenAI(
                base_url="https://api.mimo.ai/v1",
                api_key=self.api_key
            )

        elif self.provider == "bedrock":
            # Bedrock uses boto3
            import boto3
            # P18 compliant: credentials via swarm-it-auth
            aws_secret = _get_credential("AWS_SECRET_ACCESS_KEY") or ""
            aws_region = _get_credential("AWS_REGION") or "us-east-1"
            self.bedrock_client = boto3.client(
                "bedrock-runtime",
                aws_access_key_id=self.api_key,
                aws_secret_access_key=aws_secret,
                region_name=aws_region
            )
            return None  # Bedrock doesn't use OpenAI client

        else:
            raise ValueError(
                f"Unsupported provider: {self.provider}. "
                f"Use 'openai', 'mimo', or 'bedrock'"
            )

    def _load_rotor(self):
        """Lazy load yrsn rotor."""
        if self.rotor is None:
            try:
                from yrsn.core.decomposition import HybridSimplexRotor
                # HybridSimplexRotor is instantiated directly (embed_dim=64 is standard)
                self.rotor = HybridSimplexRotor(embed_dim=64)
            except Exception as e:
                print(f"[BYOK] Warning: Failed to load rotor: {e}")
                print("[BYOK] Falling back to hash-based approximation")
                self.rotor = None  # Will use fallback

    def _get_embedding(self, text: str) -> torch.Tensor:
        """
        Get embedding vector from provider.

        Args:
            text: Text to embed

        Returns:
            Embedding tensor
        """
        if self.provider in ["openai", "mimo"]:
            response = self.embed_client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            embedding = response.data[0].embedding
            return torch.tensor(embedding, dtype=torch.float32)

        elif self.provider == "bedrock":
            # Bedrock Titan embeddings
            import json
            response = self.bedrock_client.invoke_model(
                modelId=self.embedding_model,  # e.g., "amazon.titan-embed-text-v1"
                body=json.dumps({"inputText": text})
            )
            result = json.loads(response["body"].read())
            embedding = result.get("embedding", [])
            return torch.tensor(embedding, dtype=torch.float32)

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def certify(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate certificate using customer's embedding provider.

        Args:
            prompt: Text to certify
            **kwargs: Additional metadata

        Returns:
            Certificate dictionary

        Example:
            >>> cert = engine.certify("What is 2+2?")
            >>> print(f"R={cert['R']:.3f}, Decision={cert['decision']}")
            R=0.683, Decision=EXECUTE
        """
        # 1. Get embedding using customer's API key
        embedding = self._get_embedding(prompt)

        # 2. Decompose using yrsn rotor
        self._load_rotor()

        if self.rotor is not None:
            # Use real yrsn rotor
            # Ensure embedding has batch dimension [1, embed_dim]
            if embedding.dim() == 1:
                embedding = embedding.unsqueeze(0)

            # Rotor returns dict with 'R', 'S', 'N' tensors
            rsn_dict = self.rotor(embedding)
            R = float(rsn_dict['R'][0])
            S = float(rsn_dict['S'][0])
            N = float(rsn_dict['N'][0])
        else:
            # Fall back to hash-based approximation
            R, S, N = self._hash_based_rsn(prompt)

        # 3. Compute metrics
        alpha = R / (R + N) if (R + N) > 0 else 0.0
        kappa = 0.5 + 0.3 * R  # Simplified kappa estimate
        sigma = N / (R + S + N)

        # 4. Delegate gate evaluation to controlplane gatekeeper
        from ._compat import from_gatekeeper_result
        from .local.engine import _gate_identifier_to_int

        cert_estimate = to_certificate_estimate(
            R=R, S=S, N=N, kappa_gate=kappa, sigma=sigma, alpha=alpha,
        )
        gk_result = self._gatekeeper.evaluate(cert_estimate)
        decision = from_gatekeeper_result(gk_result)
        gate = _gate_identifier_to_int(gk_result.gate_reached)
        reason = f"{gk_result.decision.value} at {gk_result.gate_reached.value}"

        # 5. Estimate cost
        cost_usd = self._estimate_cost(prompt)

        # 6. Return certificate
        return {
            "id": f"byok-{uuid.uuid4()}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "R": R,
            "S": S,
            "N": N,
            "alpha": alpha,
            "kappa": kappa,
            "sigma": sigma,
            "decision": decision.value,
            "gate_decision": decision,
            "gate_reached": gate,
            "reason": reason,
            "policy": "byok",
            "raw": {
                "_byok_mode": True,
                "_provider": self.provider,
                "_embedding_model": self.embedding_model,
                "_cost_usd": cost_usd,
                "_has_rotor": self.rotor is not None,
            }
        }

    def _hash_based_rsn(self, text: str):
        """
        Hash-based RSN fallback (if rotor unavailable).

        Args:
            text: Text to decompose

        Returns:
            (R, S, N) tuple
        """
        h = hashlib.sha256(text.encode()).hexdigest()
        raw_r = int(h[0:8], 16) / 0xFFFFFFFF
        raw_s = int(h[8:16], 16) / 0xFFFFFFFF
        raw_n = int(h[16:24], 16) / 0xFFFFFFFF

        # Normalize to simplex
        total = raw_r + raw_s + raw_n
        return (raw_r / total, raw_s / total, raw_n / total)

    def _estimate_cost(self, text: str) -> float:
        """
        Estimate API cost for this certification.

        Args:
            text: Input text

        Returns:
            Estimated cost in USD
        """
        # Rough token count
        tokens = len(text.split())

        # Embedding costs (as of 2026)
        costs = {
            "openai": 0.00002,  # text-embedding-3-small
            "mimo": 0.00001,    # mimo-embed-v1
            "bedrock": 0.0001,  # amazon.titan-embed
        }

        base_cost = costs.get(self.provider, 0.00002)
        return base_cost * (tokens / 1000)


class BYOKClient:
    """
    Swarm-it-adk client with BYOK engine.

    Drop-in replacement for SwarmIt client that uses customer's LLM keys.

    Usage:
        >>> client = BYOKClient(
        ...     provider="openai",
        ...     api_key=os.environ["OPENAI_API_KEY"]
        ... )
        >>> cert = client.certify("What is AI?")
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        embedding_model: str = "text-embedding-3-small",
        **kwargs
    ):
        """
        Initialize BYOK client.

        Args:
            provider: "openai", "mimo", or "bedrock"
            api_key: Provider API key
            embedding_model: Embedding model name
            **kwargs: Additional arguments for BYOKEngine
        """
        self.engine = BYOKEngine(
            provider=provider,
            api_key=api_key,
            embedding_model=embedding_model,
            **kwargs
        )

    def certify(self, context: str, **kwargs):
        """Certify using BYOK engine."""
        return self.engine.certify(context, **kwargs)

    def get_models(self):
        """Get available models (local registry)."""
        from .models import get_models
        return get_models()
