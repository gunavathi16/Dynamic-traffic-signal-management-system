-- ===================================================================
-- AI-Augmented Smart Traffic Signal Management System
-- Relational Schema: PostgreSQL / SQLite Compatible DDL
-- ===================================================================

CREATE TABLE IF NOT EXISTS intersections (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    latitude DOUBLE PRECISION DEFAULT 0.0,
    longitude DOUBLE PRECISION DEFAULT 0.0,
    current_phase INTEGER DEFAULT 0,
    phase_name VARCHAR(50) DEFAULT 'EW_GREEN',
    cycle_time_sec INTEGER DEFAULT 90,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS traffic_metrics (
    id SERIAL PRIMARY KEY,
    intersection_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    vehicle_count INTEGER NOT NULL DEFAULT 0,
    avg_speed_kmh NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    queue_length INTEGER NOT NULL DEFAULT 0,
    congestion_level VARCHAR(20) DEFAULT 'LOW',  -- 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
    waiting_time_sec NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    inflow_rate NUMERIC(5, 2) DEFAULT 0.0,
    FOREIGN KEY (intersection_id) REFERENCES intersections(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS emergency_events (
    id SERIAL PRIMARY KEY,
    vehicle_id VARCHAR(50) NOT NULL,
    vehicle_type VARCHAR(50) DEFAULT 'AMBULANCE', -- 'AMBULANCE', 'FIRE_ENGINE', 'POLICE'
    route VARCHAR(150),
    current_edge VARCHAR(100),
    priority_level VARCHAR(20) DEFAULT 'HIGH',     -- 'HIGH', 'CRITICAL'
    corridor_active BOOLEAN DEFAULT TRUE,
    tls_adjusted VARCHAR(100),                     -- e.g. 'Node2,Node5'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cleared_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signal_phase_logs (
    id SERIAL PRIMARY KEY,
    intersection_id VARCHAR(50) NOT NULL,
    phase_index INTEGER NOT NULL,
    phase_name VARCHAR(50) NOT NULL,
    duration_sec NUMERIC(5, 2) NOT NULL,
    triggered_by_emergency BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (intersection_id) REFERENCES intersections(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    salt VARCHAR(64) NOT NULL,
    role VARCHAR(30) DEFAULT 'SUPER_ADMIN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Optimization Indexes
CREATE INDEX IF NOT EXISTS idx_metrics_intersection_time ON traffic_metrics(intersection_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_emergency_active ON emergency_events(corridor_active);
CREATE INDEX IF NOT EXISTS idx_phase_logs_intersection ON signal_phase_logs(intersection_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_admin_username ON admin_users(username);
