"""
Multi-Turn Conversation Management - Copilot SDK Pattern
Track certificate history and quality trends across conversation turns.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationTurn:
    """Single turn in a conversation."""
    turn_id: int
    prompt: str
    certificate: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class Conversation:
    """
    Multi-turn conversation with certificate history tracking.

    Inspired by GitHub Copilot SDK conversation API.
    State is managed CLIENT-SIDE (stateless server).

    Usage:
        >>> swarm = SwarmIt()
        >>> conv = swarm.create_conversation()
        >>>
        >>> # Multi-turn conversation
        >>> cert1 = conv.send("What is quantum computing?")
        >>> cert2 = conv.send("Can you give an example?")  # Has context from cert1
        >>> cert3 = conv.send("Explain the math.")  # Has context from cert1 + cert2
        >>>
        >>> # Analyze conversation
        >>> summary = conv.summary()
        >>> print(f"Success rate: {summary['success_rate']:.1%}")
    """

    def __init__(self, client, conversation_id: Optional[str] = None):
        """
        Initialize conversation.

        Args:
            client: SwarmIt client instance
            conversation_id: Optional conversation ID (auto-generated if not provided)
        """
        self.client = client
        self.conversation_id = conversation_id or f"conv-{hash(datetime.utcnow())}"
        self.turns: List[ConversationTurn] = []

    def send(
        self,
        prompt: str,
        include_context: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send prompt and track in conversation history.

        Args:
            prompt: User prompt to certify
            include_context: Include previous turns as context
            **kwargs: Additional arguments passed to client.certify()

        Returns:
            Certificate dictionary

        Example:
            >>> conv = swarm.create_conversation()
            >>> cert = conv.send("What is AI?")
            >>> print(cert['decision'])
            EXECUTE
        """
        # Build context from previous turns
        context_str = prompt
        if include_context and self.turns:
            context_str = self._build_context(prompt)

        # Certify with context
        cert = self.client.certify(
            context=context_str,
            metadata={"conversation_id": self.conversation_id},
            **kwargs
        )

        # Convert Certificate to dict if needed
        if hasattr(cert, 'to_dict'):
            cert_dict = cert.to_dict()
        else:
            cert_dict = cert

        # Record turn
        turn = ConversationTurn(
            turn_id=len(self.turns) + 1,
            prompt=prompt,
            certificate=cert_dict,
            metadata=kwargs
        )
        self.turns.append(turn)

        return cert_dict

    def _build_context(self, current_prompt: str) -> str:
        """
        Build conversation context from previous turns.

        Args:
            current_prompt: Current user prompt

        Returns:
            Context string with conversation history
        """
        # Include last 3 turns for context (to avoid token limits)
        recent_turns = self.turns[-3:]
        context_parts = [
            f"[Conversation history (last {len(recent_turns)} turns)]"
        ]

        for turn in recent_turns:
            context_parts.append(f"Turn {turn.turn_id}: {turn.prompt}")
            decision = turn.certificate.get("gate_decision", "UNKNOWN")
            context_parts.append(f"  -> Decision: {decision}")

        context_parts.append(f"\n[Current prompt]\n{current_prompt}")

        return "\n".join(context_parts)

    def get_history(self) -> List[ConversationTurn]:
        """
        Get full conversation history.

        Returns:
            List of ConversationTurn instances
        """
        return self.turns

    def get_quality_trend(self) -> Dict[str, List[float]]:
        """
        Analyze quality metrics over conversation.

        Returns:
            Dictionary of metric trends (kappa, alpha, sigma, R, S, N)

        Example:
            >>> trend = conv.get_quality_trend()
            >>> print(trend['kappa'])
            [0.75, 0.72, 0.68, 0.65]  # Degrading over time
        """
        return {
            "kappa": [turn.certificate.get("kappa", 0.0) for turn in self.turns],
            "alpha": [turn.certificate.get("alpha", 0.0) for turn in self.turns],
            "sigma": [turn.certificate.get("sigma", 0.0) for turn in self.turns],
            "R": [turn.certificate.get("R", 0.0) for turn in self.turns],
            "S": [turn.certificate.get("S", 0.0) for turn in self.turns],
            "N": [turn.certificate.get("N", 0.0) for turn in self.turns],
        }

    def detect_degradation(self, metric: str = "kappa", threshold: float = 0.1) -> bool:
        """
        Detect if quality is degrading over conversation.

        Args:
            metric: Metric to check ("kappa", "alpha", "R", etc.)
            threshold: Degradation threshold (e.g., 0.1 = 10% drop)

        Returns:
            True if metric degraded by more than threshold

        Example:
            >>> if conv.detect_degradation("kappa", threshold=0.15):
            ...     print("WARNING: Conversation quality degrading!")
        """
        trend = self.get_quality_trend().get(metric, [])
        if len(trend) < 2:
            return False

        first = trend[0]
        last = trend[-1]

        if first == 0:
            return False

        degradation = (first - last) / first
        return degradation > threshold

    def summary(self) -> Dict[str, Any]:
        """
        Get conversation summary with statistics.

        Returns:
            Summary dictionary with stats

        Example:
            >>> summary = conv.summary()
            >>> print(summary)
            {
                'conversation_id': 'conv-12345',
                'total_turns': 5,
                'blocked_turns': 1,
                'success_rate': 0.8,
                'avg_kappa': 0.72,
                'kappa_degradation': 0.15,
                'quality_trend': {...}
            }
        """
        total_turns = len(self.turns)
        if total_turns == 0:
            return {
                "conversation_id": self.conversation_id,
                "total_turns": 0,
                "blocked_turns": 0,
                "success_rate": 0.0,
            }

        # Count blocked turns
        blocked = sum(
            1 for t in self.turns
            if t.certificate.get("gate_decision") not in ["EXECUTE", "PASS_FAST", "PASS_GUARDED"]
        )

        # Calculate average metrics
        trend = self.get_quality_trend()
        avg_kappa = sum(trend["kappa"]) / len(trend["kappa"]) if trend["kappa"] else 0.0

        # Calculate degradation
        kappa_degradation = 0.0
        if len(trend["kappa"]) >= 2 and trend["kappa"][0] > 0:
            kappa_degradation = (trend["kappa"][0] - trend["kappa"][-1]) / trend["kappa"][0]

        return {
            "conversation_id": self.conversation_id,
            "total_turns": total_turns,
            "blocked_turns": blocked,
            "success_rate": (total_turns - blocked) / total_turns,
            "avg_kappa": avg_kappa,
            "kappa_degradation": kappa_degradation,
            "quality_trend": trend,
            "timestamps": {
                "start": self.turns[0].timestamp,
                "end": self.turns[-1].timestamp,
            },
        }

    def reset(self):
        """Reset conversation (clear all turns)."""
        self.turns = []

    def __len__(self):
        """Return number of turns."""
        return len(self.turns)

    def __repr__(self):
        return f"<Conversation id={self.conversation_id} turns={len(self.turns)}>"
