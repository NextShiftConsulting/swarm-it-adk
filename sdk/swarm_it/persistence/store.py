"""
Certificate Storage

Abstract interface and implementations for certificate persistence.
"""

import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Iterator
from collections import OrderedDict

from ..local.engine import RSCTCertificate


class CertificateStore(ABC):
    """
    Abstract base class for certificate storage.

    Implementations must provide:
    - store(cert): Persist a certificate
    - get(cert_id): Retrieve by ID
    - list(filter): List certificates with optional filter
    - delete(cert_id): Remove a certificate
    """

    @abstractmethod
    def store(self, cert: RSCTCertificate) -> str:
        """
        Store a certificate.

        Args:
            cert: Certificate to store

        Returns:
            Certificate ID
        """
        pass

    @abstractmethod
    def get(self, cert_id: str) -> Optional[RSCTCertificate]:
        """
        Retrieve a certificate by ID.

        Args:
            cert_id: Certificate ID

        Returns:
            Certificate or None if not found
        """
        pass

    @abstractmethod
    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        policy: Optional[str] = None,
        decision: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[RSCTCertificate]:
        """
        List certificates with optional filtering.

        Args:
            limit: Maximum number to return
            offset: Number to skip
            policy: Filter by policy name
            decision: Filter by gate decision
            since: Filter by timestamp >= since
            until: Filter by timestamp <= until

        Returns:
            List of certificates
        """
        pass

    @abstractmethod
    def delete(self, cert_id: str) -> bool:
        """
        Delete a certificate.

        Args:
            cert_id: Certificate ID

        Returns:
            True if deleted, False if not found
        """
        pass

    def count(self) -> int:
        """Get total number of stored certificates."""
        return len(self.list(limit=1000000))

    def exists(self, cert_id: str) -> bool:
        """Check if a certificate exists."""
        return self.get(cert_id) is not None


class MemoryStore(CertificateStore):
    """
    In-memory certificate store.

    Good for:
    - Development and testing
    - Short-lived processes
    - Caching layer

    Not suitable for:
    - Production persistence
    - Multi-process access
    """

    def __init__(self, max_size: int = 10000):
        """
        Initialize memory store.

        Args:
            max_size: Maximum certificates to store (LRU eviction)
        """
        self.max_size = max_size
        self._store: OrderedDict[str, RSCTCertificate] = OrderedDict()

    def store(self, cert: RSCTCertificate) -> str:
        """Store certificate in memory."""
        # LRU eviction
        while len(self._store) >= self.max_size:
            self._store.popitem(last=False)

        self._store[cert.id] = cert
        self._store.move_to_end(cert.id)
        return cert.id

    def get(self, cert_id: str) -> Optional[RSCTCertificate]:
        """Get certificate from memory."""
        cert = self._store.get(cert_id)
        if cert:
            self._store.move_to_end(cert_id)
        return cert

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        policy: Optional[str] = None,
        decision: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[RSCTCertificate]:
        """List certificates with filtering."""
        results = []

        for cert in self._store.values():
            # Apply filters
            if policy and cert.policy != policy:
                continue
            if decision and cert.decision.value != decision:
                continue
            if since and cert.timestamp < since:
                continue
            if until and cert.timestamp > until:
                continue
            results.append(cert)

        # Apply pagination
        return results[offset:offset + limit]

    def delete(self, cert_id: str) -> bool:
        """Delete certificate from memory."""
        if cert_id in self._store:
            del self._store[cert_id]
            return True
        return False

    def count(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        """Clear all certificates."""
        self._store.clear()


class SQLiteStore(CertificateStore):
    """
    SQLite-based certificate store.

    Good for:
    - Local development with persistence
    - Single-process applications
    - Lightweight deployment

    Not suitable for:
    - Multi-process concurrent access
    - High-throughput production
    """

    def __init__(self, db_path: str = "certificates.db"):
        """
        Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                policy TEXT NOT NULL,
                decision TEXT NOT NULL,
                gate_reached INTEGER NOT NULL,
                R REAL NOT NULL,
                S REAL NOT NULL,
                N REAL NOT NULL,
                kappa_gate REAL NOT NULL,
                sigma REAL NOT NULL,
                reason TEXT,
                data TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON certificates(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_policy ON certificates(policy)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decision ON certificates(decision)
        """)
        conn.commit()
        conn.close()

    def store(self, cert: RSCTCertificate) -> str:
        """Store certificate in SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO certificates
            (id, timestamp, policy, decision, gate_reached, R, S, N, kappa_gate, sigma, reason, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cert.id,
                cert.timestamp,
                cert.policy,
                cert.decision.value,
                cert.gate_reached,
                cert.R,
                cert.S,
                cert.N,
                cert.kappa_gate,
                cert.sigma,
                cert.reason,
                json.dumps(cert.to_dict()),
            )
        )
        conn.commit()
        conn.close()
        return cert.id

    def get(self, cert_id: str) -> Optional[RSCTCertificate]:
        """Get certificate from SQLite."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT data FROM certificates WHERE id = ?",
            (cert_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return RSCTCertificate.from_dict(json.loads(row[0]))
        return None

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        policy: Optional[str] = None,
        decision: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[RSCTCertificate]:
        """List certificates with filtering."""
        query = "SELECT data FROM certificates WHERE 1=1"
        params = []

        if policy:
            query += " AND policy = ?"
            params.append(policy)
        if decision:
            query += " AND decision = ?"
            params.append(decision)
        if since:
            query += " AND timestamp >= ?"
            params.append(since)
        if until:
            query += " AND timestamp <= ?"
            params.append(until)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [RSCTCertificate.from_dict(json.loads(row[0])) for row in rows]

    def delete(self, cert_id: str) -> bool:
        """Delete certificate from SQLite."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "DELETE FROM certificates WHERE id = ?",
            (cert_id,)
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def count(self) -> int:
        """Get total certificate count."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM certificates")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def vacuum(self) -> None:
        """Optimize database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("VACUUM")
        conn.close()

    def export_all(self) -> Iterator[Dict[str, Any]]:
        """Export all certificates as dicts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT data FROM certificates ORDER BY timestamp")
        for row in cursor:
            yield json.loads(row[0])
        conn.close()
