"""
Database Manager
SQLite database operations for fault signatures, analysis sessions,
and fingerprint hash storage.
"""

import logging
import sqlite3
import os
import threading
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


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

    def __init__(self, db_path: str, obd2_codes_path: str | None = None):
        self.db_path = db_path
        self._obd2_codes_path = obd2_codes_path
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
                except sqlite3.Error as e:
                    logger.warning("Error closing database connection: %s", e)
            self._all_connections.clear()
        self._local = threading.local()
        logger.debug("All database connections closed")

    def initialize(self):
        """Create tables and seed data if needed."""
        logger.info("Initializing database at %s", self.db_path)
        self._create_tables()
        self._ensure_selected_vehicle_table()
        self._ensure_failure_modes_table()
        self._ensure_diagnosis_usage_table()
        self._ensure_stripe_subscription_user_table()
        self._run_enterprise_migrations()
        self._ensure_jobs_thread_id_column()
        self._ensure_analysis_sessions_photos_column()
        self._ensure_mechanics_tracking_columns()
        self._ensure_jobs_tracking_columns()
        self._run_tracking_migrations()
        self._seed_maintenance_schedules()
        self._seed_if_empty()
        self._seed_trouble_codes_if_empty()
        self._seed_failure_modes_if_empty()
        self._seed_mechanics_if_empty()
        self._run_content_migrations()
        self._ensure_tsb_extended_columns()
        self._seed_labor_times_if_empty()
        logger.info("Database initialization complete")

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

    def _ensure_selected_vehicle_table(self):
        """Ensure selected_vehicle table exists (for new and existing DBs)."""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS selected_vehicle (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                model_year INTEGER,
                make TEXT,
                model TEXT,
                submodel TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.commit()

    def get_selected_vehicle(self) -> dict | None:
        """Return the stored selected vehicle (year, make, model, submodel) or None."""
        cursor = self.connection.execute(
            "SELECT model_year, make, model, submodel FROM selected_vehicle WHERE id = 1"
        )
        row = cursor.fetchone()
        if row is None:
            return None
        year = row["model_year"]
        if year is None and row["make"] is None and row["model"] is None:
            return None
        return {
            "model_year": year,
            "make": (row["make"] or "").strip(),
            "model": (row["model"] or "").strip(),
            "submodel": (row["submodel"] or "").strip(),
        }

    def set_selected_vehicle(
        self,
        model_year: int | None,
        make: str,
        model: str,
        submodel: str = "",
    ) -> None:
        """Store the selected vehicle (single row id=1)."""
        make = (make or "").strip()
        model = (model or "").strip()
        submodel = (submodel or "").strip()
        self.connection.execute(
            """INSERT OR REPLACE INTO selected_vehicle (id, model_year, make, model, submodel, updated_at)
               VALUES (1, ?, ?, ?, ?, datetime('now'))""",
            (model_year, make, model, submodel),
        )
        self.connection.commit()

    def _ensure_jobs_thread_id_column(self):
        """Add thread_id to jobs table if missing (for mechanic respond resume)."""
        try:
            cursor = self.connection.execute("PRAGMA table_info(jobs)")
            columns = [row[1] for row in cursor.fetchall()]
            if "thread_id" not in columns:
                self.connection.execute("ALTER TABLE jobs ADD COLUMN thread_id TEXT")
                self.connection.commit()
                logger.debug("Added thread_id column to jobs table")
        except sqlite3.OperationalError as e:
            logger.warning("Could not add thread_id to jobs: %s", e)

    def _ensure_analysis_sessions_photos_column(self):
        """Add photos column to analysis_sessions if missing (JSON array of photo URLs)."""
        try:
            cursor = self.connection.execute("PRAGMA table_info(analysis_sessions)")
            columns = [row[1] for row in cursor.fetchall()]
            if "photos" not in columns:
                self.connection.execute("ALTER TABLE analysis_sessions ADD COLUMN photos TEXT")
                self.connection.commit()
                logger.debug("Added photos column to analysis_sessions")
        except sqlite3.OperationalError as e:
            logger.warning("Could not add photos to analysis_sessions: %s", e)

    def _ensure_mechanics_tracking_columns(self):
        """Add tracking/profile columns to mechanics if missing."""
        cols = [
            ("user_id", "TEXT"),
            ("email", "TEXT"),
            ("phone", "TEXT"),
            ("service_radius_mi", "REAL DEFAULT 25"),
            ("hourly_rate_cents", "INTEGER"),
            ("bio", "TEXT"),
            ("profile_photo_url", "TEXT"),
            ("rating", "REAL DEFAULT 0"),
            ("total_jobs", "INTEGER DEFAULT 0"),
            ("is_verified", "INTEGER DEFAULT 0"),
            ("last_latitude", "REAL"),
            ("last_longitude", "REAL"),
            ("last_seen_at", "TIMESTAMP"),
        ]
        try:
            cursor = self.connection.execute("PRAGMA table_info(mechanics)")
            existing = {row[1] for row in cursor.fetchall()}
            for name, typ in cols:
                if name not in existing:
                    self.connection.execute(f"ALTER TABLE mechanics ADD COLUMN {name} {typ}")
                    logger.debug("Added %s to mechanics", name)
            self.connection.commit()
        except sqlite3.OperationalError as e:
            logger.warning("Could not add mechanics columns: %s", e)

    def _ensure_jobs_tracking_columns(self):
        """Add tracking columns to jobs if missing."""
        cols = [
            ("estimated_arrival_at", "TIMESTAMP"),
            ("mechanic_accepted_at", "TIMESTAMP"),
            ("mechanic_en_route_at", "TIMESTAMP"),
            ("mechanic_arrived_at", "TIMESTAMP"),
            ("repair_started_at", "TIMESTAMP"),
            ("completed_at", "TIMESTAMP"),
            ("route_distance_mi", "REAL"),
            ("route_duration_min", "REAL"),
        ]
        try:
            cursor = self.connection.execute("PRAGMA table_info(jobs)")
            existing = {row[1] for row in cursor.fetchall()}
            for name, typ in cols:
                if name not in existing:
                    self.connection.execute(f"ALTER TABLE jobs ADD COLUMN {name} {typ}")
                    logger.debug("Added %s to jobs", name)
            self.connection.commit()
        except sqlite3.OperationalError as e:
            logger.warning("Could not add jobs columns: %s", e)

    def _run_tracking_migrations(self):
        """Run tracking migrations (mechanic_location_log, reviews, push, maintenance)."""
        migrations_path = Path(__file__).parent / "migrations_tracking.sql"
        if migrations_path.exists():
            with open(migrations_path, "r") as f:
                sql = f.read()
            self.connection.executescript(sql)
            self.connection.commit()
            logger.debug("Tracking migrations applied")

    def _seed_maintenance_schedules(self):
        """Seed common maintenance intervals if empty."""
        try:
            cursor = self.connection.execute("SELECT COUNT(*) FROM maintenance_schedules")
            if cursor.fetchone()[0] > 0:
                return
            schedules = [
                ("oil_change", 5000, 6, "Engine oil and filter"),
                ("tire_rotation", 7500, 6, "Rotate tires"),
                ("brake_inspection", 12000, 12, "Brake pads and rotors"),
                ("air_filter", 15000, 12, "Engine air filter"),
                ("coolant_flush", 30000, 24, "Coolant system flush"),
                ("transmission_fluid", 60000, 60, "Transmission fluid"),
                ("spark_plugs", 100000, 100, "Spark plug replacement"),
            ]
            for st, miles, months, desc in schedules:
                self.connection.execute(
                    "INSERT OR IGNORE INTO maintenance_schedules (service_type, interval_miles, interval_months, description) VALUES (?, ?, ?, ?)",
                    (st, miles, months, desc),
                )
            self.connection.commit()
        except sqlite3.OperationalError as e:
            logger.debug("maintenance_schedules seed skipped: %s", e)

    def _run_enterprise_migrations(self):
        """Run enterprise migrations (repair_logs, etc.)."""
        migrations_path = Path(__file__).parent / "migrations_enterprise.sql"
        if migrations_path.exists():
            with open(migrations_path, "r") as f:
                sql = f.read()
            self.connection.executescript(sql)
            self.connection.commit()
            logger.debug("Enterprise migrations applied")

    def _ensure_failure_modes_table(self):
        """Ensure failure_modes table exists (for new and existing DBs)."""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS failure_modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                failure_id TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT,
                mechanical_class TEXT,
                required_conditions TEXT NOT NULL,
                supporting_conditions TEXT,
                disqualifiers TEXT,
                weight REAL NOT NULL DEFAULT 0.8,
                confirm_tests TEXT,
                vehicle_scope TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_failure_modes_class ON failure_modes(mechanical_class)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_failure_modes_scope ON failure_modes(vehicle_scope)"
        )
        self.connection.commit()

    def _ensure_diagnosis_usage_table(self):
        """Ensure diagnosis_usage table exists (for rate limit persistence)."""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS diagnosis_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usage_key TEXT NOT NULL,
                month TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(usage_key, month)
            )
        """)
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_diagnosis_usage_key_month ON diagnosis_usage(usage_key, month)"
        )
        self.connection.commit()

    def get_diagnosis_usage(self, usage_key: str, month: str) -> int:
        """Return current diagnosis count for the given key and month."""
        cursor = self.connection.execute(
            "SELECT count FROM diagnosis_usage WHERE usage_key = ? AND month = ?",
            (usage_key, month),
        )
        row = cursor.fetchone()
        return int(row["count"]) if row else 0

    def increment_diagnosis_usage(self, usage_key: str, month: str) -> int:
        """Increment diagnosis count for key/month; return new count."""
        self.connection.execute(
            """
            INSERT INTO diagnosis_usage (usage_key, month, count) VALUES (?, ?, 1)
            ON CONFLICT(usage_key, month) DO UPDATE SET count = count + 1
            """,
            (usage_key, month),
        )
        self.connection.commit()
        return self.get_diagnosis_usage(usage_key, month)

    def _ensure_stripe_subscription_user_table(self):
        """Ensure stripe_subscription_user table exists (webhook tier sync)."""
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS stripe_subscription_user (
                stripe_subscription_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL
            )
        """)
        self.connection.commit()

    def save_stripe_subscription_user(self, stripe_subscription_id: str, user_id: str) -> None:
        """Store mapping from Stripe subscription id to user id."""
        self.connection.execute(
            """
            INSERT OR REPLACE INTO stripe_subscription_user (stripe_subscription_id, user_id)
            VALUES (?, ?)
            """,
            (stripe_subscription_id, user_id),
        )
        self.connection.commit()

    def get_user_id_by_subscription_id(self, stripe_subscription_id: str) -> str | None:
        """Return user_id for a Stripe subscription id, or None."""
        cursor = self.connection.execute(
            "SELECT user_id FROM stripe_subscription_user WHERE stripe_subscription_id = ?",
            (stripe_subscription_id,),
        )
        row = cursor.fetchone()
        return row["user_id"] if row else None

    def get_subscription_id_by_user_id(self, user_id: str) -> str | None:
        """Return Stripe subscription id for a user (most recent row), or None."""
        cursor = self.connection.execute(
            "SELECT stripe_subscription_id FROM stripe_subscription_user WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        return row["stripe_subscription_id"] if row else None

    def delete_stripe_subscription_user(self, stripe_subscription_id: str) -> None:
        """Remove mapping after subscription ends."""
        self.connection.execute(
            "DELETE FROM stripe_subscription_user WHERE stripe_subscription_id = ?",
            (stripe_subscription_id,),
        )
        self.connection.commit()

    def create_parts_order(
        self,
        part_description: str,
        retailer: str,
        retailer_store_id: str,
        amount_cents: int,
        payment_intent_id: str,
        user_id: str | None = None,
    ) -> int:
        """Create a parts order (pending_payment). Returns order id."""
        cursor = self.connection.execute(
            """INSERT INTO parts_orders (user_id, part_description, retailer, retailer_store_id, status, payment_intent_id, amount_cents)
               VALUES (?, ?, ?, ?, 'pending_payment', ?, ?)""",
            (user_id, part_description, retailer, retailer_store_id, payment_intent_id, amount_cents),
        )
        self.connection.commit()
        return cursor.lastrowid

    def update_parts_order_paid(self, payment_intent_id: str) -> bool:
        """Mark parts order as paid by payment_intent_id. Returns True if updated."""
        cursor = self.connection.execute(
            "UPDATE parts_orders SET status = 'paid', updated_at = CURRENT_TIMESTAMP WHERE payment_intent_id = ? AND status = 'pending_payment'",
            (payment_intent_id,),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def get_parts_order_by_payment_intent(self, payment_intent_id: str) -> dict | None:
        """Return parts order by payment_intent_id or None."""
        cursor = self.connection.execute(
            "SELECT id, status, part_description, retailer FROM parts_orders WHERE payment_intent_id = ?",
            (payment_intent_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def _seed_failure_modes_if_empty(self):
        """
        Upsert all failure modes from seed data.
        Uses INSERT OR IGNORE so new patterns added to the seed file are picked
        up on next startup without wiping user-created modes.
        """
        try:
            self.connection.execute("SELECT 1 FROM failure_modes LIMIT 1")
        except sqlite3.OperationalError:
            return
        import json
        from database.seed_failure_modes import get_seed_failure_modes
        for fm in get_seed_failure_modes():
            self.connection.execute(
                """INSERT OR IGNORE INTO failure_modes
                   (failure_id, display_name, description, mechanical_class,
                    required_conditions, supporting_conditions, disqualifiers,
                    weight, confirm_tests, vehicle_scope)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fm["failure_id"],
                    fm["display_name"],
                    fm.get("description") or "",
                    fm.get("mechanical_class") or "",
                    json.dumps(fm.get("required_conditions") or []),
                    json.dumps(fm.get("supporting_conditions") or []),
                    json.dumps(fm.get("disqualifiers") or []),
                    fm.get("weight", 0.8),
                    json.dumps(fm.get("confirm_tests") or []),
                    fm.get("vehicle_scope"),
                ),
            )
        self.connection.commit()

    def _seed_mechanics_if_empty(self):
        """Seed mechanics table with mock mobile mechanics for dispatch (Phase 1)."""
        try:
            cursor = self.connection.execute("SELECT COUNT(*) FROM mechanics")
            count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            return
        if count > 0:
            return
        mock_mechanics = [
            ("Mike's Mobile Auto", 34.05, -118.25, "available", "+1-555-0101", "brakes,suspension"),
            ("Quick Fix Auto", 34.06, -118.24, "available", "+1-555-0102", "engine,electrical"),
            ("Roadside Repairs", 34.04, -118.26, "available", "+1-555-0103", "general"),
        ]
        for name, lat, lng, avail, contact, skills in mock_mechanics:
            self.connection.execute(
                """INSERT INTO mechanics (name, latitude, longitude, availability, contact, skills)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, lat, lng, avail, contact, skills),
            )
        self.connection.commit()

    def get_mechanics_by_vicinity(
        self,
        user_lat: float | None,
        user_lng: float | None,
        radius_mi: float = 25.0,
        limit: int = 10,
    ) -> list[dict]:
        """
        Return available mechanics within radius of user location.
        Uses Haversine formula for distance (SQLite has no native geo).
        If user_lat/lng is None, returns all available mechanics sorted by id.
        """
        import math

        try:
            cursor = self.connection.execute(
                "SELECT id, name, latitude, longitude, availability, rating FROM mechanics WHERE availability = 'available'"
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            try:
                cursor = self.connection.execute(
                    "SELECT id, name, latitude, longitude, availability FROM mechanics WHERE availability = 'available'"
                )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                return []

        def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            R = 3959  # Earth radius in miles
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlam = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        out = []
        for row in rows:
            m_lat = row["latitude"]
            m_lng = row["longitude"]
            if m_lat is None or m_lng is None:
                distance_mi = 999.0
            elif user_lat is not None and user_lng is not None:
                distance_mi = haversine_mi(user_lat, user_lng, m_lat, m_lng)
                if distance_mi > radius_mi:
                    continue
            else:
                distance_mi = 999.0

            out.append({
                "id": row["id"],
                "name": row["name"],
                "distance_mi": round(distance_mi, 1),
                "availability": row["availability"] or "available",
                "rating": row["rating"] if "rating" in row.keys() else None,
            })

        out.sort(key=lambda m: m["distance_mi"])
        return out[:limit]

    def create_mechanic_profile(
        self,
        user_id: str,
        name: str,
        email: str = "",
        phone: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        service_radius_mi: float = 25.0,
        hourly_rate_cents: int | None = None,
        bio: str = "",
        skills: str = "",
    ) -> int:
        """Create a mechanic profile linked to user_id. Returns mechanic id."""
        cursor = self.connection.execute(
            """INSERT INTO mechanics
               (user_id, name, email, phone, latitude, longitude, availability,
                service_radius_mi, hourly_rate_cents, bio, skills)
               VALUES (?, ?, ?, ?, ?, ?, 'available', ?, ?, ?, ?)""",
            (user_id, name, email, phone, latitude, longitude, service_radius_mi, hourly_rate_cents, bio, skills),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_mechanic_by_user_id(self, user_id: str) -> dict | None:
        """Return mechanic profile by user_id or None."""
        cursor = self.connection.execute(
            """SELECT id, user_id, name, email, phone, latitude, longitude, availability,
                      service_radius_mi, hourly_rate_cents, bio, profile_photo_url,
                      rating, total_jobs, is_verified, skills
               FROM mechanics WHERE user_id = ?""",
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_mechanic_by_id(self, mechanic_id: int) -> dict | None:
        """Return mechanic profile by id or None."""
        cursor = self.connection.execute(
            """SELECT id, user_id, name, email, phone, latitude, longitude, availability,
                      service_radius_mi, hourly_rate_cents, bio, profile_photo_url,
                      rating, total_jobs, is_verified, skills
               FROM mechanics WHERE id = ?""",
            (mechanic_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_mechanic_profile(
        self,
        mechanic_id: int,
        *,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        service_radius_mi: float | None = None,
        hourly_rate_cents: int | None = None,
        bio: str | None = None,
        profile_photo_url: str | None = None,
        skills: str | None = None,
        availability: str | None = None,
    ) -> bool:
        """Update mechanic profile. Returns True if updated."""
        updates = []
        vals = []
        for k, v in [
            ("name", name),
            ("email", email),
            ("phone", phone),
            ("latitude", latitude),
            ("longitude", longitude),
            ("service_radius_mi", service_radius_mi),
            ("hourly_rate_cents", hourly_rate_cents),
            ("bio", bio),
            ("profile_photo_url", profile_photo_url),
            ("skills", skills),
            ("availability", availability),
        ]:
            if v is not None:
                updates.append(f"{k} = ?")
                vals.append(v)
        if not updates:
            return False
        vals.append(mechanic_id)
        self.connection.execute(
            f"UPDATE mechanics SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            vals,
        )
        self.connection.commit()
        return self.connection.total_changes > 0

    def get_failure_modes(self) -> list[dict]:
        """Return all failure modes as list of dicts (for pattern engine)."""
        try:
            cursor = self.connection.execute(
                """SELECT failure_id, display_name, description, mechanical_class,
                          required_conditions, supporting_conditions, disqualifiers,
                          weight, confirm_tests, vehicle_scope
                   FROM failure_modes"""
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            return []
        import json
        out = []
        for row in rows:
            out.append({
                "failure_id": row["failure_id"],
                "display_name": row["display_name"],
                "description": row["description"] or "",
                "mechanical_class": row["mechanical_class"] or "",
                "required_conditions": json.loads(row["required_conditions"] or "[]"),
                "supporting_conditions": json.loads(row["supporting_conditions"] or "[]"),
                "disqualifiers": json.loads(row["disqualifiers"] or "[]"),
                "weight": row["weight"],
                "confirm_tests": json.loads(row["confirm_tests"] or "[]"),
                "vehicle_scope": row["vehicle_scope"],
            })
        return out

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
        except sqlite3.OperationalError as e:
            logger.warning("trouble_code_definitions table not found: %s", e)
            return

        if count > 0:
            return

        import json
        if self._obd2_codes_path and Path(self._obd2_codes_path).exists():
            json_path = Path(self._obd2_codes_path)
        else:
            json_path = Path(__file__).parent / "obd2_codes.json"
        if not json_path.exists():
            logger.warning("OBD2 codes file not found at %s", json_path)
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

    # ---- Repair Logs (Enterprise) ----

    def create_repair_log(
        self,
        session_id: int | None,
        vin: str | None,
        repair_description: str,
        parts_used: str = "",
        outcome: str = "",
    ) -> int:
        """Create a repair log entry. Returns the log ID."""
        cursor = self.connection.execute(
            """INSERT INTO repair_logs (session_id, vin, repair_description, parts_used, outcome)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, (vin or "").strip() or None, repair_description, parts_used, outcome),
        )
        self.connection.commit()
        return cursor.lastrowid

    def list_repair_logs(
        self,
        vin: str | None = None,
        session_id: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List repair logs, optionally filtered by VIN or session_id."""
        query = "SELECT id, session_id, vin, repair_description, parts_used, outcome, created_at FROM repair_logs WHERE 1=1"
        params: list = []
        if vin:
            query += " AND vin = ?"
            params.append(vin.strip())
        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = self.connection.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_analytics(self) -> dict:
        """Return shop analytics: diagnoses count, repair logs count, recent activity."""
        diagnoses = self.connection.execute(
            "SELECT COUNT(*) FROM analysis_sessions"
        ).fetchone()[0]
        repairs = self.connection.execute(
            "SELECT COUNT(*) FROM repair_logs"
        ).fetchone()[0]
        return {
            "total_diagnoses": diagnoses,
            "total_repair_logs": repairs,
        }

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

    # ---- Technical Service Bulletins ----

    def insert_tsb(
        self,
        model_year: int,
        make: str,
        model: str,
        component: str = "",
        summary: str = "",
        nhtsa_id: str = "",
        document_id: str = "",
    ) -> int:
        """Insert a single TSB record. Returns row id."""
        cursor = self.connection.execute(
            """INSERT INTO technical_service_bulletins
               (model_year, make, model, component, summary, nhtsa_id, document_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (model_year, make.strip(), model.strip(), component.strip(), summary.strip(), nhtsa_id.strip(), document_id.strip()),
        )
        self.connection.commit()
        return cursor.lastrowid

    def search_tsbs(
        self,
        model_year: int | None = None,
        make: str | None = None,
        model: str | None = None,
        component: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Search TSBs by vehicle and optional component. Returns list of dicts."""
        conditions = []
        params = []
        if model_year is not None:
            conditions.append("model_year = ?")
            params.append(model_year)
        if make:
            conditions.append("LOWER(make) LIKE LOWER(?)")
            params.append(f"%{make.strip()}%")
        if model:
            conditions.append("LOWER(model) LIKE LOWER(?)")
            params.append(f"%{model.strip()}%")
        if component:
            conditions.append("LOWER(component) LIKE LOWER(?)")
            params.append(f"%{component.strip()}%")

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        cursor = self.connection.execute(
            f"""SELECT id, model_year, make, model, component, summary, nhtsa_id, document_id,
                       bulletin_date, affected_mileage_range, affected_codes,
                       document_url, manufacturer_id, severity, source, created_at
                FROM technical_service_bulletins WHERE {where} ORDER BY model_year DESC, make, model LIMIT ?""",
            params,
        )
        rows = cursor.fetchall()
        keys = [c[0] for c in cursor.description]
        return [dict(zip(keys, row)) for row in rows]

    def get_tsb_count(self) -> int:
        """Return total number of TSB records."""
        try:
            cursor = self.connection.execute("SELECT COUNT(*) FROM technical_service_bulletins")
            return cursor.fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    def insert_tsb_extended(
        self,
        model_year: int,
        make: str,
        model: str,
        component: str = "",
        summary: str = "",
        nhtsa_id: str = "",
        document_id: str = "",
        bulletin_date: str = "",
        affected_mileage_range: str = "",
        affected_codes: str = "",
        document_url: str = "",
        manufacturer_id: str = "",
        severity: str = "medium",
        source: str = "nhtsa",
    ) -> int:
        """Insert a TSB with all extended fields. Returns row id."""
        cursor = self.connection.execute(
            """INSERT INTO technical_service_bulletins
               (model_year, make, model, component, summary, nhtsa_id, document_id,
                bulletin_date, affected_mileage_range, affected_codes,
                document_url, manufacturer_id, severity, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                model_year, make.strip(), model.strip(),
                component.strip(), summary.strip(),
                nhtsa_id.strip(), document_id.strip(),
                bulletin_date.strip(), affected_mileage_range.strip(),
                affected_codes.strip(), document_url.strip(),
                manufacturer_id.strip(), severity.strip(), source.strip(),
            ),
        )
        self.connection.commit()
        return cursor.lastrowid

    def _ensure_tsb_extended_columns(self):
        """Add extended columns to technical_service_bulletins if missing."""
        extended_cols = [
            ("bulletin_date",           "TEXT DEFAULT ''"),
            ("affected_mileage_range",  "TEXT DEFAULT ''"),
            ("affected_codes",          "TEXT DEFAULT ''"),
            ("document_url",            "TEXT DEFAULT ''"),
            ("manufacturer_id",         "TEXT DEFAULT ''"),
            ("severity",                "TEXT DEFAULT 'medium'"),
            ("source",                  "TEXT DEFAULT 'nhtsa'"),
        ]
        try:
            cursor = self.connection.execute("PRAGMA table_info(technical_service_bulletins)")
            existing = {row[1] for row in cursor.fetchall()}
            for col_name, col_def in extended_cols:
                if col_name not in existing:
                    self.connection.execute(
                        f"ALTER TABLE technical_service_bulletins ADD COLUMN {col_name} {col_def}"
                    )
                    logger.debug("Added column %s to technical_service_bulletins", col_name)
            self.connection.commit()
        except sqlite3.OperationalError as e:
            logger.warning("Could not extend technical_service_bulletins: %s", e)

    # ---- Content migrations (wiring diagrams, labor times) ----

    def _run_content_migrations(self):
        """Run content migrations (wiring_diagrams, labor_times tables)."""
        migrations_path = Path(__file__).parent / "migrations_content.sql"
        if migrations_path.exists():
            with open(migrations_path, "r") as f:
                sql = f.read()
            self.connection.executescript(sql)
            self.connection.commit()
            logger.debug("Content migrations applied")

    # ---- Wiring Diagrams ----

    def insert_wiring_diagram(
        self,
        system: str,
        circuit_name: str,
        circuit_number: str = "",
        component: str = "",
        description: str = "",
        vehicle_make: str | None = None,
        vehicle_model: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        diagram_url: str = "",
        diagram_source: str = "",
        related_codes: str = "",
        related_failure_modes: str = "",
    ) -> int:
        """Insert a wiring diagram record. Returns row id."""
        cursor = self.connection.execute(
            """INSERT INTO wiring_diagrams
               (system, circuit_name, circuit_number, component, description,
                vehicle_make, vehicle_model, year_min, year_max,
                diagram_url, diagram_source, related_codes, related_failure_modes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (system, circuit_name, circuit_number, component, description,
             vehicle_make, vehicle_model, year_min, year_max,
             diagram_url, diagram_source, related_codes, related_failure_modes),
        )
        self.connection.commit()
        return cursor.lastrowid

    def insert_wiring_pin(
        self,
        diagram_id: int,
        connector_id: str,
        pin_number: str,
        wire_color: str = "",
        signal_type: str = "signal",
        connects_to: str = "",
        typical_value: str = "",
        notes: str = "",
    ) -> int:
        """Insert a connector pin row for a wiring diagram. Returns row id."""
        cursor = self.connection.execute(
            """INSERT INTO wiring_diagram_pins
               (diagram_id, connector_id, pin_number, wire_color,
                signal_type, connects_to, typical_value, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (diagram_id, connector_id, pin_number, wire_color,
             signal_type, connects_to, typical_value, notes),
        )
        self.connection.commit()
        return cursor.lastrowid

    def search_wiring_diagrams(
        self,
        system: str | None = None,
        component: str | None = None,
        dtc_code: str | None = None,
        vehicle_make: str | None = None,
        vehicle_model: str | None = None,
        model_year: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search wiring diagrams. Returns list of dicts including pin rows."""
        conditions = []
        params = []
        if system:
            conditions.append("LOWER(system) = LOWER(?)")
            params.append(system.strip())
        if component:
            conditions.append("LOWER(component) LIKE LOWER(?)")
            params.append(f"%{component.strip()}%")
        if dtc_code:
            conditions.append("LOWER(related_codes) LIKE LOWER(?)")
            params.append(f"%{dtc_code.strip()}%")
        if vehicle_make:
            conditions.append("(vehicle_make IS NULL OR LOWER(vehicle_make) LIKE LOWER(?))")
            params.append(f"%{vehicle_make.strip()}%")
        if vehicle_model:
            conditions.append("(vehicle_model IS NULL OR LOWER(vehicle_model) LIKE LOWER(?))")
            params.append(f"%{vehicle_model.strip()}%")
        if model_year is not None:
            conditions.append("(year_min IS NULL OR year_min <= ?) AND (year_max IS NULL OR year_max >= ?)")
            params.extend([model_year, model_year])

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        try:
            cursor = self.connection.execute(
                f"""SELECT id, system, circuit_name, circuit_number, component, description,
                           vehicle_make, vehicle_model, year_min, year_max,
                           diagram_url, diagram_source, related_codes, related_failure_modes, created_at
                    FROM wiring_diagrams WHERE {where} ORDER BY system, circuit_name LIMIT ?""",
                params,
            )
            diagrams = [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()]
            # Attach pins to each diagram
            for d in diagrams:
                pin_cursor = self.connection.execute(
                    "SELECT connector_id, pin_number, wire_color, signal_type, connects_to, typical_value, notes "
                    "FROM wiring_diagram_pins WHERE diagram_id = ? ORDER BY connector_id, pin_number",
                    (d["id"],),
                )
                d["pins"] = [dict(zip([c[0] for c in pin_cursor.description], row)) for row in pin_cursor.fetchall()]
            return diagrams
        except sqlite3.OperationalError as e:
            logger.warning("wiring_diagrams search failed: %s", e)
            return []

    def get_wiring_diagram_by_id(self, diagram_id: int) -> dict | None:
        """Fetch a single wiring diagram with its pins."""
        try:
            cursor = self.connection.execute(
                "SELECT * FROM wiring_diagrams WHERE id = ?", (diagram_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            pin_cursor = self.connection.execute(
                "SELECT connector_id, pin_number, wire_color, signal_type, connects_to, typical_value, notes "
                "FROM wiring_diagram_pins WHERE diagram_id = ? ORDER BY connector_id, pin_number",
                (diagram_id,),
            )
            d["pins"] = [dict(zip([c[0] for c in pin_cursor.description], row)) for row in pin_cursor.fetchall()]
            return d
        except sqlite3.OperationalError:
            return None

    def get_wiring_diagram_count(self) -> int:
        """Return total number of wiring diagram records."""
        try:
            cursor = self.connection.execute("SELECT COUNT(*) FROM wiring_diagrams")
            return cursor.fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    # ---- Labor Times ----

    def insert_labor_time(
        self,
        operation_key: str,
        operation_name: str,
        labor_hours: float,
        labor_hours_max: float | None = None,
        vehicle_make: str | None = None,
        vehicle_model: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        skill_level: str = "intermediate",
        notes: str = "",
        related_codes: str = "",
        mechanical_class: str = "",
    ) -> int:
        """Insert or replace a labor time record. Returns row id."""
        cursor = self.connection.execute(
            """INSERT OR REPLACE INTO labor_times
               (operation_key, operation_name, labor_hours, labor_hours_max,
                vehicle_make, vehicle_model, year_min, year_max,
                skill_level, notes, related_codes, mechanical_class)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (operation_key, operation_name, labor_hours, labor_hours_max,
             vehicle_make, vehicle_model, year_min, year_max,
             skill_level, notes, related_codes, mechanical_class),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_labor_times(
        self,
        operation_key: str,
        vehicle_make: str | None = None,
        vehicle_model: str | None = None,
        model_year: int | None = None,
    ) -> list[dict]:
        """
        Look up labor times for an operation. Returns the most-specific match first
        (make+model+year > make+model > make > generic).
        """
        try:
            params: list = [f"%{operation_key.lower()}%"]
            conditions = ["LOWER(operation_key) LIKE ?"]
            if vehicle_make:
                conditions.append("(vehicle_make IS NULL OR LOWER(vehicle_make) = LOWER(?))")
                params.append(vehicle_make)
            if vehicle_model:
                conditions.append("(vehicle_model IS NULL OR LOWER(vehicle_model) = LOWER(?))")
                params.append(vehicle_model)
            if model_year is not None:
                conditions.append("(year_min IS NULL OR year_min <= ?) AND (year_max IS NULL OR year_max >= ?)")
                params.extend([model_year, model_year])

            where = " AND ".join(conditions)
            cursor = self.connection.execute(
                f"""SELECT * FROM labor_times WHERE {where}
                    ORDER BY
                      (CASE WHEN vehicle_make IS NOT NULL THEN 1 ELSE 0 END) DESC,
                      (CASE WHEN vehicle_model IS NOT NULL THEN 1 ELSE 0 END) DESC,
                      (CASE WHEN year_min IS NOT NULL THEN 1 ELSE 0 END) DESC
                    LIMIT 10""",
                params,
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError as e:
            logger.warning("labor_times query failed: %s", e)
            return []

    def _seed_labor_times_if_empty(self):
        """Seed labor_times from motor_daas stub if the table is empty."""
        try:
            cursor = self.connection.execute("SELECT COUNT(*) FROM labor_times")
            if cursor.fetchone()[0] > 0:
                return
        except sqlite3.OperationalError:
            return
        try:
            from api.services.motor_daas import _LABOR_DB
            for key, lt in _LABOR_DB.items():
                self.insert_labor_time(
                    operation_key=key,
                    operation_name=lt.operation,
                    labor_hours=lt.hours,
                    labor_hours_max=lt.hours_max,
                    skill_level=lt.skill_level,
                    notes=lt.notes,
                )
            logger.info("Seeded %d labor time records", len(_LABOR_DB))
        except Exception as e:
            logger.warning("Could not seed labor_times: %s", e)
