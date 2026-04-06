-- Content migrations: wiring diagrams, labor times, and TSB field extensions.
-- Applied automatically by DatabaseManager._run_content_migrations() on startup.
-- Safe to run multiple times (all statements use CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS patterns).

-- ---------------------------------------------------------------------------
-- 1. TECHNICAL SERVICE BULLETINS: extended columns
--    Added to the existing technical_service_bulletins table.
--    SQLite does not support ADD COLUMN IF NOT EXISTS in executescript, so
--    these are handled in Python via _ensure_tsb_extended_columns().
-- ---------------------------------------------------------------------------
-- Columns added by Python migration:
--   bulletin_date    TEXT   -- ISO date string, e.g. "2019-03-15"
--   affected_mileage_range  TEXT  -- free-form, e.g. "Under 80,000 miles"
--   affected_codes   TEXT   -- comma-separated related OBD-II / OEM codes
--   document_url     TEXT   -- link to full TSB PDF or OEM portal
--   manufacturer_id  TEXT   -- OEM bulletin number (distinct from nhtsa_id)
--   severity         TEXT   -- low | medium | high | critical
--   source           TEXT   -- nhtsa | mitchell | alldata | oem | manual


-- ---------------------------------------------------------------------------
-- 2. WIRING DIAGRAMS
-- ---------------------------------------------------------------------------

-- One record per logical circuit (e.g. "Ignition Coil 1 Circuit", "ABS Front Left WSS").
-- Each diagram belongs to a vehicle range and describes a circuit in the vehicle.
CREATE TABLE IF NOT EXISTS wiring_diagrams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    system          TEXT NOT NULL,          -- fuel | ignition | abs | charging | starting | cooling | body | hvac | transmission | other
    circuit_name    TEXT NOT NULL,          -- human-readable name, e.g. "Ignition Coil B1 Circuit"
    circuit_number  TEXT,                   -- OEM circuit number if known, e.g. "#57"
    component       TEXT,                   -- primary component, e.g. "ECM", "Ignition Coil"
    description     TEXT,                   -- plain-English circuit description
    vehicle_make    TEXT,                   -- NULL = generic / applies to all
    vehicle_model   TEXT,                   -- NULL = all models of make
    year_min        INTEGER,                -- NULL = no lower bound
    year_max        INTEGER,                -- NULL = no upper bound
    diagram_url     TEXT,                   -- external reference URL (Mitchell, AllData, OEM portal, YouTube)
    diagram_source  TEXT,                   -- label for the URL source, e.g. "Mitchell1", "AllData", "OEM Service Manual"
    related_codes   TEXT,                   -- comma-separated OBD-II codes this circuit relates to
    related_failure_modes TEXT,             -- comma-separated failure_id values
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wiring_system      ON wiring_diagrams(system);
CREATE INDEX IF NOT EXISTS idx_wiring_make_model  ON wiring_diagrams(vehicle_make, vehicle_model);
CREATE INDEX IF NOT EXISTS idx_wiring_component   ON wiring_diagrams(component);
CREATE INDEX IF NOT EXISTS idx_wiring_codes       ON wiring_diagrams(related_codes);

-- Connector pin-level data for a wiring diagram.
-- One row per pin; many pins per diagram.
CREATE TABLE IF NOT EXISTS wiring_diagram_pins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    diagram_id      INTEGER NOT NULL REFERENCES wiring_diagrams(id) ON DELETE CASCADE,
    connector_id    TEXT NOT NULL,          -- connector designator, e.g. "C101", "E5"
    pin_number      TEXT NOT NULL,          -- pin letter/number, e.g. "A", "1", "3B"
    wire_color      TEXT,                   -- e.g. "BRN/WHT", "GRN"
    signal_type     TEXT,                   -- power | ground | signal | sensor_ref | shield | not_used
    connects_to     TEXT,                   -- component or splice the pin runs to
    typical_value   TEXT,                   -- expected measurement, e.g. "12V ignition", "0-5V sweep", "< 5Ω to ground"
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_wiring_pins_diagram    ON wiring_diagram_pins(diagram_id);
CREATE INDEX IF NOT EXISTS idx_wiring_pins_connector  ON wiring_diagram_pins(connector_id);


-- ---------------------------------------------------------------------------
-- 3. LABOR TIMES
-- ---------------------------------------------------------------------------

-- Flat-rate labor times per repair operation.
-- vehicle_make / vehicle_model NULL means applies to all makes/models.
-- year_min / year_max NULL means any model year.
-- Multiple rows may match a given vehicle; callers should take the most-specific match.
CREATE TABLE IF NOT EXISTS labor_times (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_key   TEXT NOT NULL,          -- slug used for lookup, e.g. "brake_pad_front"
    operation_name  TEXT NOT NULL,          -- display name, e.g. "Front Brake Pad Replacement"
    vehicle_make    TEXT,                   -- NULL = all makes
    vehicle_model   TEXT,                   -- NULL = all models
    year_min        INTEGER,                -- NULL = any year
    year_max        INTEGER,                -- NULL = any year
    labor_hours     REAL NOT NULL,          -- base (low end of range)
    labor_hours_max REAL,                   -- high end of range (NULL = single flat rate)
    skill_level     TEXT DEFAULT 'intermediate',  -- basic | intermediate | advanced | professional
    notes           TEXT,                   -- special notes, e.g. "R&R only; does not include alignment"
    related_codes   TEXT,                   -- comma-separated OBD-II codes
    mechanical_class TEXT,                  -- MECHANICAL_CLASSES key for engine-to-labor linkage
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_labor_key          ON labor_times(operation_key);
CREATE INDEX IF NOT EXISTS idx_labor_make_model   ON labor_times(vehicle_make, vehicle_model);
CREATE INDEX IF NOT EXISTS idx_labor_class        ON labor_times(mechanical_class);
CREATE UNIQUE INDEX IF NOT EXISTS idx_labor_unique ON labor_times(operation_key, COALESCE(vehicle_make,''), COALESCE(vehicle_model,''), COALESCE(year_min,0), COALESCE(year_max,0));
