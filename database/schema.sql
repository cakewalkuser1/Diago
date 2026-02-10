-- Automotive Audio Analyzer Database Schema

-- Known fault audio signatures
CREATE TABLE IF NOT EXISTS fault_signatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL CHECK(category IN ('engine', 'exhaust', 'suspension', 'belt', 'bearing', 'intake', 'electrical', 'accessory', 'drivetrain', 'hvac', 'fuel', 'transmission', 'brakes', 'cooling', 'other')),
    associated_codes TEXT,  -- comma-separated OBD-II codes (e.g., "P0301,P0300")
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fingerprint hashes for each fault signature
CREATE TABLE IF NOT EXISTS signature_hashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signature_id INTEGER NOT NULL,
    hash_value INTEGER NOT NULL,
    time_offset REAL NOT NULL,
    FOREIGN KEY (signature_id) REFERENCES fault_signatures(id) ON DELETE CASCADE
);

-- Index for fast hash lookups during matching
CREATE INDEX IF NOT EXISTS idx_hash_value ON signature_hashes(hash_value);

-- User analysis sessions
CREATE TABLE IF NOT EXISTS analysis_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    audio_path TEXT,
    user_codes TEXT,  -- comma-separated codes entered by user
    notes TEXT,
    duration_seconds REAL
);

-- Match results for each session
CREATE TABLE IF NOT EXISTS session_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    signature_id INTEGER NOT NULL,
    confidence REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (signature_id) REFERENCES fault_signatures(id) ON DELETE CASCADE
);

-- OBD-II Trouble Code Definitions (SAE J2012 + generic)
CREATE TABLE IF NOT EXISTS trouble_code_definitions (
    code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    system TEXT NOT NULL,           -- powertrain, body, chassis, network
    subsystem TEXT,                 -- fuel_metering, ignition, emissions, etc.
    mechanical_classes TEXT,        -- comma-separated class keys matching MECHANICAL_CLASSES
    symptoms TEXT,                  -- comma-separated symptom keywords
    severity TEXT DEFAULT 'medium'  -- low, medium, high, critical
);

-- Index for fast symptom search
CREATE INDEX IF NOT EXISTS idx_code_system ON trouble_code_definitions(system);
CREATE INDEX IF NOT EXISTS idx_code_severity ON trouble_code_definitions(severity);
