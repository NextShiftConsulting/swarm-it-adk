"""Shared duck-typed certifier-verdict shim for the governance boundaries.

receive_boundary.py, output_boundary.py, and topology_policy.py each need
to read a pass/fail verdict off whatever the injected `certifier` port
returns, without assuming a single concrete certificate type. This module
exists so that duck-typing lives in exactly one place instead of being
copy-pasted three times.
"""

from typing import Any


def derived_verdict_ok(derived: Any) -> bool:
    """Duck-typed pass/fail read of a certifier-derived certificate.

    Real controlplane certs expose `.allowed`; simple test doubles may
    only expose `.verdict == "EXECUTE"`. Neither attribute present fails
    closed (returns False) rather than guessing.
    """
    if hasattr(derived, "allowed"):
        return bool(derived.allowed)
    if hasattr(derived, "verdict"):
        return derived.verdict == "EXECUTE"
    return False
