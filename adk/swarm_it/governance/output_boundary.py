"""Output-boundary recertification: the successor side of the handoff.

Before a successor's produced output crosses the GOVERNED boundary, it is
re-certified fresh — never carried over from whatever certificate admitted
the successor's input (ADR-062 Claim 9 applies here too: no reuse, no
mutation, only a new derivation). Gate authority stays with the
controlplane (ADR-004/064): this module contains no R/S/N math and no
threshold decision of its own; it only requests certification through the
injected `certifier` port and reads the verdict that comes back.

Fail-closed everywhere: output is released ONLY on a clean EXECUTE from the
certifier. A missing certifier, a refusing verdict, and a crashing
certifier all keep the output inside the boundary.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from swarm_it.governance._certifier_shims import derived_verdict_ok
from swarm_it.governance.trace import TraceRecord, emit


@dataclass(frozen=True)
class OutputVerdict:
    """Outcome of output-boundary recertification."""

    ok: bool
    released: bool
    reason: str
    certificate_ref: Optional[str] = None


def _fail(reason: str, handoff_id: Optional[str], detail: Optional[dict] = None) -> OutputVerdict:
    emit(
        TraceRecord(
            event="output_recertify",
            reason=reason,
            handoff_id=handoff_id,
            detail=detail or {},
        )
    )
    return OutputVerdict(ok=False, released=False, reason=reason)


def recertify_on_output(
    produced_state: Any,
    *,
    certifier: Optional[Callable[[Any], Any]] = None,
    handoff_id: Optional[str] = None,
) -> OutputVerdict:
    """Re-certify `produced_state` before it leaves the GOVERNED boundary.

    Calls `certifier(produced_state)` and reads what comes back — this
    module never decides the verdict itself. `certifier is None` is a
    missing-config error, not "skip the check": it fails closed
    (MISSING_CERTIFIER), never a default-permissive pass. A refusing
    (non-EXECUTE) derived verdict fails closed (OUTPUT_RECERT_REFUSED). A
    certifier that raises fails closed (OUTPUT_CERTIFIER_ERROR) rather than
    letting the exception propagate and the output escape unreleased-but-
    unaccounted-for. Only a clean EXECUTE releases the output.
    """
    if certifier is None:
        return _fail("MISSING_CERTIFIER", handoff_id)

    try:
        derived = certifier(produced_state)
    except Exception as exc:
        return _fail("OUTPUT_CERTIFIER_ERROR", handoff_id, {"error": str(exc)})

    if not derived_verdict_ok(derived):
        return _fail("OUTPUT_RECERT_REFUSED", handoff_id, {"derived_certificate_id": getattr(derived, "id", None)})

    certificate_ref = getattr(derived, "id", None)
    verdict = OutputVerdict(
        ok=True,
        released=True,
        reason="OUTPUT_RECERTIFIED",
        certificate_ref=certificate_ref,
    )
    emit(
        TraceRecord(
            event="output_recertify",
            reason=verdict.reason,
            handoff_id=handoff_id,
            detail={"certificate_ref": certificate_ref},
        )
    )
    return verdict
