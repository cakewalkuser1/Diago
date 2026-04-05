-- Uber-style tracking, mechanic profiles, reviews, push, maintenance

-- mechanic_location_log: GPS breadcrumbs for active jobs
CREATE TABLE IF NOT EXISTS mechanic_location_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    mechanic_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    heading REAL,
    speed_mph REAL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (mechanic_id) REFERENCES mechanics(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_mechanic_location_log_job ON mechanic_location_log(job_id);

-- reviews: ratings after job completion
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    reviewer_id TEXT NOT NULL,
    reviewee_id TEXT NOT NULL,
    reviewer_role TEXT NOT NULL CHECK(reviewer_role IN ('customer', 'mechanic')),
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    UNIQUE(job_id, reviewer_role)
);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewee ON reviews(reviewee_id);

-- push_subscriptions: Web Push for mechanics
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    p256dh_key TEXT NOT NULL,
    auth_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user ON push_subscriptions(user_id);

-- maintenance_records: user vehicle maintenance history
CREATE TABLE IF NOT EXISTS maintenance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    vehicle_vin TEXT,
    vehicle_year INTEGER,
    vehicle_make TEXT,
    vehicle_model TEXT,
    service_type TEXT NOT NULL,
    mileage INTEGER,
    performed_at TIMESTAMP,
    next_due_mileage INTEGER,
    next_due_date TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_maintenance_records_user ON maintenance_records(user_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_records_vehicle ON maintenance_records(vehicle_vin);

-- maintenance_schedules: common service intervals (seed data)
CREATE TABLE IF NOT EXISTS maintenance_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_type TEXT NOT NULL UNIQUE,
    interval_miles INTEGER,
    interval_months INTEGER,
    description TEXT
);
