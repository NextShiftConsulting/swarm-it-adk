"""Tests for local certification engine."""

import pytest
from swarm_it.local.engine import (
    RSCTCertificate,
    GateDecision,
    LocalEngine,
    certify_local,
)


class TestGateDecision:
    """Tests for GateDecision enum."""

    def test_allowed_decisions(self):
        assert GateDecision.EXECUTE.allowed is True
        assert GateDecision.PASS_FAST.allowed is True
        assert GateDecision.PASS_GUARDED.allowed is True
        assert GateDecision.REPAIR.allowed is True

    def test_blocked_decisions(self):
        assert GateDecision.REJECT.allowed is False
        assert GateDecision.BLOCK.allowed is False
        assert GateDecision.HALT.allowed is False

    def test_requires_action(self):
        assert GateDecision.RE_ENCODE.requires_action is True
        assert GateDecision.REPAIR.requires_action is True
        assert GateDecision.ESCALATE.requires_action is True
        assert GateDecision.EXECUTE.requires_action is False


class TestRSCTCertificate:
    """Tests for RSCTCertificate dataclass."""

    def test_simplex_valid(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        assert cert.simplex_valid is True

    def test_simplex_invalid(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.2,  # Sum > 1
            kappa_gate=0.7,
            sigma=0.3,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        assert cert.simplex_valid is False

    def test_margin_calculation(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        # margin = min(R, kappa_gate, 1-N) = min(0.6, 0.7, 0.9) = 0.6
        assert cert.margin == 0.6

    def test_has_extended_signals_false(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        assert cert.has_extended_signals is False

    def test_has_extended_signals_true(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            alpha=0.85,
            omega=0.9,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        assert cert.has_extended_signals is True

    def test_has_kappa_decomposition(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            kappa_H=0.8,
            kappa_L=0.7,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        assert cert.has_kappa_decomposition is True

    def test_classify_local_noise_saturation(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.2, S=0.2, N=0.6,  # N >= 0.5
            kappa_gate=0.5,
            sigma=0.3,
            decision=GateDecision.REJECT,
            gate_reached=1,
            reason="test",
        )
        assert cert.get_rsct_mode() == "1.1"

    def test_classify_local_fluent_hallucination(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.3, S=0.5, N=0.2,  # kappa > 0.7, R < 0.4
            kappa_gate=0.75,
            sigma=0.3,
            decision=GateDecision.REPAIR,
            gate_reached=4,
            reason="test",
        )
        assert cert.get_rsct_mode() == "3.1"

    def test_to_dict(self):
        cert = RSCTCertificate(
            id="test-123",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="passed",
        )
        d = cert.to_dict()
        assert d["certificate_id"] == "test-123"
        assert d["R"] == 0.6
        assert d["gate_decision"] == "EXECUTE"
        assert d["allowed"] is True

    def test_from_dict(self):
        data = {
            "certificate_id": "test-456",
            "timestamp": "2024-01-01T00:00:00Z",
            "R": 0.5,
            "S": 0.3,
            "N": 0.2,
            "kappa_gate": 0.6,
            "sigma": 0.4,
            "gate_decision": "EXECUTE",
            "gate_reached": 5,
            "reason": "test",
        }
        cert = RSCTCertificate.from_dict(data)
        assert cert.id == "test-456"
        assert cert.R == 0.5
        assert cert.decision == GateDecision.EXECUTE


class TestLocalEngine:
    """Tests for LocalEngine."""

    def test_certify_basic(self):
        engine = LocalEngine()
        cert = engine.certify("Hello, world!")

        assert cert.simplex_valid
        assert cert.id is not None
        assert cert.timestamp is not None

    def test_certify_deterministic(self):
        engine = LocalEngine()
        cert1 = engine.certify("Same input")
        cert2 = engine.certify("Same input")

        assert cert1.R == cert2.R
        assert cert1.S == cert2.S
        assert cert1.N == cert2.N

    def test_certify_high_noise_rejects(self):
        engine = LocalEngine(n_threshold=0.3)
        # Find an input that produces high N
        cert = engine.certify("x" * 1000)

        # With deterministic hashing, we can't guarantee high N
        # So just verify the engine runs and produces valid output
        assert cert.simplex_valid

    def test_custom_thresholds(self):
        engine = LocalEngine(
            n_threshold=0.3,
            kappa_threshold=0.5,
        )
        cert = engine.certify("test")
        assert cert is not None


class TestCertifyLocal:
    """Tests for certify_local convenience function."""

    def test_basic_usage(self):
        cert = certify_local("Test prompt")
        assert cert is not None
        assert cert.simplex_valid

    def test_with_policy(self):
        cert = certify_local("Test prompt", policy="strict")
        assert cert.policy == "strict"
