"""HandoffEnvelope — the evidence contract carried across MAS handoffs.

A HandoffEnvelope is EVIDENCE, not AUTHORITY. It carries a reference to a
controlplane-issued certificate (input_certificate_ref) plus the provenance
needed to evaluate that reference — it never carries a gate outcome,
threshold, or authorization decision itself. Any component that receives
an envelope must resolve input_certificate_ref against the controlplane
(or another authoritative gate) before acting on it.

The envelope is immutable (frozen dataclass): once constructed by the
sender, it cannot be mutated by any hop along the chain.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class HandoffEnvelope:
    """Evidence contract passed between agents at a MAS handoff.

    Fields are either identity/routing metadata, artifact provenance, or
    prior-chain evidence carried forward for downstream evaluation. None
    of these fields represent a gate decision — decisions are made
    elsewhere, against input_certificate_ref, by the controlplane.
    """

    task_id: str
    handoff_id: str
    sender_id: str
    receiver_id: str
    input_certificate_ref: str
    artifact_hashes: tuple[str, ...]
    payload_hash: str
    representation_id: str
    environment_id: str
    prior_chain_kappa_min: Optional[float]
    prior_chain_dispersion: Optional[float]
    prior_hops: int
    requested_capability: str
    topology_pattern: str
    policy_version: str
    created_at: str
    replay_seed: Optional[int]
    trace_parent: Optional[str]

    def to_a2a_extension(self) -> dict:
        """Serialize this envelope to a plain dict for a swarm-a2a extension payload."""
        data = asdict(self)
        data["artifact_hashes"] = list(self.artifact_hashes)
        return data

    @classmethod
    def from_a2a_extension(cls, data: dict) -> "HandoffEnvelope":
        """Reconstruct a HandoffEnvelope from a swarm-a2a extension payload dict."""
        fields = dict(data)
        fields["artifact_hashes"] = tuple(fields["artifact_hashes"])
        return cls(**fields)
