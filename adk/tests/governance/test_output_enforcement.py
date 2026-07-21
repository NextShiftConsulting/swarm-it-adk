"""Tests for the output-boundary recertification (V-013 T5).

Before a successor's produced output crosses the GOVERNED boundary, it is
re-certified fresh. Gate authority stays with the injected `certifier` port
(ADR-004/064) — this module contains no gate math of its own. Everything
here is fail-closed: output that fails re-cert does NOT leave the boundary.
"""

import dataclasses
from typing import Optional

import pytest

from swarm_it.governance import get_trace, reset_trace
from swarm_it.governance.output_boundary import OutputVerdict, recertify_on_output


@dataclasses.dataclass
class FakeCert:
    """Minimal cert-like double: .id, .verdict.

    Stands in for a real controlplane-issued certificate (e.g.
    RSCTCertificate) without pulling in any gate math.
    """

    id: str
    verdict: str
    kappa_compat: Optional[float] = None


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_trace()
    yield
    reset_trace()


def test_passing_output_is_released():
    def certifier(produced_state):
        return FakeCert(id="cert-OUT", verdict="EXECUTE")

    verdict = recertify_on_output({"produced": "state"}, certifier=certifier, handoff_id="handoff-001")

    assert verdict.ok is True
    assert verdict.released is True
    assert verdict.reason == "OUTPUT_RECERTIFIED"
    assert verdict.certificate_ref == "cert-OUT"

    trace = get_trace()
    assert trace[-1].event == "output_recertify"
    assert trace[-1].reason == "OUTPUT_RECERTIFIED"
    assert trace[-1].handoff_id == "handoff-001"


def test_failing_output_not_released():
    def certifier(produced_state):
        return FakeCert(id="cert-OUT", verdict="REPAIR")

    verdict = recertify_on_output({"produced": "state"}, certifier=certifier, handoff_id="handoff-002")

    assert verdict.ok is False
    assert verdict.released is False
    assert verdict.reason == "OUTPUT_RECERT_REFUSED"

    trace = get_trace()
    assert trace[-1].reason == "OUTPUT_RECERT_REFUSED"
    assert trace[-1].handoff_id == "handoff-002"


def test_missing_certifier_fails_closed():
    verdict = recertify_on_output({"produced": "state"}, certifier=None, handoff_id="handoff-003")

    assert verdict.ok is False
    assert verdict.released is False
    assert verdict.reason == "MISSING_CERTIFIER"

    trace = get_trace()
    assert trace[-1].reason == "MISSING_CERTIFIER"
    assert trace[-1].handoff_id == "handoff-003"


def test_certifier_exception_fails_closed():
    def certifier(produced_state):
        raise RuntimeError("certifier blew up")

    verdict = recertify_on_output({"produced": "state"}, certifier=certifier, handoff_id="handoff-004")

    assert verdict.ok is False
    assert verdict.released is False
    assert verdict.reason == "OUTPUT_CERTIFIER_ERROR"

    trace = get_trace()
    assert trace[-1].reason == "OUTPUT_CERTIFIER_ERROR"
    assert trace[-1].handoff_id == "handoff-004"


def test_no_prohibited_tokens_in_source():
    from pathlib import Path

    from swarm_it.governance import output_boundary

    source = Path(output_boundary.__file__).read_text(encoding="utf-8")
    assert "sigma" not in source.lower()
    assert "kappa_gate" not in source.lower()
    assert "time.time(" not in source
    assert "datetime.now(" not in source


def test_output_verdict_is_frozen_dataclass():
    verdict = OutputVerdict(ok=True, released=True, reason="OUTPUT_RECERTIFIED", certificate_ref="cert-OUT")
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.ok = False
