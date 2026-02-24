"""Tests for REST API."""

import pytest
from fastapi.testclient import TestClient

# Import with path manipulation for standalone testing
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health endpoints."""

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_ready(self, client):
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


class TestCertifyEndpoint:
    """Tests for /api/v1/certify."""

    def test_certify_basic(self, client):
        response = client.post(
            "/api/v1/certify",
            json={"prompt": "What is 2+2?"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert "R" in data
        assert "S" in data
        assert "N" in data
        assert "kappa_gate" in data
        assert "decision" in data
        assert "allowed" in data

    def test_certify_with_context(self, client):
        response = client.post(
            "/api/v1/certify",
            json={
                "prompt": "Summarize this",
                "context": "Long document about AI safety...",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["S"] > 0  # Should have support from context

    def test_certify_with_model_id(self, client):
        response = client.post(
            "/api/v1/certify",
            json={
                "prompt": "Test",
                "model_id": "gpt-4",
            },
        )

        assert response.status_code == 200

    def test_certify_empty_prompt_fails(self, client):
        response = client.post(
            "/api/v1/certify",
            json={},
        )

        assert response.status_code == 422  # Validation error


class TestValidateEndpoint:
    """Tests for /api/v1/validate."""

    def test_validate_existing_cert(self, client):
        # First create a certificate
        cert_response = client.post(
            "/api/v1/certify",
            json={"prompt": "Test"},
        )
        cert_id = cert_response.json()["id"]

        # Then validate it
        response = client.post(
            "/api/v1/validate",
            json={
                "certificate_id": cert_id,
                "validation_type": "TYPE_I",
                "score": 0.9,
                "failed": False,
            },
        )

        assert response.status_code == 200
        assert response.json()["recorded"] is True

    def test_validate_nonexistent_cert(self, client):
        response = client.post(
            "/api/v1/validate",
            json={
                "certificate_id": "nonexistent-id",
                "validation_type": "TYPE_I",
                "score": 0.9,
                "failed": False,
            },
        )

        assert response.status_code == 404

    def test_validate_all_types(self, client):
        # Create certificate
        cert_response = client.post(
            "/api/v1/certify",
            json={"prompt": "Test"},
        )
        cert_id = cert_response.json()["id"]

        # Test all validation types
        for vtype in ["TYPE_I", "TYPE_II", "TYPE_III", "TYPE_IV", "TYPE_V", "TYPE_VI"]:
            response = client.post(
                "/api/v1/validate",
                json={
                    "certificate_id": cert_id,
                    "validation_type": vtype,
                    "score": 0.5,
                    "failed": False,
                },
            )
            assert response.status_code == 200


class TestAuditEndpoint:
    """Tests for /api/v1/audit."""

    def test_audit_empty(self, client):
        response = client.post(
            "/api/v1/audit",
            json={"format": "JSON", "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert "certificate_count" in data
        assert "records" in data

    def test_audit_after_certifications(self, client):
        # Create some certificates
        for i in range(3):
            client.post(
                "/api/v1/certify",
                json={"prompt": f"Test prompt {i}"},
            )

        # Audit
        response = client.post(
            "/api/v1/audit",
            json={"format": "JSON", "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["certificate_count"] >= 3

    def test_audit_sr117_format(self, client):
        # Create a certificate
        client.post(
            "/api/v1/certify",
            json={"prompt": "Test"},
        )

        # Audit in SR 11-7 format
        response = client.post(
            "/api/v1/audit",
            json={"format": "SR11-7", "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "SR11-7"

        if data["certificate_count"] > 0:
            record = data["records"][0]
            assert "record_type" in record
            assert "quantitative_metrics" in record


class TestStatisticsEndpoint:
    """Tests for /api/v1/statistics."""

    def test_statistics(self, client):
        response = client.get("/api/v1/statistics")

        assert response.status_code == 200
        data = response.json()

        assert "total_certificates" in data
        assert "thresholds" in data
        assert "failure_rates" in data


class TestCertificateRetrieval:
    """Tests for GET /api/v1/certificates/{id}."""

    def test_get_certificate(self, client):
        # Create certificate
        cert_response = client.post(
            "/api/v1/certify",
            json={"prompt": "Test"},
        )
        cert_id = cert_response.json()["id"]

        # Retrieve it
        response = client.get(f"/api/v1/certificates/{cert_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cert_id

    def test_get_nonexistent_certificate(self, client):
        response = client.get("/api/v1/certificates/nonexistent")

        assert response.status_code == 404
