"""
Database Manager
SQLite database operations for fault signatures, analysis sessions,
and fingerprint hash storage.
"""

import sqlite3
import os
import threading
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FaultSignature:
    """Represents a known fault audio signature."""
    id: int
    name: str
    description: str
    category: str
    associated_codes: str
    created_at: str = ""


@dataclass
class AnalysisSession:
    """Represents a user analysis session."""
    id: int
    timestamp: str
    audio_path: str
    user_codes: str
    notes: str
    duration_seconds: float = 0.0


@dataclass
class MatchResult:
    """Represents a match result for a session."""
    fault_name: str
    confidence_pct: float
    trouble_codes: str
    description: str
    category: str
    signature_id: int = 0


class DatabaseManager:
    """Manages all SQLite database operations (thread-safe)."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._all_connections: list[sqlite3.Connection] = []
        self._lock = threading.Lock()

    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create a thread-local database connection."""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            self._local.connection = conn
            with self._lock:
                self._all_connections.append(conn)
        return conn

    def close(self):
        """Close all database connections across all threads."""
        with self._lock:
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        self._local = threading.local()

    def initialize(self):
        """Create tables and seed data if needed."""
        self._create_tables()
        self._seed_if_empty()
        self._seed_trouble_codes_if_empty()

    def _create_tables(self):
        """Create all database tables from the schema."""
        schema_path = Path(__file__).parent / "schema.sql"

        if schema_path.exists():
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            self.connection.executescript(schema_sql)
        else:
            # Inline fallback schema
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS fault_signatures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL CHECK(category IN ('engine', 'exhaust', 'suspension', 'belt', 'bearing', 'intake', 'electrical', 'accessory', 'drivetrain', 'hvac', 'fuel', 'transmission', 'brakes', 'cooling', 'other')),
                    associated_codes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS signature_hashes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signature_id INTEGER NOT NULL,
                    hash_value INTEGER NOT NULL,
                    time_offset REAL NOT NULL,
                    FOREIGN KEY (signature_id) REFERENCES fault_signatures(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_hash_value ON signature_hashes(hash_value);

                CREATE TABLE IF NOT EXISTS analysis_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    audio_path TEXT,
                    user_codes TEXT,
                    notes TEXT,
                    duration_seconds REAL
                );

                CREATE TABLE IF NOT EXISTS session_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    signature_id INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY (signature_id) REFERENCES fault_signatures(id) ON DELETE CASCADE
                );
            """)

        self.connection.commit()

    def _seed_if_empty(self):
        """Seed with known fault signatures if the table is empty."""
        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM fault_signatures"
        )
        count = cursor.fetchone()[0]

        if count == 0:
            from database.seed_data import get_seed_signatures
            for sig in get_seed_signatures():
                self.add_fault_signature(
                    name=sig["name"],
                    description=sig["description"],
                    category=sig["category"],
                    associated_codes=sig["associated_codes"],
                )

    def _seed_trouble_codes_if_empty(self):
        """Load trouble code definitions from JSON if the table is empty."""
        try:
            cursor = self.connection.execute(
                "SELECT COUNT(*) FROM trouble_code_definitions"
            )
            count = cursor.fetchone()[0]
        except Exception:
            # Table might not exist yet if schema failed
            return

        if count > 0:
            return

        import json
        json_path = Path(__file__).parent / "obd2_codes.json"
        if not json_path.exists():
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                codes = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        for entry in codes:
            mc = entry.get("mechanical_classes", [])
            symptoms = entry.get("symptoms", [])
            self.connection.execute(
                """INSERT OR IGNORE INTO trouble_code_definitions
                   (code, description, system, subsystem, mechanical_classes, symptoms, severity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry["code"],
                    entry["description"],
                    entry["system"],
                    entry.get("subsystem", ""),
                    ",".join(mc) if isinstance(mc, list) else str(mc),
                    ",".join(symptoms) if isinstance(symptoms, list) else str(symptoms),
                    entry.get("severity", "medium"),
                ),
            )
        self.connection.commit()

    # ---- Fault Signature Operations ----

    def add_fault_signature(
        self,
        name: str,
        description: str,
        category: str,
        associated_codes: str,
    ) -> int:
        """Add a new fault signature. Returns the new signature ID."""
        cursor = self.connection.execute(
            """INSERT INTO fault_signatures (name, description, category, associated_codes)
               VALUES (?, ?, ?, ?)""",
            (name, description, category, associated_codes),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_all_signatures(self) -> list[FaultSignature]:
        """Retrieve all fault signatures."""
        cursor = self.connection.execute(
            "SELECT * FROM fault_signatures ORDER BY category, name"
        )
        return [
            FaultSignature(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                category=row["category"],
                associated_codes=row["associated_codes"],
                created_at=row["created_at"] or "",
            )
            for row in cursor.fetchall()
        ]

    def get_signature_by_id(self, sig_id: int) -> FaultSignature | None:
        """Retrieve a specific fault signature by ID."""
        cursor = self.connection.execute(
            "SELECT * FROM fault_signatures WHERE id = ?", (sig_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return FaultSignature(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            category=row["category"],
            associated_codes=row["associated_codes"],
            created_at=row["created_at"] or "",
        )

    def get_signatures_by_code(self, code: str) -> list[FaultSignature]:
        """Find fault signatures associated with a specific trouble code."""
        cursor = self.connection.execute(
            "SELECT * FROM fault_signatures WHERE associated_codes LIKE ?",
            (f"%{code}%",),
        )
        return [
            FaultSignature(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                category=row["category"],
                associated_codes=row["associated_codes"],
                created_at=row["created_at"] or "",
            )
            for row in cursor.fetchall()
        ]

    # ---- Signature Hash Operations ----

    def add_signature_hashes(
        self,
        signature_id: int,
        hashes: list[tuple[int, float]],
    ):
        """
        Store fingerprint hashes for a fault signature.

        Args:
            signature_id: ID of the fault signature.
            hashes: List of (hash_value, time_offset) tuples.
        """
        self.connection.executemany(
            """INSERT INTO signature_hashes (signature_id, hash_value, time_offset)
               VALUES (?, ?, ?)""",
            [(signature_id, h, t) for h, t in hashes],
        )
        self.connection.commit()

    def get_signature_hashes(self, signature_id: int) -> list[tuple[int, float]]:
        """Retrieve all hashes for a signature."""
        cursor = self.connection.execute(
            "SELECT hash_value, time_offset FROM signature_hashes WHERE signature_id = ?",
            (signature_id,),
        )
        return [(row["hash_value"], row["time_offset"]) for row in cursor.fetchall()]

    def find_matching_hashes(
        self, hash_values: list[int]
    ) -> list[tuple[int, int, float]]:
        """
        Find all stored hashes that match any of the given hash values.

        Returns:
            List of (signature_id, hash_value, time_offset) tuples.
        """
        if not hash_values:
            return []

        # Use batched queries for large hash sets
        results = []
        batch_size = 500

        for i in range(0, len(hash_values), batch_size):
            batch = hash_values[i : i + batch_size]
            placeholders = ",".join("?" * len(batch))
            cursor = self.connection.execute(
                f"""SELECT signature_id, hash_value, time_offset
                    FROM signature_hashes
                    WHERE hash_value IN ({placeholders})""",
                batch,
            )
            results.extend(
                [
                    (row["signature_id"], row["hash_value"], row["time_offset"])
                    for row in cursor.fetchall()
                ]
            )

        return results

    def get_hash_count_by_signature(self, signature_id: int) -> int:
        """Get the total number of hashes stored for a signature."""
        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM signature_hashes WHERE signature_id = ?",
            (signature_id,),
        )
        return cursor.fetchone()[0]

    # ---- Analysis Session Operations ----

    def create_session(
        self,
        audio_path: str = "",
        user_codes: str = "",
        notes: str = "",
        duration_seconds: float = 0.0,
    ) -> int:
        """Create a new analysis session. Returns the session ID."""
        cursor = self.connection.execute(
            """INSERT INTO analysis_sessions
               (audio_path, user_codes, notes, duration_seconds)
               VALUES (?, ?, ?, ?)""",
            (audio_path, user_codes, notes, duration_seconds),
        )
        self.connection.commit()
        return cursor.lastrowid

    def add_session_match(
        self,
        session_id: int,
        signature_id: int,
        confidence: float,
    ):
        """Record a match result for a session."""
        self.connection.execute(
            """INSERT INTO session_matches (session_id, signature_id, confidence)
               VALUES (?, ?, ?)""",
            (session_id, signature_id, confidence),
        )
        self.connection.commit()

    def get_session_history(self, limit: int = 50) -> list[AnalysisSession]:
        """Retrieve recent analysis sessions."""
        cursor = self.connection.execute(
            """SELECT * FROM analysis_sessions
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        )
        return [
            AnalysisSession(
                id=row["id"],
                timestamp=row["timestamp"] or "",
                audio_path=row["audio_path"] or "",
                user_codes=row["user_codes"] or "",
                notes=row["notes"] or "",
                duration_seconds=row["duration_seconds"] or 0.0,
            )
            for row in cursor.fetchall()
        ]

    def get_session_matches(self, session_id: int) -> list[MatchResult]:
        """Get match results for a specific session."""
        cursor = self.connection.execute(
            """SELECT sm.confidence, fs.id, fs.name, fs.description,
                      fs.category, fs.associated_codes
               FROM session_matches sm
               JOIN fault_signatures fs ON sm.signature_id = fs.id
               WHERE sm.session_id = ?
               ORDER BY sm.confidence DESC""",
            (session_id,),
        )
        return [
            MatchResult(
                fault_name=row["name"],
                confidence_pct=row["confidence"],
                trouble_codes=row["associated_codes"] or "",
                description=row["description"] or "",
                category=row["category"],
                signature_id=row["id"],
            )
            for row in cursor.fetchall()
        ]

    def delete_session(self, session_id: int):
        """Delete an analysis session and its matches."""
        self.connection.execute(
            "DELETE FROM analysis_sessions WHERE id = ?", (session_id,)
        )
        self.connection.commit()

    # ---- Signature Management ----

    def delete_signature(self, signature_id: int):
        """Delete a fault signature and all its hashes."""
        self.connection.execute(
            "DELETE FROM signature_hashes WHERE signature_id = ?",
            (signature_id,),
        )
        self.connection.execute(
            "DELETE FROM fault_signatures WHERE id = ?", (signature_id,)
        )
        self.connection.commit()

    def get_signature_count(self) -> int:
        """Get total number of fault signatures."""
        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM fault_signatures"
        )
        return cursor.fetchone()[0]

    def get_total_hash_count(self) -> int:
        """Get total number of fingerprint hashes across all signatures."""
        cursor = self.connection.execute(
            "SELECT COUNT(*) FROM signature_hashes"
        )
        return cursor.fetchone()[0]
