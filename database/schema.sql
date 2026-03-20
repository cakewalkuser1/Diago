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
    duration_seconds REAL,
    photos TEXT  -- JSON array of photo URLs
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

-- Technical Service Bulletins (imported from NHTSA or other sources)
CREATE TABLE IF NOT EXISTS technical_service_bulletins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_year INTEGER NOT NULL,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    component TEXT,
    summary TEXT,
    nhtsa_id TEXT,
    document_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tsb_vehicle ON technical_service_bulletins(model_year, make, model);
CREATE INDEX IF NOT EXISTS idx_tsb_component ON technical_service_bulletins(component);

-- Single row: current vehicle for tailored diagnosis (year, make, model, submodel/trim)
CREATE TABLE IF NOT EXISTS selected_vehicle (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    model_year INTEGER,
    make TEXT,
    model TEXT,
    submodel TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Failure modes: pattern conditions, disqualifiers, weights, confirm tests (master-tech layer)
CREATE TABLE IF NOT EXISTS failure_modes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    failure_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    mechanical_class TEXT,
    required_conditions TEXT NOT NULL,   -- JSON array of condition keys, e.g. ["P0301","cold_start_misfire","coolant_loss"]
    supporting_conditions TEXT,          -- JSON array, optional
    disqualifiers TEXT,                  -- JSON array, e.g. ["no_coolant_loss"]
    weight REAL NOT NULL DEFAULT 0.8,
    confirm_tests TEXT,                 -- JSON array of {test, tool, expected}
    vehicle_scope TEXT,                 -- optional: make/model/engine slug for platform-specific
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_failure_modes_class ON failure_modes(mechanical_class);
CREATE INDEX IF NOT EXISTS idx_failure_modes_scope ON failure_modes(vehicle_scope);

-- Repair logs (shop/enterprise)
CREATE TABLE IF NOT EXISTS repair_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    vin TEXT,
    repair_description TEXT NOT NULL,
    parts_used TEXT,
    outcome TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES analysis_sessions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_repair_logs_vin ON repair_logs(vin);
CREATE INDEX IF NOT EXISTS idx_repair_logs_session ON repair_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_repair_logs_created ON repair_logs(created_at);

-- Diagnosis usage per key (user_id or anon:ip) per calendar month (rate limit persistence)
CREATE TABLE IF NOT EXISTS diagnosis_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usage_key TEXT NOT NULL,
    month TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(usage_key, month)
);
CREATE INDEX IF NOT EXISTS idx_diagnosis_usage_key_month ON diagnosis_usage(usage_key, month);

-- Stripe subscription -> user mapping (for webhook: set tier to free on cancel)
CREATE TABLE IF NOT EXISTS stripe_subscription_user (
    stripe_subscription_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL
);

-- Dispatch: mobile mechanics (for "find mechanic in vicinity")
CREATE TABLE IF NOT EXISTS mechanics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    availability TEXT DEFAULT 'available',  -- available, busy, offline
    contact TEXT,
    skills TEXT,  -- comma-separated or JSON for vehicle focus
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mechanics_availability ON mechanics(availability);
CREATE INDEX IF NOT EXISTS idx_mechanics_location ON mechanics(latitude, longitude);

-- Dispatch: jobs (diagnosis -> part -> mechanic assignment)
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    diagnosis_session_id INTEGER,
    part_info TEXT,
    user_latitude REAL,
    user_longitude REAL,
    user_address TEXT,
    status TEXT NOT NULL DEFAULT 'pending_mechanic',  -- pending_mechanic, mechanic_pinged, accepted, denied, dispatched, completed
    assigned_mechanic_id INTEGER,
    thread_id TEXT,  -- LangGraph thread_id for resuming on mechanic respond
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (diagnosis_session_id) REFERENCES analysis_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_mechanic_id) REFERENCES mechanics(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);

-- Dispatch: parts orders (part selection + payment + stock)
CREATE TABLE IF NOT EXISTS parts_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    part_description TEXT NOT NULL,
    retailer TEXT,
    retailer_store_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending_payment',  -- pending_payment, paid, stock_confirmed
    payment_intent_id TEXT,
    amount_cents INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_parts_orders_user ON parts_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_parts_orders_status ON parts_orders(status);
