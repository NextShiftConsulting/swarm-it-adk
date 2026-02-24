"""Tests for certificate store."""

import pytest
import tempfile
import os

from store.certificates import MemoryCertificateStore, SQLiteCertificateStore


def make_cert(id: str = "test-123") -> dict:
    """Create a test certificate."""
    return {
        "id": id,
        "timestamp": "2026-02-24T12:00:00Z",
        "R": 0.6,
        "S": 0.3,
        "N": 0.1,
        "kappa_gate": 0.7,
        "sigma": 0.3,
        "decision": "EXECUTE",
        "gate_reached": 5,
        "reason": "test",
        "allowed": True,
    }


class TestMemoryStore:
    """Tests for MemoryCertificateStore."""

    def test_store_and_get(self):
        store = MemoryCertificateStore()
        cert = make_cert()

        store.store(cert)
        retrieved = store.get("test-123")

        assert retrieved is not None
        assert retrieved["id"] == "test-123"

    def test_get_nonexistent(self):
        store = MemoryCertificateStore()

        assert store.get("nonexistent") is None

    def test_list(self):
        store = MemoryCertificateStore()

        for i in range(5):
            store.store(make_cert(id=f"cert-{i}"))

        certs = store.list()
        assert len(certs) == 5

    def test_list_with_limit(self):
        store = MemoryCertificateStore()

        for i in range(10):
            store.store(make_cert(id=f"cert-{i}"))

        certs = store.list(limit=5)
        assert len(certs) == 5

    def test_count(self):
        store = MemoryCertificateStore()

        assert store.count() == 0

        store.store(make_cert(id="1"))
        store.store(make_cert(id="2"))

        assert store.count() == 2

    def test_delete(self):
        store = MemoryCertificateStore()
        store.store(make_cert())

        assert store.delete("test-123") is True
        assert store.get("test-123") is None
        assert store.delete("test-123") is False  # Already deleted

    def test_lru_eviction(self):
        store = MemoryCertificateStore(max_size=3)

        store.store(make_cert(id="1"))
        store.store(make_cert(id="2"))
        store.store(make_cert(id="3"))
        store.store(make_cert(id="4"))  # Evicts "1"

        assert store.get("1") is None
        assert store.get("4") is not None

    def test_clear(self):
        store = MemoryCertificateStore()
        store.store(make_cert())

        store.clear()

        assert store.count() == 0


class TestSQLiteStore:
    """Tests for SQLiteCertificateStore."""

    @pytest.fixture
    def db_path(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        os.unlink(path)

    def test_store_and_get(self, db_path):
        store = SQLiteCertificateStore(db_path)
        cert = make_cert()

        store.store(cert)
        retrieved = store.get("test-123")

        assert retrieved is not None
        assert retrieved["R"] == 0.6

    def test_get_nonexistent(self, db_path):
        store = SQLiteCertificateStore(db_path)

        assert store.get("nonexistent") is None

    def test_list(self, db_path):
        store = SQLiteCertificateStore(db_path)

        for i in range(5):
            store.store(make_cert(id=f"cert-{i}"))

        certs = store.list()
        assert len(certs) == 5

    def test_count(self, db_path):
        store = SQLiteCertificateStore(db_path)

        assert store.count() == 0

        store.store(make_cert(id="1"))
        store.store(make_cert(id="2"))

        assert store.count() == 2

    def test_delete(self, db_path):
        store = SQLiteCertificateStore(db_path)
        store.store(make_cert())

        assert store.delete("test-123") is True
        assert store.get("test-123") is None

    def test_persistence(self, db_path):
        # Write with one instance
        store1 = SQLiteCertificateStore(db_path)
        store1.store(make_cert())

        # Read with another instance
        store2 = SQLiteCertificateStore(db_path)
        retrieved = store2.get("test-123")

        assert retrieved is not None
