"""
Swarm Certifier

Certifies entire swarm topologies, producing aggregate certificates
with per-agent breakdowns.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

from .models import Swarm, Agent, Channel
from ..local.engine import RSCTCertificate, GateDecision


@dataclass
class SwarmCertificate:
    """
    Certificate for an entire swarm execution.

    Contains:
    - Aggregate RSN across all agents
    - Per-agent certificate breakdown
    - Swarm-level metrics (consensus, weakest link)
    - Gate decision for the swarm as a whole
    """

    id: str
    timestamp: str
    swarm_id: str

    # Aggregate RSN (averaged across agents)
    R: float
    S: float
    N: float

    # Swarm-level metrics
    consensus: float  # Phasor coherence
    kappa_gate_min: float  # Weakest agent
    kappa_interface_min: Optional[float]  # Weakest channel
    sigma_max: float  # Most turbulent agent

    # Gate result
    decision: GateDecision
    gate_reached: int
    reason: str

    # Per-agent breakdown
    agent_certificates: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Topology snapshot
    topology_hash: str = ""

    # Metadata
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision.allowed

    @property
    def margin(self) -> float:
        """Safety margin for swarm."""
        return min(
            self.R,
            self.kappa_gate_min,
            self.consensus,
            1.0 - self.N,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.id,
            "timestamp": self.timestamp,
            "swarm_id": self.swarm_id,
            "aggregate": {
                "R": self.R,
                "S": self.S,
                "N": self.N,
            },
            "metrics": {
                "consensus": self.consensus,
                "kappa_gate_min": self.kappa_gate_min,
                "kappa_interface_min": self.kappa_interface_min,
                "sigma_max": self.sigma_max,
            },
            "gate": {
                "decision": self.decision.value,
                "gate_reached": self.gate_reached,
                "reason": self.reason,
            },
            "allowed": self.allowed,
            "margin": self.margin,
            "agent_count": len(self.agent_certificates),
            "agent_certificates": self.agent_certificates,
            "topology_hash": self.topology_hash,
        }


class SwarmCertifier:
    """
    Certifies swarm topologies.

    Combines individual agent certifications into a swarm-level
    certificate with aggregate metrics and weakest-link analysis.
    """

    def __init__(
        self,
        consensus_threshold: float = 0.4,
        kappa_min_threshold: float = 0.3,
        interface_threshold: float = 0.3,
    ):
        """
        Initialize certifier.

        Args:
            consensus_threshold: Minimum consensus for EXECUTE
            kappa_min_threshold: Minimum agent kappa for EXECUTE
            interface_threshold: Minimum channel kappa for EXECUTE
        """
        self.consensus_threshold = consensus_threshold
        self.kappa_min_threshold = kappa_min_threshold
        self.interface_threshold = interface_threshold

    def certify(
        self,
        swarm: Swarm,
        task: Optional[str] = None,
        agent_certificates: Optional[Dict[str, RSCTCertificate]] = None,
    ) -> SwarmCertificate:
        """
        Certify a swarm for task execution.

        Args:
            swarm: Swarm topology to certify
            task: Optional task description (for context)
            agent_certificates: Optional pre-computed agent certificates

        Returns:
            SwarmCertificate with aggregate metrics
        """
        # Use provided certificates or generate from agent kappas
        if agent_certificates is None:
            agent_certificates = self._generate_agent_certificates(swarm)

        # Compute aggregate RSN
        R_sum, S_sum, N_sum = 0.0, 0.0, 0.0
        sigma_max = 0.0

        for cert in agent_certificates.values():
            R_sum += cert.R
            S_sum += cert.S
            N_sum += cert.N
            sigma_max = max(sigma_max, cert.sigma)

        n_agents = len(agent_certificates) or 1
        R = R_sum / n_agents
        S = S_sum / n_agents
        N = N_sum / n_agents

        # Get swarm metrics
        consensus = swarm.consensus
        kappa_min = swarm.kappa_gate_min
        interface_min = swarm.kappa_interface_min

        # Determine gate decision
        decision, gate, reason = self._compute_gate_decision(
            swarm, consensus, kappa_min, interface_min, N, sigma_max
        )

        # Create certificate
        return SwarmCertificate(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            swarm_id=swarm.id,
            R=R,
            S=S,
            N=N,
            consensus=consensus,
            kappa_gate_min=kappa_min,
            kappa_interface_min=interface_min,
            sigma_max=sigma_max,
            decision=decision,
            gate_reached=gate,
            reason=reason,
            agent_certificates={
                agent_id: cert.to_dict()
                for agent_id, cert in agent_certificates.items()
            },
            topology_hash=self._compute_topology_hash(swarm),
        )

    def _generate_agent_certificates(self, swarm: Swarm) -> Dict[str, RSCTCertificate]:
        """Generate certificates from agent kappa values."""
        certs = {}

        for agent in swarm.agents:
            # Create certificate from agent health
            kappa = agent.kappa_gate
            R = 0.6 + 0.3 * kappa  # Estimate R from kappa
            N = 0.1 + 0.2 * (1 - kappa)  # Estimate N inverse to kappa
            S = 1.0 - R - N

            certs[agent.id] = RSCTCertificate(
                id=f"agent-{agent.id}-{uuid.uuid4().hex[:8]}",
                timestamp=datetime.utcnow().isoformat() + "Z",
                R=max(0, min(1, R)),
                S=max(0, min(1, S)),
                N=max(0, min(1, N)),
                kappa_gate=kappa,
                sigma=0.3,  # Default
                kappa_H=agent.kappa_H,
                kappa_L=agent.kappa_L,
                kappa_interface=agent.kappa_interface,
                decision=GateDecision.EXECUTE if kappa >= 0.4 else GateDecision.BLOCK,
                gate_reached=5 if kappa >= 0.4 else 3,
                reason=f"Agent {agent.name}: kappa={kappa:.3f}",
            )

        return certs

    def _compute_gate_decision(
        self,
        swarm: Swarm,
        consensus: float,
        kappa_min: float,
        interface_min: Optional[float],
        N: float,
        sigma_max: float,
    ) -> tuple:
        """Compute swarm-level gate decision."""

        # Check noise (Gate 1)
        if N >= 0.5:
            return GateDecision.REJECT, 1, f"Swarm noise too high: N={N:.3f}"

        # Check consensus (Gate 2)
        if consensus < self.consensus_threshold:
            return GateDecision.BLOCK, 2, f"Low consensus: c={consensus:.3f}"

        # Check weakest agent (Gate 3)
        if kappa_min < self.kappa_min_threshold:
            weakest = swarm.weakest_agent
            return GateDecision.REPAIR, 3, f"Weakest agent {weakest.name if weakest else 'unknown'}: kappa={kappa_min:.3f}"

        # Check weakest channel (Gate 4)
        if interface_min is not None and interface_min < self.interface_threshold:
            weakest = swarm.weakest_channel
            return GateDecision.REPAIR, 4, f"Weakest channel: kappa_interface={interface_min:.3f}"

        # Check turbulence
        if sigma_max > 0.7:
            return GateDecision.BLOCK, 2, f"High turbulence: sigma_max={sigma_max:.3f}"

        return GateDecision.EXECUTE, 5, "Swarm certified for execution"

    def _compute_topology_hash(self, swarm: Swarm) -> str:
        """Compute hash of swarm topology for change detection."""
        import hashlib

        parts = [swarm.id, swarm.name]
        parts.extend(sorted(a.id for a in swarm.agents))
        parts.extend(sorted(f"{c.source_id}->{c.target_id}" for c in swarm.channels))

        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


def certify_swarm(
    swarm: Swarm,
    task: Optional[str] = None,
) -> SwarmCertificate:
    """
    Convenience function for one-shot swarm certification.

    Args:
        swarm: Swarm to certify
        task: Optional task description

    Returns:
        SwarmCertificate
    """
    certifier = SwarmCertifier()
    return certifier.certify(swarm, task)
