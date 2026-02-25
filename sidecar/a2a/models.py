"""
A2A Data Models - Agent topology and swarm structures.

Based on RSCT theory:
- Each agent has individual RSN certification
- Agent links have kappa_interface (compatibility score)
- Swarm kappa = min(kappa_interface) across all links
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class AgentRole(Enum):
    """Standard agent roles in a swarm."""
    COORDINATOR = "coordinator"  # Orchestrates other agents
    WORKER = "worker"            # Executes tasks
    VALIDATOR = "validator"      # Validates outputs
    ROUTER = "router"            # Routes messages
    SPECIALIST = "specialist"    # Domain-specific agent


@dataclass
class Agent:
    """
    An agent in a multi-agent swarm.

    Each agent has:
    - Identity (id, name, role)
    - Model configuration (model, provider)
    - Individual RSN baseline from its outputs
    """
    id: str
    name: str
    role: AgentRole = AgentRole.WORKER
    model: str = "claude-3-sonnet"
    provider: str = "bedrock"

    # RSN baseline for this agent's outputs
    baseline_R: float = 0.5
    baseline_S: float = 0.3
    baseline_N: float = 0.2

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def baseline_kappa(self) -> float:
        """Agent's baseline quality score."""
        if self.baseline_R + self.baseline_N == 0:
            return 0.5
        return self.baseline_R / (self.baseline_R + self.baseline_N)


@dataclass
class AgentLink:
    """
    A communication link between two agents.

    kappa_interface measures compatibility:
    - How well source's outputs match target's expected inputs
    - Computed from RSN of messages passing through link
    """
    source: Agent
    target: Agent

    # Interface compatibility (computed from message certifications)
    kappa_interface: float = 0.5
    message_count: int = 0

    # Running stats
    total_R: float = 0.0
    total_S: float = 0.0
    total_N: float = 0.0

    def update(self, R: float, S: float, N: float):
        """Update link stats with new message RSN."""
        self.message_count += 1
        self.total_R += R
        self.total_S += S
        self.total_N += N

        # Recompute kappa_interface as average kappa
        avg_R = self.total_R / self.message_count
        avg_N = self.total_N / self.message_count
        if avg_R + avg_N > 0:
            self.kappa_interface = avg_R / (avg_R + avg_N)
        else:
            self.kappa_interface = 0.5

    @property
    def link_id(self) -> str:
        return f"{self.source.id}->{self.target.id}"


@dataclass
class Message:
    """
    A message between agents.

    Each message is certified with RSN before delivery.
    """
    id: str
    source_id: str
    target_id: str
    content: str

    # Certification results (filled after certify())
    R: Optional[float] = None
    S: Optional[float] = None
    N: Optional[float] = None
    kappa: Optional[float] = None
    decision: Optional[str] = None
    allowed: bool = False

    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Swarm:
    """
    A multi-agent swarm with topology.

    Swarm-level metrics:
    - kappa_swarm = min(kappa_interface) across all links
    - weakest_link identifies bottleneck
    """
    id: str
    name: str
    agents: List[Agent] = field(default_factory=list)
    links: List[AgentLink] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_agent(self, agent: Agent):
        """Add agent to swarm."""
        self.agents.append(agent)

    def add_link(self, source_id: str, target_id: str) -> AgentLink:
        """Create link between agents."""
        source = self.get_agent(source_id)
        target = self.get_agent(target_id)
        if not source or not target:
            raise ValueError(f"Agent not found: {source_id} or {target_id}")

        link = AgentLink(source=source, target=target)
        self.links.append(link)
        return link

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_link(self, source_id: str, target_id: str) -> Optional[AgentLink]:
        """Get link between agents."""
        for link in self.links:
            if link.source.id == source_id and link.target.id == target_id:
                return link
        return None

    @property
    def kappa_swarm(self) -> float:
        """Swarm-level kappa = min across all links."""
        if not self.links:
            return 0.5
        return min(link.kappa_interface for link in self.links)

    @property
    def weakest_link(self) -> Optional[AgentLink]:
        """Link with lowest kappa_interface."""
        if not self.links:
            return None
        return min(self.links, key=lambda l: l.kappa_interface)


@dataclass
class SwarmCertificate:
    """
    Swarm-level certificate aggregating all agent interactions.
    """
    swarm_id: str
    timestamp: datetime

    # Swarm-level metrics
    kappa_swarm: float
    total_messages: int
    blocked_messages: int

    # Per-link breakdown
    link_kappas: Dict[str, float] = field(default_factory=dict)
    weakest_link_id: Optional[str] = None

    # Per-agent breakdown
    agent_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Decision
    swarm_healthy: bool = True
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "swarm_id": self.swarm_id,
            "timestamp": self.timestamp.isoformat(),
            "kappa_swarm": round(self.kappa_swarm, 4),
            "total_messages": self.total_messages,
            "blocked_messages": self.blocked_messages,
            "link_kappas": {k: round(v, 4) for k, v in self.link_kappas.items()},
            "weakest_link_id": self.weakest_link_id,
            "agent_stats": self.agent_stats,
            "swarm_healthy": self.swarm_healthy,
            "issues": self.issues,
        }
