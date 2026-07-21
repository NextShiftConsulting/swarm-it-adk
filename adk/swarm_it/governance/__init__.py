"""Governance module — MAS coordination-governance evidence contracts.

Sits beside topology/: topology certifies swarm structure, governance
carries per-handoff evidence (HandoffEnvelope) between agents without
self-authorizing any gate decision.
"""

from swarm_it.governance.envelope import HandoffEnvelope

__all__ = ["HandoffEnvelope"]
