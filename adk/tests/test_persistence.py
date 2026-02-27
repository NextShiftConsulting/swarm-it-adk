"""Tests for certificate persistence."""

import os
import tempfile
import pytest
from swarm_it.local.engine import RSCTCertificate, GateDecision
from swarm_it.persistence.store import (
    MemoryStore,
    SQLiteStore,
)
from swarm_it.persistence.audit import (
    AuditLog,
    AuditEntry,
    SR117AuditFormatter,
)


def create_test_certificate(
    id: str = "test-123",
    R: float = 0.6,
    S: float = 0.3,
    N: float = 0.1,
) -> RSCTCertificate:
    return RSCTCertificate(
        id=id,
        timestamp="2024-01-01T00:00:00Z",
        R=R, S=S, N=N,
        kappa_gate=0.7,
        sigma=0.3,
        decision=GateDecision.EXECUTE,
        gate_reached=5,
        reason="test",
    )


class TestMemoryStore:
    """Tests for in-memory certificate store."""

    def test_store_and_get(self):
        store = MemoryStore()
        cert = create_test_certificate()
        store.store(cert)

        retrieved = store.get(cert.id)
        assert retrieved is not None
        assert retrieved.id == cert.id

    def test_get_nonexistent(self):
        store = MemoryStore()
        assert store.get("nonexistent") is None

    def test_list_all(self):
        store = MemoryStore()
        for i in range(5):
            store.store(create_test_certificate(id=f"cert-{i}"))

        certs = store.list()
        assert len(certs) == 5

    def test_list_with_limit(self):
        store = MemoryStore()
        for i in range(10):
            store.store(create_test_certificate(id=f"cert-{i}"))

        certs = store.list(limit=5)
        assert len(certs) == 5

    def test_list_with_offset(self):
        store = MemoryStore()
        for i in range(10):
            store.store(create_test_certificate(id=f"cert-{i}"))

        certs = store.list(limit=5, offset=5)
        assert len(certs) == 5

    def test_delete(self):
        store = MemoryStore()
        cert = create_test_certificate()
        store.store(cert)

        assert store.delete(cert.id) is True
        assert store.get(cert.id) is None
        assert store.delete(cert.id) is False  # Already deleted

    def test_count(self):
        store = MemoryStore()
        assert store.count() == 0

        store.store(create_test_certificate(id="1"))
        store.store(create_test_certificate(id="2"))
        assert store.count() == 2

    def test_lru_eviction(self):
        store = MemoryStore(max_size=3)
        store.store(create_test_certificate(id="1"))
        store.store(create_test_certificate(id="2"))
        store.store(create_test_certificate(id="3"))
        store.store(create_test_certificate(id="4"))  # Evicts "1"

        assert store.get("1") is None
        assert store.get("4") is not None

    def test_clear(self):
        store = MemoryStore()
        store.store(create_test_certificate())
        store.clear()
        assert store.count() == 0


class TestSQLiteStore:
    """Tests for SQLite certificate store."""

    @pytest.fixture
    def db_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    def test_store_and_get(self, db_path):
        store = SQLiteStore(db_path)
        cert = create_test_certificate()
        store.store(cert)

        retrieved = store.get(cert.id)
        assert retrieved is not None
        assert retrieved.R == cert.R

    def test_get_nonexistent(self, db_path):
        store = SQLiteStore(db_path)
        assert store.get("nonexistent") is None

    def test_list_with_policy_filter(self, db_path):
        store = SQLiteStore(db_path)

        cert1 = create_test_certificate(id="1")
        cert1.policy = "strict"
        store.store(cert1)

        cert2 = create_test_certificate(id="2")
        cert2.policy = "lenient"
        store.store(cert2)

        strict = store.list(policy="strict")
        assert len(strict) == 1
        assert strict[0].policy == "strict"

    def test_delete(self, db_path):
        store = SQLiteStore(db_path)
        cert = create_test_certificate()
        store.store(cert)

        assert store.delete(cert.id) is True
        assert store.get(cert.id) is None

    def test_count(self, db_path):
        store = SQLiteStore(db_path)
        assert store.count() == 0

        store.store(create_test_certificate(id="1"))
        store.store(create_test_certificate(id="2"))
        assert store.count() == 2


class TestAuditEntry:
    """Tests for AuditEntry."""

    def test_from_certificate(self):
        cert = create_test_certificate()
        entry = AuditEntry.from_certificate(cert)

        assert entry.certificate_id == cert.id
        assert entry.kappa_gate == cert.kappa_gate
        assert entry.outcome == "EXECUTE"

    def test_to_sr117_format(self):
        cert = create_test_certificate()
        entry = AuditEntry.from_certificate(cert)
        sr117 = entry.to_sr117_format()

        assert "model_id" in sr117
        assert "quality_metrics" in sr117
        assert "gate_outcome" in sr117


class TestAuditLog:
    """Tests for AuditLog."""

    def test_log_entry(self):
        log = AuditLog()
        cert = create_test_certificate()
        entry = log.log(cert)

        assert entry.certificate_id == cert.id
        assert log.count() == 1

    def test_get_entries(self):
        log = AuditLog()
        for i in range(5):
            log.log(create_test_certificate(id=f"cert-{i}"))

        entries = log.get_entries(limit=3)
        assert len(entries) == 3

    def test_log_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            log = AuditLog(output_path=path, buffer_size=2)
            log.log(create_test_certificate(id="1"))
            log.log(create_test_certificate(id="2"))  # Triggers flush
            log.close()

            with open(path) as f:
                lines = f.readlines()
            assert len(lines) >= 2
        finally:
            os.unlink(path)


class TestSR117Formatter:
    """Tests for SR 11-7 audit formatter."""

    def test_format_validation_record(self):
        cert = create_test_certificate()
        record = SR117AuditFormatter.format_validation_record(cert)

        assert record["record_type"] == "MODEL_VALIDATION"
        assert "quantitative_metrics" in record
        assert "risk_indicators" in record
        assert "compliance_assertions" in record

    def test_generate_batch_report(self):
        certs = [create_test_certificate(id=f"cert-{i}") for i in range(5)]
        report = SR117AuditFormatter.generate_batch_report(certs, "Test Report")

        assert report["report_type"] == "SR11-7_BATCH_VALIDATION"
        assert report["summary"]["total_validations"] == 5
        assert len(report["individual_records"]) == 5

    def test_risk_level_computation(self):
        # High noise = critical
        high_noise = create_test_certificate(R=0.2, S=0.2, N=0.6)
        record = SR117AuditFormatter.format_validation_record(high_noise)
        assert record["risk_indicators"]["overall_risk"] == "CRITICAL"

        # Healthy = low
        healthy = create_test_certificate(R=0.7, S=0.2, N=0.1)
        record = SR117AuditFormatter.format_validation_record(healthy)
        assert record["risk_indicators"]["overall_risk"] == "LOW"
