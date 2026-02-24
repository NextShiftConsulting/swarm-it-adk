"""
Swarm-It Python Client - Thin client for the sidecar.

Usage:
    from swarm_it import SwarmIt

    swarm = SwarmIt(url="http://localhost:8080")
    cert = swarm.certify("What is the capital of France?")

    if cert.allowed:
        response = my_llm(prompt)
        swarm.validate(cert.id, "TYPE_I", score=0.9)
"""

from .client import SwarmIt, Certificate, GateDecision, ValidationType

__version__ = "0.1.0"
__all__ = ["SwarmIt", "Certificate", "GateDecision", "ValidationType"]
