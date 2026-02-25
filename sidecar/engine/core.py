"""
RSCT Engine Core - Uses injected adapters.

Hex arch: Engine depends on PORTS, not implementations.
Adapters injected at construction time.
"""

from typing import Dict, Any, Optional, List
from ..ports import EmbeddingPort, RSNPort
from .patterns import get_detector


class RSCTEngine:
    """
    RSCT Certification Engine.

    Depends on ports (interfaces), not implementations.
    """

    def __init__(
        self,
        embedding_adapter: EmbeddingPort,
        rsn_adapter: RSNPort,
    ):
        self.embeddings = embedding_adapter
        self.rsn = rsn_adapter
        self.patterns = get_detector()

    def certify(self, prompt: str) -> Dict[str, Any]:
        """Certify a prompt."""

        # 1. Pattern pre-screen
        matches = self.patterns.detect(prompt)
        if matches and matches[0].score >= 0.9:
            return self._reject(prompt, matches[0].category)

        # 2. Get embeddings via adapter
        embeddings = self.embeddings.embed(prompt)

        # 3. Compute RSN via adapter
        rsn = self.rsn.compute(embeddings)
        R, S, N = rsn["R"], rsn["S"], rsn["N"]

        # 4. Gate decision
        kappa = R / (R + N) if (R + N) > 0 else 0.5
        decision, gate = self._gate(R, S, N, kappa)

        return {
            "R": round(R, 4),
            "S": round(S, 4),
            "N": round(N, 4),
            "kappa": round(kappa, 4),
            "decision": decision,
            "gate": gate,
            "allowed": decision in ("EXECUTE", "REPAIR"),
        }

    def _reject(self, prompt: str, reason: str) -> Dict[str, Any]:
        return {
            "R": 0.0, "S": 0.0, "N": 1.0,
            "kappa": 0.0,
            "decision": "REJECT",
            "gate": 0,
            "allowed": False,
            "reason": reason,
        }

    def _gate(self, R: float, S: float, N: float, kappa: float):
        if N >= 0.5:
            return "REJECT", 1
        if R < 0.3:
            return "BLOCK", 2
        if kappa < 0.7:
            return "REPAIR", 4
        return "EXECUTE", 5
