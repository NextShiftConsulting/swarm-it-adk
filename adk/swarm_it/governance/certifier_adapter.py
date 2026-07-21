"""Certifier adapter — normalizes real certificate types for the boundaries.

receive_boundary.py, output_boundary.py, and _certifier_shims.py all read a
derived certificate's `.kappa_compat` / `.allowed` / `.id` / `.expires_at`
by duck-typing. That works for the FakeCert test doubles used in the
governance unit tests, but the two REAL certificate types this repo
produces do not share one shape:

- RSCTCertificate (swarm_it.local.engine) exposes `.kappa_compat` directly.
- SwarmCertificate (swarm_it.topology.certifier) exposes the same
  per-hop ENFORCED proxy value under `.kappa_compat_chain_min` instead —
  it has no `.kappa_compat` attribute at all.

Feeding a raw SwarmCertificate straight into the boundaries therefore
reads kappa_compat=None on every hop, which ChainKappaTracker treats as
incomparable and fails closed, regardless of the swarm certificate's
actual verdict (V-013 finding I1).

This module is the single place that maps either real type (or anything
duck-type-compatible with them) onto one NormalizedCertificate shape, so
the boundaries can be driven by a real certifier without changing their
reading logic. It contains no gate math and makes no allow/refuse
decision of its own — `allowed` is read via the existing
`derived_verdict_ok` shim so that duck-typing still lives in exactly one
place.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from swarm_it.governance._certifier_shims import derived_verdict_ok


@dataclass(frozen=True)
class NormalizedCertificate:
    """The one shape the governance boundaries are written to read.

    id: certificate identifier, or None if the source cert exposes none.
    kappa_compat: the per-hop ENFORCED compatibility proxy. Prefer the
        source's own `.kappa_compat`; if absent, fall back to
        `.kappa_compat_chain_min` (SwarmCertificate's name for the same
        proxy). None if neither is present — callers must treat that as
        incomparable, same as today.
    allowed: pass/fail verdict, read via derived_verdict_ok so the
        duck-typing precedence (`.allowed` then `.verdict == "EXECUTE"`)
        stays defined in exactly one place.
    expires_at: staleness marker, None-safe. Neither real cert type
        currently carries one; that is expected, not an adapter bug.
    """

    id: Optional[str]
    kappa_compat: Optional[float]
    allowed: bool
    expires_at: Optional[float] = None


def normalize_certificate(cert: Any) -> NormalizedCertificate:
    """Map a real (or duck-type-compatible) certificate onto NormalizedCertificate.

    kappa_compat precedence: `.kappa_compat` wins when present; otherwise
    fall back to `.kappa_compat_chain_min` (SwarmCertificate). This is the
    fix for I1 — without the fallback, a SwarmCertificate's enforced
    proxy is invisible to the boundaries.
    """
    kappa_compat = getattr(cert, "kappa_compat", None)
    if kappa_compat is None:
        kappa_compat = getattr(cert, "kappa_compat_chain_min", None)

    return NormalizedCertificate(
        id=getattr(cert, "id", None),
        kappa_compat=kappa_compat,
        allowed=derived_verdict_ok(cert),
        expires_at=getattr(cert, "expires_at", None),
    )


def make_certifier(certify_fn: Callable[[Any], Any]) -> Callable[[Any], NormalizedCertificate]:
    """Wrap a raw certification function so it returns a NormalizedCertificate.

    `certify_fn` is any callable that produces a real certificate (e.g. a
    bound `LocalEngine.certify`, `SwarmCertifier.certify`, or a
    controlplane-backed certifier) from a state argument. The returned
    callable is what receive_boundary/output_boundary expect for their
    `certifier` port.
    """

    def _certifier(state: Any) -> NormalizedCertificate:
        return normalize_certificate(certify_fn(state))

    return _certifier
