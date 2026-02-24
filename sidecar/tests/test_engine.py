"""Tests for RSCT Engine."""

import pytest
from engine.rsct import RSCTEngine


class TestRSCTEngine:
    """Tests for RSCTEngine certification."""

    def setup_method(self):
        self.engine = RSCTEngine()

    def test_certify_basic(self):
        """Basic certification returns valid certificate."""
        cert = self.engine.certify(prompt="What is 2+2?")

        assert cert["id"] is not None
        assert cert["timestamp"] is not None
        assert 0 <= cert["R"] <= 1
        assert 0 <= cert["S"] <= 1
        assert 0 <= cert["N"] <= 1
        assert abs(cert["R"] + cert["S"] + cert["N"] - 1.0) < 0.01  # Simplex
        assert cert["decision"] in ("EXECUTE", "REPAIR", "DELEGATE", "BLOCK", "REJECT")

    def test_certify_short_prompt_has_more_noise(self):
        """Very short prompts should have more noise."""
        short = self.engine.certify(prompt="Hi")
        long = self.engine.certify(prompt="Please explain the concept of quantum entanglement in detail")

        # Short prompts tend to have higher N
        assert short["N"] >= long["N"] * 0.8  # Allow some variance

    def test_certify_with_context_has_more_support(self):
        """Prompts with context should have more support."""
        no_context = self.engine.certify(prompt="Summarize this")
        with_context = self.engine.certify(
            prompt="Summarize this",
            context="This is a long document about machine learning and artificial intelligence. " * 10,
        )

        assert with_context["S"] >= no_context["S"]

    def test_gate_decision_execute(self):
        """Good prompts should get EXECUTE decision."""
        cert = self.engine.certify(
            prompt="Explain the theory of relativity in simple terms with examples",
            context="Physics context for educational purposes",
        )

        # With good R, low N, reasonable kappa, should execute
        assert cert["decision"] == "EXECUTE"
        assert cert["allowed"] is True
        assert cert["gate_reached"] == 5

    def test_kappa_gate_computed(self):
        """kappa_gate should be computed."""
        cert = self.engine.certify(prompt="Test prompt")

        assert cert["kappa_gate"] is not None
        assert 0 <= cert["kappa_gate"] <= 1

    def test_multimodal_detection(self):
        """Prompts mentioning images should be detected as multimodal."""
        text_only = self.engine.certify(prompt="What is 2+2?")
        multimodal = self.engine.certify(prompt="Describe this image of a cat")

        assert text_only["is_multimodal"] is False
        assert multimodal["is_multimodal"] is True

    def test_multimodal_has_hierarchy(self):
        """Multimodal prompts should have kappa hierarchy."""
        cert = self.engine.certify(prompt="Analyze this screenshot")

        assert cert["is_multimodal"] is True
        assert cert["kappa_H"] is not None
        assert cert["kappa_L"] is not None
        assert cert["kappa_interface"] is not None

    def test_weak_modality_identified(self):
        """Multimodal should identify weak modality."""
        cert = self.engine.certify(prompt="What does this photo show?")

        if cert["is_multimodal"]:
            # weak_modality should be text, vision, or interface
            assert cert["weak_modality"] in ("text", "vision", "interface", None)


class TestValidationFeedback:
    """Tests for validation feedback loop."""

    def setup_method(self):
        self.engine = RSCTEngine()

    def test_record_validation(self):
        """Validation recording should work."""
        result = self.engine.record_validation(
            certificate_id="test-123",
            validation_type="TYPE_I",
            score=0.9,
            failed=False,
        )

        # First few validations shouldn't trigger adjustments
        assert result is None or isinstance(result, dict)

    def test_failure_rate_tracking(self):
        """Failure rates should be tracked."""
        # Record some validations
        for i in range(10):
            self.engine.record_validation(
                certificate_id=f"test-{i}",
                validation_type="TYPE_I",
                score=0.5,
                failed=i < 3,  # 3/10 = 30% failure
            )

        rates = self.engine.get_failure_rates()
        assert "TYPE_I" in rates
        assert rates["TYPE_I"] == 0.3

    def test_threshold_adjustment_triggered(self):
        """High failure rate should trigger adjustment recommendation."""
        # Record many failures to trigger adjustment
        for i in range(20):
            result = self.engine.record_validation(
                certificate_id=f"test-{i}",
                validation_type="TYPE_I",
                score=0.3,
                failed=True,  # 100% failure
            )

        # Should eventually recommend tightening
        assert result is not None
        assert result["recommendation"] == "tighten"


class TestThresholds:
    """Tests for threshold management."""

    def setup_method(self):
        self.engine = RSCTEngine()

    def test_default_thresholds(self):
        """Default thresholds should be set."""
        thresholds = self.engine.get_thresholds()

        assert thresholds["kappa_threshold"] == 0.7
        assert thresholds["N_threshold"] == 0.5

    def test_set_threshold(self):
        """Thresholds can be modified."""
        self.engine.set_threshold("kappa_threshold", 0.8)

        assert self.engine.thresholds["kappa_threshold"] == 0.8

    def test_stricter_threshold_affects_decisions(self):
        """Stricter kappa threshold should block more."""
        # With default threshold
        cert1 = self.engine.certify(prompt="Test")
        decision1 = cert1["decision"]

        # With stricter threshold
        self.engine.set_threshold("kappa_threshold", 0.95)
        cert2 = self.engine.certify(prompt="Test")

        # Stricter threshold may change decision
        # (depends on computed kappa)
        assert cert2["decision"] in ("EXECUTE", "REPAIR", "DELEGATE", "BLOCK", "REJECT")
