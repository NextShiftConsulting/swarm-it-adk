"""Tests for swarm topology models and certification."""

import pytest
from swarm_it.topology.models import (
    SolverType,
    Modality,
    Agent,
    Channel,
    Swarm,
)
from swarm_it.topology.certifier import (
    SwarmCertifier,
    certify_swarm,
)
from swarm_it.topology.patterns import (
    create_pipeline_swarm,
    create_hub_spoke_swarm,
    create_mesh_swarm,
    create_ring_swarm,
)


class TestSolverType:
    """Tests for SolverType enum."""

    def test_is_neural(self):
        assert SolverType.TRANSFORMER.is_neural is True
        assert SolverType.HYBRID.is_neural is True
        assert SolverType.SYMBOLIC.is_neural is False
        assert SolverType.TOOL.is_neural is False


class TestAgent:
    """Tests for Agent model."""

    def test_basic_agent(self):
        agent = Agent(
            id="agent-1",
            name="Planner",
            role="planner",
        )
        assert agent.id == "agent-1"
        assert agent.solver_type == SolverType.TRANSFORMER  # Default

    def test_kappa_gate_default(self):
        agent = Agent(id="a", name="A", role="r")
        assert agent.kappa_gate == 0.5  # Default when no per-modality

    def test_kappa_gate_multimodal(self):
        agent = Agent(
            id="a", name="A", role="r",
            kappa_H=0.8,
            kappa_L=0.6,
            kappa_interface=0.7,
        )
        assert agent.kappa_gate == 0.6  # min of all

    def test_is_multimodal(self):
        agent = Agent(
            id="a", name="A", role="r",
            kappa_H=0.8,
            kappa_L=0.6,
        )
        assert agent.is_multimodal is True

    def test_hierarchy_gap(self):
        agent = Agent(
            id="a", name="A", role="r",
            kappa_H=0.8,
            kappa_L=0.5,
        )
        assert agent.hierarchy_gap == 0.3

    def test_health_status(self):
        healthy = Agent(id="a", name="A", role="r", kappa_H=0.8, kappa_L=0.8)
        degraded = Agent(id="b", name="B", role="r", kappa_H=0.5, kappa_L=0.5)
        critical = Agent(id="c", name="C", role="r", kappa_H=0.3, kappa_L=0.3)

        assert healthy.health_status == "healthy"
        assert degraded.health_status == "degraded"
        assert critical.health_status == "critical"


class TestChannel:
    """Tests for Channel model."""

    def test_basic_channel(self):
        channel = Channel(
            source_id="agent-1",
            target_id="agent-2",
            channel_type="message",
        )
        assert channel.source_id == "agent-1"
        assert channel.modality == Modality.TEXT  # Default

    def test_health_status(self):
        healthy = Channel("a", "b", "msg", kappa_interface=0.8)
        degraded = Channel("a", "b", "msg", kappa_interface=0.5)
        critical = Channel("a", "b", "msg", kappa_interface=0.2)
        unknown = Channel("a", "b", "msg")

        assert healthy.health_status == "healthy"
        assert degraded.health_status == "degraded"
        assert critical.health_status == "critical"
        assert unknown.health_status == "unknown"


class TestSwarm:
    """Tests for Swarm model."""

    def test_empty_swarm(self):
        swarm = Swarm(id="s1", name="Empty")
        assert swarm.agent_count == 0
        assert swarm.consensus == 0.0

    def test_single_agent_swarm(self):
        swarm = Swarm(
            id="s1", name="Single",
            agents=[Agent(id="a1", name="A", role="r", kappa_H=0.8, kappa_L=0.8)],
        )
        assert swarm.agent_count == 1
        assert swarm.consensus == 1.0  # Single agent = full consensus

    def test_consensus_high(self):
        """Similar kappas = high consensus."""
        swarm = Swarm(
            id="s1", name="Consensus",
            agents=[
                Agent(id="a1", name="A", role="r", kappa_H=0.8, kappa_L=0.8),
                Agent(id="a2", name="B", role="r", kappa_H=0.75, kappa_L=0.75),
            ],
        )
        assert swarm.consensus > 0.9

    def test_consensus_low(self):
        """Divergent kappas = low consensus."""
        swarm = Swarm(
            id="s1", name="Divergent",
            agents=[
                Agent(id="a1", name="A", role="r", kappa_H=0.9, kappa_L=0.9),
                Agent(id="a2", name="B", role="r", kappa_H=0.3, kappa_L=0.3),
            ],
        )
        assert swarm.consensus < 0.7

    def test_weakest_agent(self):
        swarm = Swarm(
            id="s1", name="Test",
            agents=[
                Agent(id="a1", name="Strong", role="r", kappa_H=0.8, kappa_L=0.8),
                Agent(id="a2", name="Weak", role="r", kappa_H=0.3, kappa_L=0.3),
            ],
        )
        assert swarm.weakest_agent.id == "a2"
        assert swarm.kappa_gate_min == 0.3

    def test_weakest_channel(self):
        swarm = Swarm(
            id="s1", name="Test",
            agents=[
                Agent(id="a1", name="A", role="r"),
                Agent(id="a2", name="B", role="r"),
            ],
            channels=[
                Channel("a1", "a2", "msg", kappa_interface=0.8),
                Channel("a2", "a1", "msg", kappa_interface=0.4),
            ],
        )
        assert swarm.weakest_channel.kappa_interface == 0.4

    def test_to_dict_and_from_dict(self):
        swarm = Swarm(
            id="s1", name="Test",
            agents=[Agent(id="a1", name="A", role="r", kappa_H=0.7, kappa_L=0.7)],
            channels=[Channel("a1", "a1", "msg", kappa_interface=0.8)],
        )
        d = swarm.to_dict()
        restored = Swarm.from_dict(d)
        assert restored.id == swarm.id
        assert restored.agent_count == swarm.agent_count


class TestSwarmCertifier:
    """Tests for SwarmCertifier."""

    def test_certify_healthy_swarm(self):
        swarm = Swarm(
            id="s1", name="Healthy",
            agents=[
                Agent(id="a1", name="A", role="r", kappa_H=0.8, kappa_L=0.8),
                Agent(id="a2", name="B", role="r", kappa_H=0.7, kappa_L=0.7),
            ],
            channels=[Channel("a1", "a2", "delegation", kappa_interface=0.8)],
        )
        cert = certify_swarm(swarm)
        assert cert.allowed is True
        assert cert.decision.value == "EXECUTE"

    def test_certify_low_consensus_blocks(self):
        swarm = Swarm(
            id="s1", name="Divergent",
            agents=[
                Agent(id="a1", name="A", role="r", kappa_H=0.9, kappa_L=0.9),
                Agent(id="a2", name="B", role="r", kappa_H=0.2, kappa_L=0.2),
            ],
        )
        cert = certify_swarm(swarm)
        # May block due to low consensus or weakest agent
        assert cert.gate_reached <= 3


class TestSwarmPatterns:
    """Tests for swarm pattern factories."""

    def test_pipeline_swarm(self):
        swarm = create_pipeline_swarm(
            name="Test Pipeline",
            roles=["research", "draft", "review", "publish"],
        )
        assert swarm.agent_count == 4
        assert swarm.channel_count == 3  # Linear: 3 connections for 4 agents

    def test_hub_spoke_swarm(self):
        swarm = create_hub_spoke_swarm(
            name="Test Hub",
            hub_role="coordinator",
            spoke_roles=["worker1", "worker2", "worker3"],
        )
        assert swarm.agent_count == 4  # 1 hub + 3 spokes
        assert swarm.channel_count == 6  # Bidirectional to each spoke

    def test_mesh_swarm(self):
        swarm = create_mesh_swarm(
            name="Test Mesh",
            roles=["a", "b", "c"],
        )
        assert swarm.agent_count == 3
        assert swarm.channel_count == 6  # 3 * 2 = 6 directed edges

    def test_ring_swarm(self):
        swarm = create_ring_swarm(
            name="Test Ring",
            roles=["a", "b", "c", "d"],
        )
        assert swarm.agent_count == 4
        assert swarm.channel_count == 4  # Circular: same as agent count

    def test_pipeline_with_solver_types(self):
        swarm = create_pipeline_swarm(
            name="Mixed Pipeline",
            roles=["research", "code", "test"],
            solver_types=[SolverType.TRANSFORMER, SolverType.SYMBOLIC, SolverType.TOOL],
        )
        assert swarm.agents[0].solver_type == SolverType.TRANSFORMER
        assert swarm.agents[1].solver_type == SolverType.SYMBOLIC
        assert swarm.agents[2].solver_type == SolverType.TOOL
