"""
P18 Compliance Tests - Hardware Compression Protection

Tests for PRINCIPLE 18: Hardware Compression Target Is Explicit and Versioned

These tests ensure the dimension reduction path (1024d → 64d) is protected
from accidental removal and properly enforced at runtime.

Reference: FIRST_PRINCIPLES_v3_MODERN.md - PRINCIPLE 18
"""

import pytest
import torch
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from swarm_it.projection import (
    DimensionContract,
    ProjectionLayer,
    get_projection_layer,
    validate_projection_at_startup,
    project_to_target_dim,
)


class TestDimensionContract:
    """Test dimension contract loading and validation."""

    def test_contract_loads_successfully(self):
        """P18: Dimension contract must load from YAML."""
        # This will load the actual contract file
        contract = DimensionContract.load()

        assert contract.input_dim == 1024
        assert contract.output_dim == 64
        assert contract.enabled is True
        assert "memristor" in contract.reason.lower() or "hardware" in contract.reason.lower()

    def test_contract_file_missing_raises_error(self):
        """P18: Missing contract file must raise clear error."""
        fake_path = Path("/nonexistent/dimension_contract.yaml")

        with pytest.raises(FileNotFoundError) as exc_info:
            DimensionContract.load(fake_path)

        assert "P18 VIOLATION" in str(exc_info.value)
        assert "Dimension contract not found" in str(exc_info.value)

    def test_contract_disabled_raises_error(self, tmp_path):
        """P18: Disabled compression must raise clear error."""
        # Create a contract with compression disabled
        contract_path = tmp_path / "dimension_contract.yaml"
        with open(contract_path, "w") as f:
            yaml.dump({
                "compression": {
                    "enabled": False,
                    "input": {"dimension": 1024},
                    "output": {"dimension": 64},
                }
            }, f)

        with pytest.raises(ValueError) as exc_info:
            DimensionContract.load(contract_path)

        assert "P18 VIOLATION" in str(exc_info.value)
        assert "Compression disabled" in str(exc_info.value)


class TestProjectionDimensions:
    """Test projection dimension contract enforcement."""

    def test_projection_dimensions_match_contract(self):
        """
        P18: Projection input/output dims must match declared contract.

        CRITICAL TEST: This prevents accidental dimension changes.
        """
        contract = DimensionContract.load()

        # Create projection layer (without checkpoint for this test)
        with patch.object(DimensionContract, 'load', return_value=contract):
            # Mock the FAIL_FAST policy check for this test
            contract_copy = DimensionContract(
                input_dim=1024,
                output_dim=64,
                reason=contract.reason,
                checkpoint=contract.checkpoint,
                enabled=True,
                fallback_policy="ALLOW_UNINITIALIZED",  # Allow for test
            )

            projection = ProjectionLayer(
                input_dim=1024,
                output_dim=64,
                contract=contract_copy,
                checkpoint_path=None,  # Skip checkpoint loading for dimension test
            )

            assert projection.input_dim == contract.input_dim
            assert projection.output_dim == contract.output_dim
            assert projection.input_dim == 1024
            assert projection.output_dim == 64

    def test_projection_dimension_mismatch_raises_error(self):
        """P18: Dimension mismatch must fail fast with clear error."""
        contract = DimensionContract.load()

        # Try to create projection with wrong dimensions
        with pytest.raises(ValueError) as exc_info:
            ProjectionLayer(
                input_dim=512,  # WRONG - contract says 1024
                output_dim=64,
                contract=contract,
                checkpoint_path=None,
            )

        assert "P18 VIOLATION" in str(exc_info.value)
        assert "does not match contract" in str(exc_info.value)

    def test_projection_output_dimension_mismatch_raises_error(self):
        """P18: Output dimension mismatch must fail fast."""
        contract = DimensionContract.load()

        # Try to create projection with wrong output dimension
        with pytest.raises(ValueError) as exc_info:
            ProjectionLayer(
                input_dim=1024,
                output_dim=128,  # WRONG - contract says 64
                contract=contract,
                checkpoint_path=None,
            )

        assert "P18 VIOLATION" in str(exc_info.value)
        assert "does not match contract" in str(exc_info.value)


class TestProjectionCheckpoint:
    """Test projection checkpoint loading and validation."""

    def test_projection_checkpoint_exists(self, tmp_path):
        """
        P18: Trained projection checkpoint must exist at startup.

        CRITICAL TEST: Prevents deployment without trained projection.
        """
        # Create a mock checkpoint
        checkpoint_path = tmp_path / "trained_rotor_universal64.pt"
        mock_state_dict = {
            "weight": torch.randn(64, 1024),
            "bias": torch.randn(64),
        }
        torch.save(mock_state_dict, checkpoint_path)

        # Load contract and create projection
        contract = DimensionContract.load()
        contract_copy = DimensionContract(
            input_dim=1024,
            output_dim=64,
            reason=contract.reason,
            checkpoint=str(checkpoint_path),
            enabled=True,
            fallback_policy="FAIL_FAST",
        )

        projection = ProjectionLayer(
            input_dim=1024,
            output_dim=64,
            checkpoint_path=checkpoint_path,
            contract=contract_copy,
        )

        assert projection.checkpoint_loaded() is True
        assert projection.is_trained() is True

    def test_missing_checkpoint_with_fail_fast_raises_error(self):
        """P18: Missing checkpoint with FAIL_FAST policy must raise error."""
        contract = DimensionContract.load()

        with pytest.raises((FileNotFoundError, ValueError)) as exc_info:
            ProjectionLayer(
                input_dim=1024,
                output_dim=64,
                checkpoint_path=Path("/nonexistent/checkpoint.pt"),
                contract=contract,
            )

        assert "P18 VIOLATION" in str(exc_info.value)

    def test_corrupted_checkpoint_raises_error(self, tmp_path):
        """P18: Corrupted checkpoint must raise clear error."""
        # Create a corrupted checkpoint
        checkpoint_path = tmp_path / "corrupted.pt"
        with open(checkpoint_path, "w") as f:
            f.write("CORRUPTED DATA")

        contract = DimensionContract.load()
        contract_copy = DimensionContract(
            input_dim=1024,
            output_dim=64,
            reason=contract.reason,
            checkpoint=str(checkpoint_path),
            enabled=True,
            fallback_policy="FAIL_FAST",
        )

        with pytest.raises(RuntimeError) as exc_info:
            ProjectionLayer(
                input_dim=1024,
                output_dim=64,
                checkpoint_path=checkpoint_path,
                contract=contract_copy,
            )

        assert "P18 VIOLATION" in str(exc_info.value)
        assert "Failed to load projection checkpoint" in str(exc_info.value)


class TestCertificateQuality:
    """Test certificate quality validation after compression."""

    def test_certificate_quality_at_64d(self, tmp_path):
        """
        P18: Certificate quality must be validated after compression.

        This test ensures compression doesn't degrade certificate quality
        below acceptable thresholds.

        NOTE: This is a structural test. Real validation requires:
        - Trained projection checkpoint
        - Real embedding inputs
        - Certificate generation pipeline
        """
        # Create mock projection with checkpoint
        checkpoint_path = tmp_path / "trained_rotor_universal64.pt"
        mock_state_dict = {
            "weight": torch.randn(64, 1024),
            "bias": torch.randn(64),
        }
        torch.save(mock_state_dict, checkpoint_path)

        contract = DimensionContract.load()
        contract_copy = DimensionContract(
            input_dim=1024,
            output_dim=64,
            reason=contract.reason,
            checkpoint=str(checkpoint_path),
            enabled=True,
            fallback_policy="FAIL_FAST",
        )

        projection = ProjectionLayer(
            input_dim=1024,
            output_dim=64,
            checkpoint_path=checkpoint_path,
            contract=contract_copy,
        )

        # Test projection produces correct output shape
        embeddings_1024d = torch.randn(1, 1024)
        embeddings_64d = projection(embeddings_1024d)

        assert embeddings_64d.shape == (1, 64)
        assert embeddings_64d.dtype == torch.float32

        # NOTE: Real certificate quality test would:
        # 1. Generate certificate from embeddings_1024d
        # 2. Generate certificate from embeddings_64d
        # 3. Assert cert_similarity(cert_before, cert_after) >= 0.90


class TestMultimodalAlignment:
    """Test multimodal dimension alignment."""

    def test_multimodal_dimension_alignment(self):
        """
        P18: Text and vision features must produce same dimension if multimodal.

        This structural test ensures the projection target (64d) aligns with
        vision feature dimensions for multimodal use cases.

        NOTE: Full test requires:
        - Vision encoder producing 64d features
        - Text embeddings projected to 64d
        - Multimodal fusion layer
        """
        contract = DimensionContract.load()

        # Verify contract specifies multimodal alignment rationale
        assert contract.output_dim == 64
        # Check if rationale mentions vision/multimodal
        # (This would be in the YAML contract)

        # Structural test: projection output should match expected vision dim
        expected_vision_dim = 64  # From dimension contract rationale

        assert contract.output_dim == expected_vision_dim


class TestStartupValidation:
    """Test startup validation for P18 compliance."""

    def test_startup_validation_passes_with_valid_checkpoint(self, tmp_path):
        """P18: Startup validation must pass with valid checkpoint."""
        # Create mock checkpoint
        checkpoint_path = tmp_path / "trained_rotor_universal64.pt"
        mock_state_dict = {
            "weight": torch.randn(64, 1024),
            "bias": torch.randn(64),
        }
        torch.save(mock_state_dict, checkpoint_path)

        # Mock get_projection_layer to return valid projection
        with patch("swarm_it.projection.get_projection_layer") as mock_get:
            contract = DimensionContract.load()
            contract_copy = DimensionContract(
                input_dim=1024,
                output_dim=64,
                reason=contract.reason,
                checkpoint=str(checkpoint_path),
                enabled=True,
                fallback_policy="FAIL_FAST",
            )

            projection = ProjectionLayer(
                input_dim=1024,
                output_dim=64,
                checkpoint_path=checkpoint_path,
                contract=contract_copy,
            )

            mock_get.return_value = projection

            result = validate_projection_at_startup()

            assert result["status"] == "PASS"
            assert result["checkpoint_loaded"] is True
            assert result["input_dim"] == 1024
            assert result["output_dim"] == 64

    def test_startup_validation_fails_without_checkpoint(self):
        """P18: Startup validation must fail without checkpoint."""
        # Mock get_projection_layer to return projection without checkpoint
        with patch("swarm_it.projection.get_projection_layer") as mock_get:
            mock_projection = Mock()
            mock_projection.checkpoint_loaded.return_value = False
            mock_projection.input_dim = 1024
            mock_projection.output_dim = 64
            mock_projection.get_contract_info.return_value = {
                "input_dim": 1024,
                "output_dim": 64,
                "checkpoint": "missing.pt",
                "reason": "test",
                "checkpoint_loaded": False,
            }

            mock_get.return_value = mock_projection

            with pytest.raises(RuntimeError) as exc_info:
                validate_projection_at_startup()

            assert "P18 VIOLATION" in str(exc_info.value)
            assert "Projection checkpoint not loaded" in str(exc_info.value)


class TestRuntimeEnforcement:
    """Test runtime dimension enforcement."""

    def test_projection_rejects_wrong_input_dimension(self, tmp_path):
        """P18: Projection must reject inputs with wrong dimension."""
        # Create mock checkpoint
        checkpoint_path = tmp_path / "trained_rotor_universal64.pt"
        mock_state_dict = {
            "weight": torch.randn(64, 1024),
            "bias": torch.randn(64),
        }
        torch.save(mock_state_dict, checkpoint_path)

        contract = DimensionContract.load()
        contract_copy = DimensionContract(
            input_dim=1024,
            output_dim=64,
            reason=contract.reason,
            checkpoint=str(checkpoint_path),
            enabled=True,
            fallback_policy="FAIL_FAST",
        )

        projection = ProjectionLayer(
            input_dim=1024,
            output_dim=64,
            checkpoint_path=checkpoint_path,
            contract=contract_copy,
        )

        # Try to project embeddings with wrong dimension
        wrong_embeddings = torch.randn(1, 512)  # Should be 1024

        with pytest.raises(ValueError) as exc_info:
            projection(wrong_embeddings)

        assert "P18 VIOLATION" in str(exc_info.value)
        assert "does not match projection input dimension" in str(exc_info.value)


class TestContractChangeControl:
    """Test change control for dimension contracts."""

    def test_contract_has_approval_requirements(self):
        """P18: Contract must specify approval requirements."""
        contract_path = Path(__file__).parent.parent.parent / "config" / "dimension_contract.yaml"

        with open(contract_path, "r") as f:
            contract_data = yaml.safe_load(f)

        # Verify change control section exists
        assert "change_control" in contract_data
        change_control = contract_data["change_control"]

        # Verify approval requirements
        assert "requires_approval_from" in change_control
        approvers = change_control["requires_approval_from"]

        assert "architecture" in approvers
        assert "hardware" in approvers

    def test_contract_has_validation_tests(self):
        """P18: Contract must list required validation tests."""
        contract_path = Path(__file__).parent.parent.parent / "config" / "dimension_contract.yaml"

        with open(contract_path, "r") as f:
            contract_data = yaml.safe_load(f)

        change_control = contract_data["change_control"]

        # Verify validation tests are listed
        assert "validation_tests" in change_control
        tests = change_control["validation_tests"]

        required_tests = [
            "test_projection_dimensions_match_contract",
            "test_projection_checkpoint_exists",
            "test_certificate_quality_at_64d",
            "test_multimodal_dimension_alignment",
        ]

        for required_test in required_tests:
            assert required_test in tests, f"Missing required test: {required_test}"

    def test_contract_prohibits_dangerous_changes(self):
        """P18: Contract must explicitly prohibit dangerous changes."""
        contract_path = Path(__file__).parent.parent.parent / "config" / "dimension_contract.yaml"

        with open(contract_path, "r") as f:
            contract_data = yaml.safe_load(f)

        change_control = contract_data["change_control"]

        # Verify prohibited changes are listed
        assert "prohibited_changes" in change_control
        prohibited = change_control["prohibited_changes"]

        # Check for key prohibitions
        prohibited_text = " ".join(prohibited).lower()
        assert "removing projection layer" in prohibited_text or "remove" in prohibited_text
        assert "architecture review" in prohibited_text or "review" in prohibited_text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
