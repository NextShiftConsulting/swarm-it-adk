"""
Swarm It - Execution Governance for AI Systems

Simple SDK for RSCT-certified AI execution gating.

Usage:
    from swarm_it import SwarmIt

    swarm = SwarmIt(api_key="your-key")

    # Simple check
    cert = swarm.certify("What is the capital of France?")
    if cert.allowed:
        response = my_llm(prompt)

    # Or use decorator
    @swarm.gate
    def ask(prompt):
        return openai.chat.completions.create(...)
"""

from .client import SwarmIt, Certificate, GateDecision
from .decorators import gate, certified
from .exceptions import (
    SwarmItError,
    CertificationError,
    GateBlockedError,
    AuthenticationError,
)

__version__ = "0.1.0"
__all__ = [
    "SwarmIt",
    "Certificate",
    "GateDecision",
    "gate",
    "certified",
    "SwarmItError",
    "CertificationError",
    "GateBlockedError",
    "AuthenticationError",
]
