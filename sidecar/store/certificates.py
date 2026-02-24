"""
Certificate Store - Persistence layer for certificates.

Supports in-memory (default) and SQLite backends.
"""

import json
import os
import sqlite3
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime
from typing import Dict, Any, Optional, List


class CertificateStore(ABC):
    """Abstract certificate store interface."""

    def __new__(cls, *args, **kwargs):
        """Factory to select backend based on environment."""
        if cls is CertificateStore:
            db_path = os.environ.get("SWARM_IT_DB_PATH")
            if db_path:
                return super().__new__(SQLiteCertificateStore)
            return super().__new__(MemoryCertificateStore)
        return super().__new__(cls)

    @abstractmethod
    def store(self, cert: Dict[str, Any]) -> None:
        """Store a certificate."""
        pass

    @abstractmethod
    def get(self, cert_id: str) -> Optional[Dict[str, Any]]:
        """Get a certificate by ID."""
        pass

    @abstractmethod
    def list(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List certificates."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Count total certificates."""
        pass

    @abstractmethod
    def delete(self, cert_id: str) -> bool:
        """Delete a certificate."""
        pass


class MemoryCertificateStore(CertificateStore):
    """In-memory certificate store with LRU eviction."""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    def store(self, cert: Dict[str, Any]) -> None:
        cert_id = cert.get("id")
        if not cert_id:
            raise ValueError("Certificate must have 'id' field")

        # LRU eviction
        if len(self._store) >= self.max_size:
            self._store.popitem(last=False)

        self._store[cert_id] = cert
        self._store.move_to_end(cert_id)

    def get(self, cert_id: str) -> Optional[Dict[str, Any]]:
        cert = self._store.get(cert_id)
        if cert:
            self._store.move_to_end(cert_id)
        return cert

    def list(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        certs = list(self._store.values())
        return certs[offset:offset + limit]

    def count(self) -> int:
        return len(self._store)

    def delete(self, cert_id: str) -> bool:
        if cert_id in self._store:
            del self._store[cert_id]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()


class SQLiteCertificateStore(CertificateStore):
    """SQLite-backed certificate store."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("SWARM_IT_DB_PATH", "certificates.db")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS certificates (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL,
                    decision TEXT,
                    kappa_gate REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON certificates(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_decision ON certificates(decision)
            """)

    def store(self, cert: Dict[str, Any]) -> None:
        cert_id = cert.get("id")
        if not cert_id:
            raise ValueError("Certificate must have 'id' field")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO certificates (id, timestamp, data, decision, kappa_gate)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cert_id,
                    cert.get("timestamp"),
                    json.dumps(cert),
                    cert.get("decision"),
                    cert.get("kappa_gate"),
                ),
            )

    def get(self, cert_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM certificates WHERE id = ?",
                (cert_id,),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    def list(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM certificates ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            return [json.loads(row[0]) for row in cursor.fetchall()]

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM certificates")
            return cursor.fetchone()[0]

    def delete(self, cert_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM certificates WHERE id = ?",
                (cert_id,),
            )
            return cursor.rowcount > 0
