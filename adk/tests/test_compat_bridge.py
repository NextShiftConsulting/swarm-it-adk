"""Tests for _compat.py and _config_bridge.py — controlplane bridge layer."""

import pytest
from yrsn_controlplane import (
    MeasurementEstimate,
    EnforcementDecision,
    GatekeeperConfig,
    GatekeeperResult,
    SequentialGatekeeper,
    get_preset,
)

from swarm_it._compat import (
    GateDecision,
    from_enforcement_decision,
    from_gatekeeper_result,
    to_certificate_estimate,
)
from swarm_it._config_bridge import (
    model_id_to_config,
    thresholds_to_config,
)


class TestGateDecisionEnum:
    """Tests for ADK GateDecision enum properties."""

    def test_core_decisions_match_enforcement(self):
        """Core values are 1:1 with EnforcementDecision."""
        for ed in EnforcementDecision:
            gd = GateDecision(ed.value)
            assert gd.value == ed.value

    def test_allowed_property(self):
        assert GateDecision.EXECUTE.allowed is True
        assert GateDecision.REPAIR.allowed is True
        assert GateDecision.WARN.allowed is True
        assert GateDecision.FALLBACK.allowed is True
        assert GateDecision.PASS_FAST.allowed is True
        assert GateDecision.PASS_GUARDED.allowed is True
        assert GateDecision.REJECT.allowed is False
        assert GateDecision.BLOCK.allowed is False
        assert GateDecision.HALT.allowed is False
        assert GateDecision.TIMEOUT.allowed is False
        assert GateDecision.ESCALATE.allowed is False

    def test_requires_action_property(self):
        assert GateDecision.RE_ENCODE.requires_action is True
        assert GateDecision.REPAIR.requires_action is True
        assert GateDecision.ESCALATE.requires_action is True
        assert GateDecision.EXECUTE.requires_action is False
        assert GateDecision.REJECT.requires_action is False

    def test_to_enforcement_decision_core(self):
        """Core decisions round-trip to EnforcementDecision."""
        assert GateDecision.EXECUTE.to_enforcement_decision() == EnforcementDecision.EXECUTE
        assert GateDecision.REJECT.to_enforcement_decision() == EnforcementDecision.REJECT
        assert GateDecision.BLOCK.to_enforcement_decision() == EnforcementDecision.BLOCK
        assert GateDecision.RE_ENCODE.to_enforcement_decision() == EnforcementDecision.RE_ENCODE
        assert GateDecision.REPAIR.to_enforcement_decision() == EnforcementDecision.REPAIR

    def test_to_enforcement_decision_legacy_maps_to_execute(self):
        """Legacy decisions map to EXECUTE."""
        assert GateDecision.PASS_FAST.to_enforcement_decision() == EnforcementDecision.EXECUTE
        assert GateDecision.PASS_GUARDED.to_enforcement_decision() == EnforcementDecision.EXECUTE

    def test_to_enforcement_decision_adk_only_returns_none(self):
        """ADK-only decisions have no controlplane equivalent."""
        assert GateDecision.HALT.to_enforcement_decision() is None
        assert GateDecision.TIMEOUT.to_enforcement_decision() is None
        assert GateDecision.ESCALATE.to_enforcement_decision() is None


class TestFromEnforcementDecision:
    """Tests for from_enforcement_decision()."""

    @pytest.mark.parametrize("ed", list(EnforcementDecision))
    def test_all_enforcement_decisions_convert(self, ed):
        """Every EnforcementDecision maps to a GateDecision."""
        gd = from_enforcement_decision(ed)
        assert isinstance(gd, GateDecision)
        assert gd.value == ed.value


class TestFromGatekeeperResult:
    """Tests for from_gatekeeper_result()."""

    def test_execute_result(self):
        gk = SequentialGatekeeper()
        est = to_certificate_estimate(R=0.7, S=0.2, N=0.1, kappa_gate=0.8, sigma=0.2, alpha=0.875)
        result = gk.evaluate(est)
        decision = from_gatekeeper_result(result)
        assert isinstance(decision, GateDecision)

    def test_high_noise_rejects(self):
        gk = SequentialGatekeeper()
        est = to_certificate_estimate(R=0.1, S=0.1, N=0.8, kappa_gate=0.3, sigma=0.8, alpha=0.11)
        result = gk.evaluate(est)
        decision = from_gatekeeper_result(result)
        assert decision.allowed is False


class TestToMeasurementEstimate:
    """Tests for to_certificate_estimate()."""

    def test_basic_estimate(self):
        est = to_certificate_estimate(R=0.6, S=0.3, N=0.1, kappa_gate=0.7, sigma=0.3, alpha=0.85)
        assert isinstance(est, MeasurementEstimate)
        assert est.alpha == 0.85
        assert est.kappa_gate == 0.7
        assert est.sigma == 0.3

    def test_alpha_auto_computed(self):
        est = to_certificate_estimate(R=0.6, S=0.3, N=0.1, kappa_gate=0.7, sigma=0.3)
        expected_alpha = 0.6 / (0.6 + 0.1)
        assert abs(est.alpha - expected_alpha) < 1e-9

    def test_alpha_zero_division(self):
        est = to_certificate_estimate(R=0.0, S=1.0, N=0.0, kappa_gate=0.5, sigma=0.5)
        assert est.alpha == 0.0

    def test_extended_kappa_fields(self):
        # kappa_gate must equal min(kappa_H, kappa_L, kappa_interface)
        est = to_certificate_estimate(
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.6, sigma=0.3, alpha=0.85,
            kappa_H=0.8, kappa_L=0.6, kappa_interface=0.7,
        )
        assert est.kappa_H == 0.8
        assert est.kappa_L == 0.6
        assert est.kappa_interface == 0.7

    def test_coherence_in_evidence(self):
        est = to_certificate_estimate(
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7, sigma=0.3, alpha=0.85,
            coherence=0.9,
        )
        assert est.evidence["coherence"] == 0.9

    def test_estimate_accepted_by_gatekeeper(self):
        """Estimate produced by bridge is valid input for SequentialGatekeeper."""
        est = to_certificate_estimate(R=0.6, S=0.3, N=0.1, kappa_gate=0.7, sigma=0.3, alpha=0.85)
        gk = SequentialGatekeeper()
        result = gk.evaluate(est)
        assert isinstance(result, GatekeeperResult)


class TestThresholdsToConfig:
    """Tests for thresholds_to_config()."""

    def test_basic_mapping(self):
        config = thresholds_to_config({"kappa": 0.7, "R": 0.3, "S": 0.4, "N": 0.5})
        assert isinstance(config, GatekeeperConfig)
        assert config.N_thr == 0.5
        assert config.alpha_min == 0.3
        assert config.c_min == 0.4
        assert config.kappa_base == 0.7

    def test_defaults_when_missing(self):
        config = thresholds_to_config({})
        assert config.N_thr == 0.5
        assert config.alpha_min == 0.3
        assert config.c_min == 0.4
        assert config.kappa_base == 0.5

    def test_kappa_l_threshold(self):
        config = thresholds_to_config({"kappa_L": 0.4})
        assert config.kappa_L_min == 0.4

    def test_config_accepted_by_gatekeeper(self):
        """Config produced by bridge is valid for SequentialGatekeeper."""
        config = thresholds_to_config({"kappa": 0.6, "N": 0.4})
        gk = SequentialGatekeeper(config)
        est = to_certificate_estimate(R=0.5, S=0.3, N=0.2, kappa_gate=0.6, sigma=0.3, alpha=0.71)
        result = gk.evaluate(est)
        assert isinstance(result, GatekeeperResult)


class TestModelIdToConfig:
    """Tests for model_id_to_config()."""

    @pytest.mark.parametrize("model_id", ["universal64", "strict", "permissive", "research", "multimodal"])
    def test_known_model_ids(self, model_id):
        config = model_id_to_config(model_id)
        assert isinstance(config, GatekeeperConfig)

    def test_unknown_model_id_falls_back_to_universal(self):
        config = model_id_to_config("nonexistent")
        universal = get_preset("universal")
        assert config.N_thr == universal.N_thr
        assert config.alpha_min == universal.alpha_min
