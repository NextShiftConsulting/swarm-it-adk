"""
Swarm Topology Models

Defines multi-agent swarm structures for certification.
"""

from .models import (
    SolverType,
    Agent,
    Channel,
    Swarm,
)

from .certifier import (
    SwarmCertifier,
    SwarmCertificate,
    certify_swarm,
)

from .patterns import (
    SwarmPattern,
    create_pipeline_swarm,
    create_hub_spoke_swarm,
    create_mesh_swarm,
)

__all__ = [
    # Models
    "SolverType",
    "Agent",
    "Channel",
    "Swarm",
    # Certifier
    "SwarmCertifier",
    "SwarmCertificate",
    "certify_swarm",
    # Patterns
    "SwarmPattern",
    "create_pipeline_swarm",
    "create_hub_spoke_swarm",
    "create_mesh_swarm",
]
