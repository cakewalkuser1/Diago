-- Enterprise migration: repair logs, session extensions, analytics support

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
