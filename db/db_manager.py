"""
Database Manager for AI-Augmented Smart Traffic Signal Management System.
Supports PostgreSQL (via psycopg2) with automatic fallback to SQLite.
"""

import os
import sqlite3
import datetime
import hashlib
import secrets
from typing import List, Dict, Any, Tuple, Optional

# Optional psycopg2
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

DB_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(DB_DIR, "traffic_system.db")
SCHEMA_SQL_PATH = os.path.join(DB_DIR, "schema.sql")

# PostgreSQL Config from Environment
PG_HOST = os.getenv("PGHOST", "localhost")
PG_PORT = int(os.getenv("PGPORT", "5432"))
PG_DB = os.getenv("PGDATABASE", "traffic_db")
PG_USER = os.getenv("PGUSER", "postgres")
PG_PASSWORD = os.getenv("PGPASSWORD", "postgres")

ACTIVE_ENGINE = "sqlite"  # 'postgresql' or 'sqlite'


def get_db_connection():
    """
    Returns an active database connection and engine type.
    Tries PostgreSQL first if credentials/service are available, else SQLite.
    """
    global ACTIVE_ENGINE
    if PSYCOPG2_AVAILABLE and os.getenv("USE_POSTGRES", "false").lower() in ("1", "true", "yes"):
        try:
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                dbname=PG_DB,
                user=PG_USER,
                password=PG_PASSWORD,
                connect_timeout=3
            )
            ACTIVE_ENGINE = "postgresql"
            return conn, "postgresql"
        except Exception:
            pass  # Fallback to SQLite

    # Default to robust SQLite
    conn = sqlite3.connect(SQLITE_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    ACTIVE_ENGINE = "sqlite"
    return conn, "sqlite"


def get_schema_ddl() -> str:
    """Returns the SQL schema definition for LLM context."""
    if os.path.exists(SCHEMA_SQL_PATH):
        with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return """
    CREATE TABLE intersections (id VARCHAR PRIMARY KEY, name VARCHAR, current_phase INT, phase_name VARCHAR, cycle_time_sec INT, status VARCHAR);
    CREATE TABLE traffic_metrics (id INT PRIMARY KEY, intersection_id VARCHAR, timestamp TIMESTAMP, vehicle_count INT, avg_speed_kmh NUMERIC, queue_length INT, congestion_level VARCHAR, waiting_time_sec NUMERIC);
    CREATE TABLE emergency_events (id INT PRIMARY KEY, vehicle_id VARCHAR, vehicle_type VARCHAR, route VARCHAR, priority_level VARCHAR, corridor_active BOOLEAN, tls_adjusted VARCHAR, created_at TIMESTAMP, cleared_at TIMESTAMP);
    CREATE TABLE signal_phase_logs (id INT PRIMARY KEY, intersection_id VARCHAR, phase_index INT, phase_name VARCHAR, duration_sec NUMERIC, triggered_by_emergency BOOLEAN, timestamp TIMESTAMP);
    """


def init_db():
    """Initializes tables and seeds starting sample data if empty."""
    conn, engine = get_db_connection()
    cursor = conn.cursor()

    if engine == "sqlite":
        # SQLite compatible creation
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS intersections (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            latitude REAL DEFAULT 0.0,
            longitude REAL DEFAULT 0.0,
            current_phase INTEGER DEFAULT 0,
            phase_name TEXT DEFAULT 'EW_GREEN',
            cycle_time_sec INTEGER DEFAULT 90,
            status TEXT DEFAULT 'ACTIVE',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS traffic_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intersection_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            vehicle_count INTEGER NOT NULL DEFAULT 0,
            avg_speed_kmh REAL NOT NULL DEFAULT 0.0,
            queue_length INTEGER NOT NULL DEFAULT 0,
            congestion_level TEXT DEFAULT 'LOW',
            waiting_time_sec REAL NOT NULL DEFAULT 0.0,
            inflow_rate REAL DEFAULT 0.0,
            FOREIGN KEY (intersection_id) REFERENCES intersections(id)
        );

        CREATE TABLE IF NOT EXISTS emergency_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            vehicle_type TEXT DEFAULT 'AMBULANCE',
            route TEXT,
            current_edge TEXT,
            priority_level TEXT DEFAULT 'HIGH',
            corridor_active BOOLEAN DEFAULT 1,
            tls_adjusted TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cleared_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS signal_phase_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intersection_id TEXT NOT NULL,
            phase_index INTEGER NOT NULL,
            phase_name TEXT NOT NULL,
            duration_sec REAL NOT NULL,
            triggered_by_emergency BOOLEAN DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (intersection_id) REFERENCES intersections(id)
        );

        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT DEFAULT 'SUPER_ADMIN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_admin_username ON admin_users(username);
        """)
    else:
        with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
            cursor.execute(f.read())

    # Ensure admin user is seeded
    seed_admin_user()

    # Seed baseline intersections if table is empty
    cursor.execute("SELECT COUNT(*) FROM intersections")
    count = cursor.fetchone()[0]
    if count == 0:
        base_intersections = [
            ("Node2", "Main St & 1st Ave (Downtown West)", 37.7749, -122.4194, 0, "EW_GREEN", 90, "ACTIVE"),
            ("Node5", "Main St & 4th Ave (Downtown East)", 37.7758, -122.4140, 2, "NS_GREEN", 90, "ACTIVE"),
            ("Node8", "Highway 27 North Interchange", 37.7801, -122.4102, 0, "EW_GREEN", 120, "ACTIVE"),
            ("Node11", "Metro Hospital Expressway Junction", 37.7712, -122.4250, 0, "EW_GREEN", 90, "ACTIVE"),
        ]
        insert_query = """
        INSERT INTO intersections (id, name, latitude, longitude, current_phase, phase_name, cycle_time_sec, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """ if engine == "sqlite" else """
        INSERT INTO intersections (id, name, latitude, longitude, current_phase, phase_name, cycle_time_sec, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.executemany(insert_query, base_intersections)

        # Seed historical telemetry for past hours
        now = datetime.datetime.now()
        metric_rows = []
        for i in range(24):
            hist_time = (now - datetime.timedelta(minutes=(24 - i) * 10)).strftime("%Y-%m-%d %H:%M:%S")
            # Node2
            metric_rows.append((
                "Node2", hist_time, 25 + (i % 8) * 4, 38.5 - (i % 6) * 2.1, 4 + (i % 5),
                "MODERATE" if i % 4 == 0 else "LOW", 14.5 + (i % 5) * 3, 12.0 + (i % 3)
            ))
            # Node5
            metric_rows.append((
                "Node5", hist_time, 42 + (i % 10) * 5, 26.0 - (i % 5) * 1.8, 11 + (i % 7),
                "HIGH" if i % 3 == 0 else "MODERATE", 28.0 + (i % 4) * 4.5, 18.0 + (i % 4)
            ))

        metric_insert = """
        INSERT INTO traffic_metrics (intersection_id, timestamp, vehicle_count, avg_speed_kmh, queue_length, congestion_level, waiting_time_sec, inflow_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """ if engine == "sqlite" else """
        INSERT INTO traffic_metrics (intersection_id, timestamp, vehicle_count, avg_speed_kmh, queue_length, congestion_level, waiting_time_sec, inflow_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.executemany(metric_insert, metric_rows)

        # Seed sample emergency event
        em_time = (now - datetime.timedelta(minutes=35)).strftime("%Y-%m-%d %H:%M:%S")
        cleared = (now - datetime.timedelta(minutes=28)).strftime("%Y-%m-%d %H:%M:%S")
        em_insert = """
        INSERT INTO emergency_events (vehicle_id, vehicle_type, route, current_edge, priority_level, corridor_active, tls_adjusted, created_at, cleared_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """ if engine == "sqlite" else """
        INSERT INTO emergency_events (vehicle_id, vehicle_type, route, current_edge, priority_level, corridor_active, tls_adjusted, created_at, cleared_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(em_insert, (
            "EM_AMB_911", "AMBULANCE", "Hospital Corridor Eastbound", "edge_main_wb", "CRITICAL", False, "Node2,Node5", em_time, cleared
        ))

    conn.commit()
    conn.close()
    return engine


def execute_safe_query(query: str, params: Tuple = ()) -> Tuple[List[str], List[Dict[str, Any]], str]:
    """
    Executes a SELECT query safely and returns (columns, rows_as_dicts, engine).
    """
    conn, engine = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            raw_rows = cursor.fetchall()
            rows = []
            for r in raw_rows:
                if engine == "postgresql":
                    rows.append(dict(zip(columns, r)))
                else:
                    rows.append({col: r[col] for col in columns})
            return columns, rows, engine
        return [], [], engine
    finally:
        conn.close()


def log_live_metric(intersection_id: str, vehicle_count: int, avg_speed: float, queue_len: int, congestion: str, waiting_time: float):
    """Logs real-time traffic telemetry from the simulation into database."""
    conn, engine = get_db_connection()
    try:
        cursor = conn.cursor()
        q = """
        INSERT INTO traffic_metrics (intersection_id, timestamp, vehicle_count, avg_speed_kmh, queue_length, congestion_level, waiting_time_sec)
        VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
        """ if engine == "sqlite" else """
        INSERT INTO traffic_metrics (intersection_id, timestamp, vehicle_count, avg_speed_kmh, queue_length, congestion_level, waiting_time_sec)
        VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s)
        """
        cursor.execute(q, (intersection_id, vehicle_count, round(avg_speed, 2), queue_len, congestion, round(waiting_time, 2)))
        conn.commit()
    finally:
        conn.close()


def log_emergency_event(vehicle_id: str, vehicle_type: str, route: str, tls_adjusted: str) -> int:
    """Logs the activation of an emergency corridor preemption event."""
    conn, engine = get_db_connection()
    try:
        cursor = conn.cursor()
        q = """
        INSERT INTO emergency_events (vehicle_id, vehicle_type, route, priority_level, corridor_active, tls_adjusted, created_at)
        VALUES (?, ?, ?, 'CRITICAL', 1, ?, CURRENT_TIMESTAMP)
        """ if engine == "sqlite" else """
        INSERT INTO emergency_events (vehicle_id, vehicle_type, route, priority_level, corridor_active, tls_adjusted, created_at)
        VALUES (%s, %s, %s, 'CRITICAL', TRUE, %s, CURRENT_TIMESTAMP) RETURNING id
        """
        cursor.execute(q, (vehicle_id, vehicle_type, route, tls_adjusted))
        event_id = cursor.lastrowid if engine == "sqlite" else cursor.fetchone()[0]
        conn.commit()
        return event_id
    finally:
        conn.close()


def clear_emergency_event(vehicle_id: str):
    """Marks an emergency corridor preemption as completed."""
    conn, engine = get_db_connection()
    try:
        cursor = conn.cursor()
        q = """
        UPDATE emergency_events
        SET corridor_active = 0, cleared_at = CURRENT_TIMESTAMP
        WHERE vehicle_id = ? AND corridor_active = 1
        """ if engine == "sqlite" else """
        UPDATE emergency_events
        SET corridor_active = FALSE, cleared_at = CURRENT_TIMESTAMP
        WHERE vehicle_id = %s AND corridor_active = TRUE
        """
        cursor.execute(q, (vehicle_id,))
        conn.commit()
    finally:
        conn.close()


# -------------------------------------------------------------
# Admin Authentication & Security
# -------------------------------------------------------------

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 100,000 iterations.
    Returns (hex_hash, salt).
    """
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return pw_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verifies a plain text password against stored hash and salt."""
    test_hash, _ = hash_password(password, salt=salt)
    return secrets.compare_digest(test_hash, password_hash)


def seed_admin_user(default_username: str = "admin", default_password: str = "admin123") -> bool:
    """
    Seeds the initial administrator account if no admin accounts exist.
    Credentials can also be customized via ADMIN_USERNAME and ADMIN_PASSWORD env vars.
    """
    username = os.getenv("ADMIN_USERNAME", default_username).strip()
    password = os.getenv("ADMIN_PASSWORD", default_password)

    conn, engine = get_db_connection()
    try:
        cursor = conn.cursor()
        q_check = "SELECT COUNT(*) FROM admin_users WHERE username = ?" if engine == "sqlite" else "SELECT COUNT(*) FROM admin_users WHERE username = %s"
        cursor.execute(q_check, (username,))
        count = cursor.fetchone()[0]
        if count == 0:
            pw_hash, salt = hash_password(password)
            q_ins = """
            INSERT INTO admin_users (username, password_hash, salt, role)
            VALUES (?, ?, ?, 'SUPER_ADMIN')
            """ if engine == "sqlite" else """
            INSERT INTO admin_users (username, password_hash, salt, role)
            VALUES (%s, %s, %s, 'SUPER_ADMIN')
            """
            cursor.execute(q_ins, (username, pw_hash, salt))
            conn.commit()
            return True
        return False
    finally:
        conn.close()


def authenticate_admin(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticates an administrator with username and password.
    Returns admin details if valid; None otherwise.
    """
    if not username or not password:
        return None

    conn, engine = get_db_connection()
    try:
        cursor = conn.cursor()
        q = "SELECT id, username, password_hash, salt, role FROM admin_users WHERE username = ?" if engine == "sqlite" else "SELECT id, username, password_hash, salt, role FROM admin_users WHERE username = %s"
        cursor.execute(q, (username.strip(),))
        row = cursor.fetchone()
        if not row:
            return None

        if engine == "sqlite":
            user_id = row["id"]
            uname = row["username"]
            pw_hash = row["password_hash"]
            salt = row["salt"]
            role = row["role"]
        else:
            user_id, uname, pw_hash, salt, role = row[0], row[1], row[2], row[3], row[4]

        if verify_password(password, pw_hash, salt):
            # Update last_login
            q_upd = "UPDATE admin_users SET last_login = CURRENT_TIMESTAMP WHERE id = ?" if engine == "sqlite" else "UPDATE admin_users SET last_login = CURRENT_TIMESTAMP WHERE id = %s"
            cursor.execute(q_upd, (user_id,))
            conn.commit()
            return {
                "id": user_id,
                "username": uname,
                "role": role
            }
        return None
    finally:
        conn.close()

