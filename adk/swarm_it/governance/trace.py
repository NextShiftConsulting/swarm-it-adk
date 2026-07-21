"""Append-only trace sink for governance events.

TraceRecord is inert observability, not a decision. Nothing in this
module resolves a certificate, computes a gate outcome, or authorizes
anything — it only records what happened so the chain is auditable.
The sink is append-only by construction: emit() appends and nothing in
this module ever overwrites or deletes an existing record.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class TraceRecord:
    """One immutable observation emitted at a governance boundary."""

    event: str
    reason: str
    handoff_id: Optional[str]
    detail: dict = field(default_factory=dict)
    trace_parent: Optional[str] = None


_TRACE: list[TraceRecord] = []


def emit(record: TraceRecord) -> None:
    """Append a TraceRecord to the in-process sink. Never overwrites or deletes."""
    _TRACE.append(record)


def get_trace() -> tuple[TraceRecord, ...]:
    """Return an immutable snapshot of every record emitted so far, in order."""
    return tuple(_TRACE)


def reset_trace() -> None:
    """Clear the sink. Test isolation only — not for use in business logic."""
    _TRACE.clear()
