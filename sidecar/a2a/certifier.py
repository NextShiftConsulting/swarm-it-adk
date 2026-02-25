"""
SwarmCertifier - Certifies agent-to-agent communications.

Uses RSCTEngine for individual message certification,
aggregates to swarm-level metrics.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from .models import (
    Agent, AgentLink, Swarm, Message, SwarmCertificate, AgentRole
)


class SwarmCertifier:
    """
    Certifies messages in a multi-agent swarm.

    Usage:
        from sidecar.a2a import SwarmCertifier, Agent, AgentRole

        certifier = SwarmCertifier()

        # Define agents
        coordinator = Agent(id="coord", name="Coordinator", role=AgentRole.COORDINATOR)
        worker = Agent(id="worker1", name="Worker 1", role=AgentRole.WORKER)

        # Create swarm
        swarm = certifier.create_swarm("my-swarm", [coordinator, worker])
        certifier.add_link(swarm, "coord", "worker1")

        # Certify message
        msg = certifier.certify_message(
            swarm,
            source_id="coord",
            target_id="worker1",
            content="Analyze this data..."
        )

        # Check swarm health
        cert = certifier.get_swarm_certificate(swarm)
        print(f"Swarm kappa: {cert.kappa_swarm}")
    """

    # Thresholds
    KAPPA_HEALTHY = 0.6      # Swarm considered healthy above this
    KAPPA_WARNING = 0.4      # Warning threshold
    BLOCK_THRESHOLD = 0.3    # Block messages below this

    def __init__(self, engine=None):
        """
        Initialize with RSCTEngine.

        Args:
            engine: RSCTEngine instance (auto-created if None)
        """
        if engine is None:
            from ..bootstrap import create_engine
            engine = create_engine()
        self.engine = engine
        self._swarms: Dict[str, Swarm] = {}

    def create_swarm(
        self,
        name: str,
        agents: List[Agent],
        swarm_id: Optional[str] = None,
    ) -> Swarm:
        """Create a new swarm with agents."""
        swarm_id = swarm_id or str(uuid.uuid4())[:8]
        swarm = Swarm(id=swarm_id, name=name, agents=agents)
        self._swarms[swarm_id] = swarm
        return swarm

    def add_link(self, swarm: Swarm, source_id: str, target_id: str) -> AgentLink:
        """Add communication link between agents."""
        return swarm.add_link(source_id, target_id)

    def certify_message(
        self,
        swarm: Swarm,
        source_id: str,
        target_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Certify a message between agents.

        Returns:
            Message with RSN certification filled in
        """
        # Create message
        msg = Message(
            id=str(uuid.uuid4())[:8],
            source_id=source_id,
            target_id=target_id,
            content=content,
            metadata=metadata or {},
        )

        # Certify content using RSCTEngine
        cert = self.engine.certify(content)

        # Fill certification results
        msg.R = cert["R"]
        msg.S = cert["S"]
        msg.N = cert["N"]
        msg.kappa = cert.get("kappa", cert.get("kappa_gate", 0))
        msg.decision = cert["decision"]
        msg.allowed = cert["allowed"]

        # Update link stats
        link = swarm.get_link(source_id, target_id)
        if link:
            link.update(msg.R, msg.S, msg.N)

        return msg

    def certify_batch(
        self,
        swarm: Swarm,
        messages: List[Dict[str, str]],
    ) -> List[Message]:
        """
        Certify multiple messages.

        Args:
            swarm: Target swarm
            messages: List of {source_id, target_id, content}
        """
        results = []
        for m in messages:
            msg = self.certify_message(
                swarm,
                source_id=m["source_id"],
                target_id=m["target_id"],
                content=m["content"],
            )
            results.append(msg)
        return results

    def get_swarm_certificate(self, swarm: Swarm) -> SwarmCertificate:
        """
        Generate swarm-level certificate.

        Aggregates all link metrics into swarm health assessment.
        """
        # Collect link kappas
        link_kappas = {}
        total_messages = 0
        blocked_messages = 0

        for link in swarm.links:
            link_kappas[link.link_id] = link.kappa_interface
            total_messages += link.message_count
            # Estimate blocked (would need to track this properly)

        # Find weakest link
        weakest = swarm.weakest_link
        weakest_id = weakest.link_id if weakest else None

        # Agent stats
        agent_stats = {}
        for agent in swarm.agents:
            agent_stats[agent.id] = {
                "name": agent.name,
                "role": agent.role.value,
                "baseline_kappa": round(agent.baseline_kappa, 4),
            }

        # Assess health
        kappa_swarm = swarm.kappa_swarm
        issues = []

        if kappa_swarm < self.BLOCK_THRESHOLD:
            issues.append(f"Critical: kappa_swarm={kappa_swarm:.2f} below block threshold")
        elif kappa_swarm < self.KAPPA_WARNING:
            issues.append(f"Warning: kappa_swarm={kappa_swarm:.2f} below warning threshold")

        if weakest and weakest.kappa_interface < self.KAPPA_WARNING:
            issues.append(f"Weak link: {weakest_id} has kappa={weakest.kappa_interface:.2f}")

        return SwarmCertificate(
            swarm_id=swarm.id,
            timestamp=datetime.utcnow(),
            kappa_swarm=kappa_swarm,
            total_messages=total_messages,
            blocked_messages=blocked_messages,
            link_kappas=link_kappas,
            weakest_link_id=weakest_id,
            agent_stats=agent_stats,
            swarm_healthy=kappa_swarm >= self.KAPPA_HEALTHY,
            issues=issues,
        )

    def should_block_message(self, msg: Message) -> bool:
        """Check if message should be blocked based on certification."""
        if not msg.allowed:
            return True
        if msg.kappa and msg.kappa < self.BLOCK_THRESHOLD:
            return True
        return False

    def get_swarm(self, swarm_id: str) -> Optional[Swarm]:
        """Get swarm by ID."""
        return self._swarms.get(swarm_id)
