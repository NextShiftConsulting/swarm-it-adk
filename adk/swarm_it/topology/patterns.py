"""
Common Swarm Patterns

Provides factory functions for creating standard swarm topologies.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

from .models import Swarm, Agent, Channel, SolverType, Modality


class SwarmPattern(Enum):
    """Standard swarm topology patterns."""

    PIPELINE = "pipeline"  # Linear chain: A → B → C → D
    HUB_SPOKE = "hub_spoke"  # Central coordinator: A ↔ {B, C, D}
    MESH = "mesh"  # Fully connected: All ↔ All
    HIERARCHICAL = "hierarchical"  # Tree structure
    RING = "ring"  # Circular: A → B → C → A


def create_pipeline_swarm(
    name: str,
    roles: List[str],
    solver_types: Optional[List[SolverType]] = None,
    modalities: Optional[List[Modality]] = None,
    default_kappa: float = 0.7,
) -> Swarm:
    """
    Create a linear pipeline swarm: A → B → C → ...

    Each agent passes output to the next in sequence.

    Args:
        name: Swarm name
        roles: List of role names (determines agent count)
        solver_types: Optional solver types per agent
        modalities: Optional modalities per agent
        default_kappa: Default kappa for agents

    Returns:
        Swarm with pipeline topology
    """
    agents = []
    channels = []

    n = len(roles)
    solver_types = solver_types or [SolverType.TRANSFORMER] * n
    modalities = modalities or [Modality.TEXT] * n

    for i, role in enumerate(roles):
        agent = Agent(
            id=f"agent-{i}",
            name=f"{role.replace('_', ' ').title()}",
            role=role,
            solver_type=solver_types[i] if i < len(solver_types) else SolverType.TRANSFORMER,
            modality=modalities[i] if i < len(modalities) else Modality.TEXT,
            kappa_H=default_kappa,
            kappa_L=default_kappa * 0.9,
            kappa_interface=default_kappa * 0.95,
        )
        agents.append(agent)

        # Create channel to next agent
        if i < n - 1:
            channels.append(Channel(
                source_id=f"agent-{i}",
                target_id=f"agent-{i+1}",
                channel_type="delegation",
                modality=modalities[i] if i < len(modalities) else Modality.TEXT,
                kappa_interface=default_kappa * 0.95,
            ))

    return Swarm(
        id=f"swarm-pipeline-{uuid.uuid4().hex[:8]}",
        name=name,
        description=f"Pipeline swarm: {' → '.join(roles)}",
        agents=agents,
        channels=channels,
        config={"pattern": SwarmPattern.PIPELINE.value},
    )


def create_hub_spoke_swarm(
    name: str,
    hub_role: str,
    spoke_roles: List[str],
    hub_solver: SolverType = SolverType.TRANSFORMER,
    spoke_solver: SolverType = SolverType.TRANSFORMER,
    default_kappa: float = 0.7,
) -> Swarm:
    """
    Create a hub-and-spoke swarm: Hub ↔ {Spoke1, Spoke2, ...}

    Central coordinator delegates to and aggregates from spokes.

    Args:
        name: Swarm name
        hub_role: Role of the central hub agent
        spoke_roles: Roles of spoke agents
        hub_solver: Solver type for hub
        spoke_solver: Solver type for spokes
        default_kappa: Default kappa for agents

    Returns:
        Swarm with hub-spoke topology
    """
    agents = []
    channels = []

    # Create hub
    hub = Agent(
        id="agent-hub",
        name=f"{hub_role.replace('_', ' ').title()} (Hub)",
        role=hub_role,
        solver_type=hub_solver,
        modality=Modality.TEXT,
        kappa_H=default_kappa,
        kappa_L=default_kappa * 0.9,
        kappa_interface=default_kappa * 0.95,
    )
    agents.append(hub)

    # Create spokes
    for i, role in enumerate(spoke_roles):
        spoke = Agent(
            id=f"agent-spoke-{i}",
            name=f"{role.replace('_', ' ').title()}",
            role=role,
            solver_type=spoke_solver,
            modality=Modality.TEXT,
            kappa_H=default_kappa,
            kappa_L=default_kappa * 0.9,
            kappa_interface=default_kappa * 0.95,
        )
        agents.append(spoke)

        # Bidirectional channels between hub and spoke
        channels.append(Channel(
            source_id="agent-hub",
            target_id=f"agent-spoke-{i}",
            channel_type="delegation",
            kappa_interface=default_kappa * 0.95,
        ))
        channels.append(Channel(
            source_id=f"agent-spoke-{i}",
            target_id="agent-hub",
            channel_type="message",
            kappa_interface=default_kappa * 0.95,
        ))

    return Swarm(
        id=f"swarm-hub-{uuid.uuid4().hex[:8]}",
        name=name,
        description=f"Hub-spoke swarm: {hub_role} ↔ {{{', '.join(spoke_roles)}}}",
        agents=agents,
        channels=channels,
        config={"pattern": SwarmPattern.HUB_SPOKE.value},
    )


def create_mesh_swarm(
    name: str,
    roles: List[str],
    solver_types: Optional[List[SolverType]] = None,
    default_kappa: float = 0.7,
) -> Swarm:
    """
    Create a fully-connected mesh swarm: All ↔ All

    Every agent can communicate with every other agent.

    Args:
        name: Swarm name
        roles: List of role names
        solver_types: Optional solver types per agent
        default_kappa: Default kappa for agents

    Returns:
        Swarm with mesh topology
    """
    agents = []
    channels = []

    n = len(roles)
    solver_types = solver_types or [SolverType.TRANSFORMER] * n

    # Create agents
    for i, role in enumerate(roles):
        agent = Agent(
            id=f"agent-{i}",
            name=f"{role.replace('_', ' ').title()}",
            role=role,
            solver_type=solver_types[i] if i < len(solver_types) else SolverType.TRANSFORMER,
            modality=Modality.TEXT,
            kappa_H=default_kappa,
            kappa_L=default_kappa * 0.9,
            kappa_interface=default_kappa * 0.95,
        )
        agents.append(agent)

    # Create full mesh of channels
    for i in range(n):
        for j in range(n):
            if i != j:
                channels.append(Channel(
                    source_id=f"agent-{i}",
                    target_id=f"agent-{j}",
                    channel_type="message",
                    kappa_interface=default_kappa * 0.95,
                ))

    return Swarm(
        id=f"swarm-mesh-{uuid.uuid4().hex[:8]}",
        name=name,
        description=f"Mesh swarm: {{{', '.join(roles)}}}",
        agents=agents,
        channels=channels,
        config={"pattern": SwarmPattern.MESH.value},
    )


def create_hierarchical_swarm(
    name: str,
    structure: Dict[str, Any],
    default_kappa: float = 0.7,
) -> Swarm:
    """
    Create a hierarchical tree swarm.

    Structure is a nested dict where keys are roles and values are
    either None (leaf) or another dict (subtree).

    Example:
        {
            "ceo": {
                "vp_engineering": {
                    "lead_backend": None,
                    "lead_frontend": None,
                },
                "vp_product": {
                    "pm_core": None,
                    "pm_growth": None,
                }
            }
        }

    Args:
        name: Swarm name
        structure: Nested dict defining hierarchy
        default_kappa: Default kappa for agents

    Returns:
        Swarm with hierarchical topology
    """
    agents = []
    channels = []
    agent_counter = [0]  # Mutable counter

    def _process_node(role: str, children: Optional[Dict], parent_id: Optional[str]):
        agent_id = f"agent-{agent_counter[0]}"
        agent_counter[0] += 1

        agent = Agent(
            id=agent_id,
            name=f"{role.replace('_', ' ').title()}",
            role=role,
            solver_type=SolverType.TRANSFORMER,
            modality=Modality.TEXT,
            kappa_H=default_kappa,
            kappa_L=default_kappa * 0.9,
            kappa_interface=default_kappa * 0.95,
        )
        agents.append(agent)

        # Create channel from parent
        if parent_id:
            channels.append(Channel(
                source_id=parent_id,
                target_id=agent_id,
                channel_type="delegation",
                kappa_interface=default_kappa * 0.95,
            ))
            channels.append(Channel(
                source_id=agent_id,
                target_id=parent_id,
                channel_type="message",
                kappa_interface=default_kappa * 0.95,
            ))

        # Process children
        if children:
            for child_role, grandchildren in children.items():
                _process_node(child_role, grandchildren, agent_id)

    # Process root nodes
    for root_role, children in structure.items():
        _process_node(root_role, children, None)

    return Swarm(
        id=f"swarm-hier-{uuid.uuid4().hex[:8]}",
        name=name,
        description=f"Hierarchical swarm with {len(agents)} agents",
        agents=agents,
        channels=channels,
        config={"pattern": SwarmPattern.HIERARCHICAL.value},
    )


def create_ring_swarm(
    name: str,
    roles: List[str],
    default_kappa: float = 0.7,
) -> Swarm:
    """
    Create a ring swarm: A → B → C → A

    Circular topology where each agent passes to the next,
    and the last passes back to the first.

    Args:
        name: Swarm name
        roles: List of role names
        default_kappa: Default kappa for agents

    Returns:
        Swarm with ring topology
    """
    agents = []
    channels = []

    n = len(roles)

    for i, role in enumerate(roles):
        agent = Agent(
            id=f"agent-{i}",
            name=f"{role.replace('_', ' ').title()}",
            role=role,
            solver_type=SolverType.TRANSFORMER,
            modality=Modality.TEXT,
            kappa_H=default_kappa,
            kappa_L=default_kappa * 0.9,
            kappa_interface=default_kappa * 0.95,
        )
        agents.append(agent)

        # Create channel to next agent (wrapping around)
        next_idx = (i + 1) % n
        channels.append(Channel(
            source_id=f"agent-{i}",
            target_id=f"agent-{next_idx}",
            channel_type="message",
            kappa_interface=default_kappa * 0.95,
        ))

    return Swarm(
        id=f"swarm-ring-{uuid.uuid4().hex[:8]}",
        name=name,
        description=f"Ring swarm: {' → '.join(roles)} → {roles[0]}",
        agents=agents,
        channels=channels,
        config={"pattern": SwarmPattern.RING.value},
    )
