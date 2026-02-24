"""Tests for taxonomy classification."""

import pytest
from swarm_it.local.engine import RSCTCertificate, GateDecision
from swarm_it.taxonomy.classification import (
    RSCTMode,
    DegradationType,
    Severity,
    classify_certificate,
    add_error_codes,
    diagnose_multimodal,
)
from swarm_it.taxonomy.feedback import (
    ValidationFeedbackLoop,
    ValidationType,
)
from swarm_it.taxonomy.bridge import (
    to_yrsn_dict,
    from_yrsn_dict,
    extract_hierarchy,
    validate_round_trip,
)


class TestClassification:
    """Tests for certificate classification."""

    def test_classify_nominal(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.7, S=0.2, N=0.1,
            kappa_gate=0.8,
            sigma=0.2,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        result = classify_certificate(cert)
        assert result.rsct_mode == RSCTMode.NOMINAL
        assert result.degradation_type == DegradationType.NOMINAL
        assert result.severity == Severity.TRACE

    def test_classify_noise_saturation(self):
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
        result = classify_certificate(cert)
        assert result.rsct_mode == RSCTMode.NOISE_SATURATION
        assert result.severity == Severity.FATAL

    def test_classify_fluent_hallucination(self):
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
        result = classify_certificate(cert)
        assert result.rsct_mode == RSCTMode.FLUENT_HALLUCINATION
        assert result.degradation_type == DegradationType.HALLUCINATION

    def test_classify_trajectory_divergence(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.5, S=0.3, N=0.2,
            kappa_gate=0.6,
            sigma=0.8,  # sigma > 0.7
            decision=GateDecision.BLOCK,
            gate_reached=2,
            reason="test",
        )
        result = classify_certificate(cert)
        assert result.rsct_mode == RSCTMode.TRAJECTORY_DIVERGENCE

    def test_error_codes_generated(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.2, S=0.2, N=0.6,
            kappa_gate=0.5,
            sigma=0.3,
            decision=GateDecision.REJECT,
            gate_reached=1,
            reason="test",
        )
        result = classify_certificate(cert)
        assert "V1.1.1" in result.error_codes  # Noise saturation


class TestMultimodalClassification:
    """Tests for multimodal kappa classification."""

    def test_weakest_link_cascade(self):
        """V4.4.1: One modality drags gate below threshold."""
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.25,  # min of decomposition
            sigma=0.3,
            kappa_H=0.8,  # Healthy
            kappa_L=0.25,  # Critical - weakest link
            kappa_A=0.7,
            decision=GateDecision.REPAIR,
            gate_reached=4,
            reason="test",
        )
        result = classify_certificate(cert)
        assert result.rsct_mode == RSCTMode.WEAKEST_LINK_CASCADE
        assert "V4.4.1" in result.error_codes

    def test_cross_modal_desync(self):
        """V4.4.2: Interface kappa below threshold."""
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.25,
            sigma=0.3,
            kappa_H=0.7,
            kappa_L=0.7,
            kappa_interface=0.25,  # Interface degraded
            decision=GateDecision.REPAIR,
            gate_reached=4,
            reason="test",
        )
        result = classify_certificate(cert)
        assert result.rsct_mode == RSCTMode.CROSS_MODAL_DESYNC
        assert "V4.4.2" in result.error_codes

    def test_diagnose_multimodal_healthy(self):
        """All modalities healthy."""
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            kappa_H=0.8,
            kappa_L=0.75,
            kappa_interface=0.7,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        diag = diagnose_multimodal(cert)
        assert diag["available"] is True
        assert diag["is_desynced"] is False
        assert all(h == "healthy" for h in diag["health"].values())

    def test_diagnose_multimodal_degraded(self):
        """One modality degraded."""
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.5,
            sigma=0.3,
            kappa_H=0.8,
            kappa_L=0.5,  # Degraded
            kappa_interface=0.7,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        diag = diagnose_multimodal(cert)
        assert diag["available"] is True
        assert diag["health"]["low_level"] == "degraded"
        assert diag["weakest"] == "low_level"

    def test_diagnose_multimodal_critical(self):
        """One modality critical."""
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.3,
            sigma=0.3,
            kappa_H=0.8,
            kappa_L=0.3,  # Critical
            kappa_interface=0.7,
            decision=GateDecision.REPAIR,
            gate_reached=4,
            reason="test",
        )
        diag = diagnose_multimodal(cert)
        assert diag["available"] is True
        assert diag["is_desynced"] is True
        assert diag["health"]["low_level"] == "critical"
        assert len(diag["recommendations"]) > 0

    def test_diagnose_multimodal_not_available(self):
        """Single-modal certificate."""
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
        diag = diagnose_multimodal(cert)
        assert diag["available"] is False

    def test_hierarchy_gap_detection(self):
        """High gap between H and L kappa."""
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.4,
            sigma=0.3,
            kappa_H=0.9,
            kappa_L=0.4,  # Gap = 0.5 > 0.3
            kappa_interface=0.7,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        diag = diagnose_multimodal(cert)
        # Should flag high spread
        assert any("spread" in r.lower() or "sync" in r.lower() for r in diag["recommendations"])

    def test_kappa_gate_enforcement(self):
        """kappa_gate should be used for enforcement, not individual kappas."""
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.25,  # This is what matters
            sigma=0.3,
            kappa_H=0.8,  # Individual kappas healthy
            kappa_L=0.25,  # Except this one
            decision=GateDecision.REPAIR,
            gate_reached=4,
            reason="test",
        )
        # Classify uses kappa_gate for mode detection
        result = classify_certificate(cert)
        # Should detect weakest-link pattern
        assert result.rsct_mode in (RSCTMode.WEAKEST_LINK_CASCADE, RSCTMode.CROSS_MODAL_DESYNC)


class TestAddErrorCodes:
    """Tests for add_error_codes function."""

    def test_add_codes_modifies_certificate(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.2, S=0.2, N=0.6,
            kappa_gate=0.5,
            sigma=0.3,
            decision=GateDecision.REJECT,
            gate_reached=1,
            reason="test",
        )
        updated = add_error_codes(cert)
        assert updated is cert  # Same object
        assert len(cert.error_codes) > 0
        assert cert.rsct_mode is not None


class TestValidationFeedbackLoop:
    """Tests for ValidationFeedbackLoop."""

    def test_record_validation(self):
        loop = ValidationFeedbackLoop()
        event = loop.record(
            certificate_id="cert-1",
            validation_type=ValidationType.TYPE_I,
            score=0.8,
            failed=True,
        )
        assert event.certificate_id == "cert-1"
        assert event.failed is True

    def test_compute_adjustments_not_enough_samples(self):
        loop = ValidationFeedbackLoop(min_samples=10)
        for i in range(5):
            loop.record(f"cert-{i}", ValidationType.TYPE_I, 0.8, True)
        adjustments = loop.compute_adjustments()
        assert len(adjustments) == 0  # Not enough samples

    def test_compute_adjustments_with_failures(self):
        loop = ValidationFeedbackLoop(min_samples=10)
        # Record 20 Type I validations, 15 failed (75% rate > 10% threshold)
        for i in range(20):
            loop.record(f"cert-{i}", ValidationType.TYPE_I, 0.8, i < 15)
        adjustments = loop.compute_adjustments()
        # Should recommend tightening N_threshold
        assert any(a.parameter == "N_threshold" for a in adjustments)

    def test_get_failure_rates(self):
        loop = ValidationFeedbackLoop()
        loop.record("cert-1", ValidationType.TYPE_I, 0.8, True)
        loop.record("cert-2", ValidationType.TYPE_I, 0.3, False)
        rates = loop.get_failure_rates()
        assert rates["type_I"] == 0.5


class TestBridge:
    """Tests for certificate bridge."""

    def test_to_yrsn_dict(self):
        cert = RSCTCertificate(
            id="test-123",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        yrsn_dict = to_yrsn_dict(cert)
        assert yrsn_dict["certificate_id"] == "test-123"
        assert yrsn_dict["S_sup"] == 0.3  # Uses yrsn naming
        assert yrsn_dict["source"] == "swarm_it_sdk"

    def test_from_yrsn_dict(self):
        data = {
            "certificate_id": "test-456",
            "timestamp": "2024-01-01T00:00:00Z",
            "R": 0.5,
            "S_sup": 0.3,  # yrsn naming
            "N": 0.2,
            "kappa_gate": 0.6,
            "sigma": 0.4,
            "gate_decision": "EXECUTE",
            "gate_reached": 5,
            "gate_reason": "test",
        }
        cert = from_yrsn_dict(data)
        assert cert.id == "test-456"
        assert cert.S == 0.3

    def test_round_trip(self):
        cert = RSCTCertificate(
            id="test-789",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.7,
            sigma=0.3,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        assert validate_round_trip(cert) is True

    def test_multimodal_round_trip(self):
        """Multimodal hierarchy should survive round-trip."""
        cert = RSCTCertificate(
            id="test-multimodal",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.65,
            sigma=0.3,
            kappa_H=0.8,
            kappa_L=0.65,
            kappa_A=0.7,
            kappa_interface=0.75,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        yrsn_dict = to_yrsn_dict(cert)
        restored = from_yrsn_dict(yrsn_dict)

        assert restored.kappa_H == cert.kappa_H
        assert restored.kappa_L == cert.kappa_L
        assert restored.kappa_interface == cert.kappa_interface

    def test_extract_hierarchy(self):
        cert = RSCTCertificate(
            id="test",
            timestamp="2024-01-01T00:00:00Z",
            R=0.6, S=0.3, N=0.1,
            kappa_gate=0.65,
            sigma=0.3,
            kappa_H=0.8,
            kappa_L=0.65,
            decision=GateDecision.EXECUTE,
            gate_reached=5,
            reason="test",
        )
        hierarchy = extract_hierarchy(cert)
        assert hierarchy.is_multimodal is True
        assert hierarchy.kappa_gate == 0.65
        assert hierarchy.hierarchy_gap == 0.15
        assert hierarchy.dominant_modality == "H"
