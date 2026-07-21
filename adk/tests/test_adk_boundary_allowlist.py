"""ADK boundary gate: the ADK is app-agnostic (governed envelope, not the brain).

Subfolders under ``adk/swarm_it/`` partition by MECHANISM (framework, transport,
persistence, port, coordination), never by APP / customer / domain. An app
subfolder (``floodcaster/``, ``igor/``, ``marketron/`` ...) is by construction
the place the forbidden things accumulate -- entitlement, plan/policy truth,
tenant membership, wallet/certificate logic, domain rules -- and it couples the
ADK's release, IP, and tenant boundaries. Apps CONSUME the ADK from their own
repos, each through a port; they do not live inside it.

Fail-closed: any directory under ``adk/swarm_it/`` not on the MECHANISM_DIRS
allowlist trips CI, forcing the app-vs-mechanism decision at PR time. If the new
dir is a mechanism, add it here with a one-line note; if it is an app/domain, it
belongs in its own repo (do NOT add it).

Necessary, not sufficient: this catches app-named top-level dirs, not app logic
smuggled into a mechanism dir.
"""

from pathlib import Path

# Mechanism directories the ADK may contain. Extend ONLY with mechanism terms.
MECHANISM_DIRS = {
    # --- present today ---
    "integrations",   # framework/transport integration adapters
    "local",          # local / in-process runtime
    "persistence",    # storage adapters
    "providers",      # port interfaces + null / reference implementations
    "taxonomy",       # failure / decision taxonomy
    "topology",       # coordination patterns
    # governance/ removed from main 2026-07-21 (V-013 orphaned parallel stack; snapshot tag v013-orphan-snapshot; see ADR-079 amendment). Re-add when reconciled onto canonical surfaces.
    # --- agreed target structure (governed-envelope ADK); checked only if present ---
    "contracts",      # stable canonical objects (identity, delegation, execution, certificate, events)
    "runtime",        # execution guard / tool + handoff interceptors / outcome reporter
    "client",         # authenticated API clients (junction/auth/certify/payment)
    "adapters",       # framework adapters (langgraph, crewai, autogen, mcp, a2a, direct_http)
    "onboarding",     # config generator / connection test / diagnostics
    "events",         # canonical event schema
}

# Known app / customer / domain tokens -> a clearer failure message than the
# generic allowlist miss. Redundant with the allowlist (which already fails);
# this only names the specific mistake.
APP_TOKENS = {
    "floodcaster", "igor", "marketron", "geometry", "ibbs", "omd",
    "nfip", "hydrology", "insurer", "carrier", "tenant",
}

_PKG = Path(__file__).resolve().parents[1] / "swarm_it"


def _subdirs():
    if not _PKG.is_dir():
        return []
    return [p.name for p in _PKG.iterdir()
            if p.is_dir() and not p.name.startswith((".", "__"))]


def test_adk_has_no_app_subfolders():
    offenders = []
    for name in _subdirs():
        low = name.lower()
        if any(tok in low for tok in APP_TOKENS):
            offenders.append(
                (name, "app/customer/domain name -- apps live in their own repo "
                       "and consume the ADK through a port, not inside it"))
        elif low not in MECHANISM_DIRS:
            offenders.append(
                (name, "not on the MECHANISM_DIRS allowlist -- if it is a mechanism, "
                       "add it (with a note); if it is an app/domain, it does not "
                       "belong in the ADK"))
    assert not offenders, (
        "ADK boundary violation -- the ADK must stay app-agnostic "
        "(governed envelope, not the brain):\n"
        + "\n".join(f"  adk/swarm_it/{n}/  ->  {why}" for n, why in offenders)
    )
