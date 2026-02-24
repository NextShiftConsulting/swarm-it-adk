"""
Swarm Topology Models

Defines agents, channels, and swarm structures for multi-agent certification.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class SolverType(Enum):
    """Types of solvers that agents can use."""

    TRANSFORMER = "transformer"  # LLM-based
    SYMBOLIC = "symbolic"  # Rule-based, SAT, theorem provers
    HYBRID = "hybrid"  # Mix of neural and symbolic
    TOOL = "tool"  # External tool/API
    HUMAN = "human"  # Human-in-the-loop

    @property
    def is_neural(self) -> bool:
        """Check if solver is neural-based."""
        return self in (SolverType.TRANSFORMER, SolverType.HYBRID)

    @property
    def requires_embedding(self) -> bool:
        """Check if solver requires embedding space."""
        return self in (SolverType.TRANSFORMER, SolverType.HYBRID)


class Modality(Enum):
    """Input/output modalities."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    CODE = "code"
    STRUCTURED = "structured"  # JSON, tables, etc.
    MULTIMODAL = "multimodal"


@dataclass
class Agent:
    """
    Agent in a swarm topology.

    Each agent has:
    - Identity (id, name, role)
    - Solver configuration (solver_type, modality)
    - Per-modality health scores (kappa_H, kappa_L, kappa_interface)
    """

    id: str
    name: str
    role: str

    # Solver configuration
    solver_type: SolverType = SolverType.TRANSFORMER
    modality: Modality = Modality.TEXT

    # Per-modality kappa (compatibility health)
    kappa_H: Optional[float] = None  # High-level (text/symbolic)
    kappa_L: Optional[float] = None  # Low-level (vision/signal)
    kappa_interface: Optional[float] = None  # Cross-modal

    # Additional metadata
    model: Optional[str] = None  # e.g., "gpt-4", "claude-3"
    config: Dict[str, Any] = field(default_factory=dict)

    @property
    def kappa_gate(self) -> float:
        """
        Enforced kappa: minimum of all modality kappas.

        This is the "weakest link" that determines agent health.
        """
        kappas = [k for k in [self.kappa_H, self.kappa_L, self.kappa_interface] if k is not None]
        if not kappas:
            return 0.5  # Default when no per-modality data
        return min(kappas)

    @property
    def kappa_modal(self) -> Dict[str, Optional[float]]:
        """Per-modality kappa as dict."""
        return {
            "H": self.kappa_H,
            "L": self.kappa_L,
            "interface": self.kappa_interface,
        }

    @property
    def is_multimodal(self) -> bool:
        """Check if agent has multimodal kappa data."""
        return self.kappa_H is not None and self.kappa_L is not None

    @property
    def hierarchy_gap(self) -> Optional[float]:
        """Gap between high-level and low-level kappa."""
        if self.kappa_H is not None and self.kappa_L is not None:
            return abs(self.kappa_H - self.kappa_L)
        return None

    @property
    def dominant_modality(self) -> Optional[str]:
        """Which modality has higher kappa."""
        if self.kappa_H is not None and self.kappa_L is not None:
            return "H" if self.kappa_H > self.kappa_L else "L"
        return None

    @property
    def health_status(self) -> str:
        """Agent health based on kappa_gate."""
        if self.kappa_gate >= 0.7:
            return "healthy"
        elif self.kappa_gate >= 0.4:
            return "degraded"
        else:
            return "critical"

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "solver_type": self.solver_type.value,
            "modality": self.modality.value,
            "kappa_gate": self.kappa_gate,
            "health_status": self.health_status,
        }

        if self.is_multimodal:
            result["kappa_modal"] = self.kappa_modal
            result["hierarchy_gap"] = self.hierarchy_gap
            result["dominant_modality"] = self.dominant_modality

        if self.model:
            result["model"] = self.model

        return result


@dataclass
class Channel:
    """
    Communication channel between agents.

    Channels represent how agents pass information:
    - Messages (text, structured data)
    - Tool calls (function invocations)
    - Memory sharing (shared context)
    - Delegation (task handoff)
    """

    source_id: str
    target_id: str
    channel_type: str  # "message", "tool_call", "memory_share", "delegation"

    # Channel modality
    modality: Modality = Modality.TEXT

    # Channel health
    kappa_interface: Optional[float] = None  # Cross-agent compatibility
    latency_ms: Optional[float] = None
    bandwidth: Optional[float] = None  # Messages per second

    # Metadata
    config: Dict[str, Any] = field(default_factory=dict)

    @property
    def health_status(self) -> str:
        """Channel health based on kappa_interface."""
        if self.kappa_interface is None:
            return "unknown"
        if self.kappa_interface >= 0.7:
            return "healthy"
        elif self.kappa_interface >= 0.4:
            return "degraded"
        else:
            return "critical"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "channel_type": self.channel_type,
            "modality": self.modality.value,
            "kappa_interface": self.kappa_interface,
            "health_status": self.health_status,
            "latency_ms": self.latency_ms,
        }


@dataclass
class Swarm:
    """
    Multi-agent swarm topology.

    A swarm consists of:
    - Agents with individual health scores
    - Channels connecting agents
    - Aggregate metrics (consensus, weakest link)
    """

    id: str
    name: str
    agents: List[Agent] = field(default_factory=list)
    channels: List[Channel] = field(default_factory=list)

    # Metadata
    description: str = ""
    config: Dict[str, Any] = field(default_factory=dict)

    @property
    def agent_count(self) -> int:
        return len(self.agents)

    @property
    def channel_count(self) -> int:
        return len(self.channels)

    @property
    def consensus(self) -> float:
        """
        Phasor coherence across swarm.

        High consensus = agents agree (kappas similar)
        Low consensus = agents disagree (kappas divergent)
        """
        if not self.agents:
            return 0.0

        kappas = [a.kappa_gate for a in self.agents]
        if len(kappas) < 2:
            return 1.0

        mean_k = sum(kappas) / len(kappas)
        variance = sum((k - mean_k) ** 2 for k in kappas) / len(kappas)

        # Consensus = 1 - normalized variance
        return max(0.0, 1.0 - variance * 4)  # Scale variance

    @property
    def kappa_gate_min(self) -> float:
        """Minimum kappa_gate across all agents (weakest agent)."""
        if not self.agents:
            return 0.0
        return min(a.kappa_gate for a in self.agents)

    @property
    def kappa_interface_min(self) -> Optional[float]:
        """Minimum kappa_interface across all channels (weakest link)."""
        interfaces = [c.kappa_interface for c in self.channels if c.kappa_interface is not None]
        if not interfaces:
            return None
        return min(interfaces)

    @property
    def weakest_agent(self) -> Optional[Agent]:
        """Agent with lowest kappa_gate."""
        if not self.agents:
            return None
        return min(self.agents, key=lambda a: a.kappa_gate)

    @property
    def weakest_channel(self) -> Optional[Channel]:
        """Channel with lowest kappa_interface."""
        valid = [c for c in self.channels if c.kappa_interface is not None]
        if not valid:
            return None
        return min(valid, key=lambda c: c.kappa_interface)

    @property
    def health_status(self) -> str:
        """Overall swarm health."""
        if self.kappa_gate_min >= 0.7 and (self.kappa_interface_min is None or self.kappa_interface_min >= 0.7):
            return "healthy"
        elif self.kappa_gate_min >= 0.4:
            return "degraded"
        else:
            return "critical"

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_channels_from(self, agent_id: str) -> List[Channel]:
        """Get all channels originating from an agent."""
        return [c for c in self.channels if c.source_id == agent_id]

    def get_channels_to(self, agent_id: str) -> List[Channel]:
        """Get all channels targeting an agent."""
        return [c for c in self.channels if c.target_id == agent_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_count": self.agent_count,
            "channel_count": self.channel_count,
            "agents": [a.to_dict() for a in self.agents],
            "channels": [c.to_dict() for c in self.channels],
            "metrics": {
                "consensus": self.consensus,
                "kappa_gate_min": self.kappa_gate_min,
                "kappa_interface_min": self.kappa_interface_min,
                "health_status": self.health_status,
            },
            "weakest_agent_id": self.weakest_agent.id if self.weakest_agent else None,
            "weakest_channel": (
                f"{self.weakest_channel.source_id}->{self.weakest_channel.target_id}"
                if self.weakest_channel else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Swarm":
        """Create swarm from dict."""
        agents = [
            Agent(
                id=a["id"],
                name=a["name"],
                role=a["role"],
                solver_type=SolverType(a.get("solver_type", "transformer")),
                modality=Modality(a.get("modality", "text")),
                kappa_H=a.get("kappa_modal", {}).get("H"),
                kappa_L=a.get("kappa_modal", {}).get("L"),
                kappa_interface=a.get("kappa_modal", {}).get("interface"),
                model=a.get("model"),
            )
            for a in data.get("agents", [])
        ]

        channels = [
            Channel(
                source_id=c["source_id"],
                target_id=c["target_id"],
                channel_type=c["channel_type"],
                modality=Modality(c.get("modality", "text")),
                kappa_interface=c.get("kappa_interface"),
                latency_ms=c.get("latency_ms"),
            )
            for c in data.get("channels", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            agents=agents,
            channels=channels,
            config=data.get("config", {}),
        )
