"""
A2A (Agent-to-Agent) - Multi-agent swarm certification.

This module provides:
- Agent/Swarm topology models
- Cross-agent message certification
- Swarm-level kappa aggregation
- AWS Bedrock integration for agent orchestration
"""

from .models import Agent, AgentLink, Swarm, Message, SwarmCertificate, AgentRole
from .certifier import SwarmCertifier

__all__ = [
    "Agent",
    "AgentLink",
    "AgentRole",
    "Swarm",
    "Message",
    "SwarmCertificate",
    "SwarmCertifier",
]
