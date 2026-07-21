"""Governance module — MAS coordination-governance evidence contracts.

Sits beside topology/: topology certifies swarm structure, governance
carries per-handoff evidence (HandoffEnvelope) between agents without
self-authorizing any gate decision.
"""

from swarm_it.governance.chain_kappa import ChainKappaState, ChainKappaTracker
from swarm_it.governance.cycle_guard import CycleGuard
from swarm_it.governance.envelope import HandoffEnvelope
from swarm_it.governance.output_boundary import OutputVerdict, recertify_on_output
from swarm_it.governance.p10 import P10Budget, P10Decision, P10State, decide
from swarm_it.governance.receive_boundary import ReceiveVerdict, validate_on_receive
from swarm_it.governance.topology_policy import (
    HopInput,
    TopologyDecision,
    UnsupportedTopologyError,
    accept,
    accept_hub_spoke,
    accept_mesh,
    accept_pipeline,
)
from swarm_it.governance.trace import TraceRecord, emit, get_trace, reset_trace

__all__ = [
    "HandoffEnvelope",
    "TraceRecord",
    "emit",
    "get_trace",
    "reset_trace",
    "CycleGuard",
    "validate_on_receive",
    "ReceiveVerdict",
    "ChainKappaTracker",
    "ChainKappaState",
    "recertify_on_output",
    "OutputVerdict",
    "TopologyDecision",
    "HopInput",
    "UnsupportedTopologyError",
    "accept",
    "accept_pipeline",
    "accept_hub_spoke",
    "accept_mesh",
    "P10Budget",
    "P10State",
    "P10Decision",
    "decide",
]
