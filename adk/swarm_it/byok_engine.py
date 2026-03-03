"""
BYOK (Bring Your Own Key) Engine - Copilot SDK Pattern
Local RSCT certification using customer's LLM credentials.
"""

import os
import torch
import hashlib
import uuid
from typing import Dict, Any, Optional
from datetime import datetime


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
        rotor_checkpoint: str = "trained_rotor_universal64.pt",
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
            self.bedrock_client = boto3.client(
                "bedrock-runtime",
                aws_access_key_id=self.api_key,
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=os.environ.get("AWS_REGION", "us-east-1")
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
                print(f"[BYOK] Falling back to hash-based approximation")
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
        kappa = min(R, S)  # Simplified kappa
        sigma = N / (R + S + N)

        # 4. Apply gate logic
        decision, gate_reached, reason = self._apply_gates(R, S, N, kappa)

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
            "decision": decision,
            "gate_reached": gate_reached,
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

    def _apply_gates(self, R: float, S: float, N: float, kappa: float):
        """
        Apply RSCT quality gates.

        Returns:
            (decision, gate_reached, reason)
        """
        # Gate 1: Integrity (N < 0.7)
        if N > 0.7:
            return "REJECT", 1, f"High noise: N={N:.3f} (threshold: 0.5)"

        # Gate 2: Noise (N < 0.5)
        if N > self.thresholds.get("N", 0.5):
            return "BLOCK", 2, f"Noise threshold: N={N:.3f}"

        # Gate 3: Relevance (R >= threshold)
        if R < self.thresholds.get("R", 0.3):
            return "BLOCK", 3, f"Low relevance: R={R:.3f}"

        # Gate 4: Stability (S >= threshold)
        if S < self.thresholds.get("S", 0.4):
            return "REPAIR", 4, f"Low stability: S={S:.3f}"

        # Gate 5: Compatibility (kappa >= threshold)
        if kappa < self.thresholds.get("kappa", 0.7):
            return "BLOCK", 5, f"Low compatibility: kappa={kappa:.3f}"

        # All gates passed
        return "EXECUTE", 5, f"All gates passed (kappa={kappa:.3f})"

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
