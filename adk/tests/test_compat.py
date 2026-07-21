"""Contract tests for _compat output-direction normalization (V-013 Decision 2).

Folded in from the removed governance/certifier_adapter.py. The load-bearing case
is the real SwarmCertificate, whose enforced proxy is `.kappa_compat_chain_min`
(no `.kappa_compat`) — normalize_certificate must surface it.
"""
from types import SimpleNamespace

from swarm_it._compat import (
    NormalizedCertificate,
    make_certifier,
    normalize_certificate,
)


def test_normalize_kappa_compat_direct():
    cert = SimpleNamespace(id="c1", kappa_compat=0.7, allowed=True)
    n = normalize_certificate(cert)
    assert isinstance(n, NormalizedCertificate)
    assert n.id == "c1" and n.kappa_compat == 0.7 and n.allowed is True


def test_normalize_real_swarm_certificate_uses_chain_min():
    # The I1 fix on the REAL type: SwarmCertificate exposes kappa_compat_chain_min,
    # not kappa_compat. normalize must surface the chain-min as kappa_compat.
    from swarm_it.topology.certifier import SwarmCertifier
    from swarm_it.topology.models import Agent, Channel, Swarm

    swarm = Swarm(
        id="s1", name="Healthy",
        agents=[
            Agent(id="a1", name="A", role="r", kappa_H=0.8, kappa_L=0.8),
            Agent(id="a2", name="B", role="r", kappa_H=0.7, kappa_L=0.7),
        ],
        channels=[Channel("a1", "a2", "delegation", kappa_interface=0.8)],
    )
    cert = SwarmCertifier().certify(swarm)
    assert not hasattr(cert, "kappa_compat")  # confirms the mismatch this fixes
    n = normalize_certificate(cert)
    assert n.kappa_compat == cert.kappa_compat_chain_min
    assert n.kappa_compat is not None
    assert n.allowed == cert.allowed


def test_unknown_shape_fails_closed():
    n = normalize_certificate(SimpleNamespace())  # no .allowed, no .verdict
    assert n.allowed is False


def test_make_certifier_returns_normalized():
    raw = lambda state: SimpleNamespace(id="x", kappa_compat=0.6, allowed=True)
    certifier = make_certifier(raw)
    n = certifier("some-state")
    assert isinstance(n, NormalizedCertificate)
    assert n.kappa_compat == 0.6 and n.allowed is True


def test_no_gate_math_or_prohibited_tokens_in_source():
    import swarm_it._compat as m
    from pathlib import Path
    src = Path(m.__file__).read_text(encoding="utf-8")
    assert "kappa_gate" not in src
