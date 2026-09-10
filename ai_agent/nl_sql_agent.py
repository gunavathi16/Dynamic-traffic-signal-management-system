"""
Text-to-SQL AI Agent for AI-Augmented Smart Traffic Signal Management System.
Translates natural language questions into safe SQL, executes queries, and synthesizes analytical insights.
Supports Anthropic Claude API with intelligent local semantic fallback.
"""

import os
import re
import time
from typing import Dict, Any, Optional

from db.db_manager import execute_safe_query, get_schema_ddl, ACTIVE_ENGINE
from ai_agent.sql_safety import validate_and_sanitize_sql, SQLSafetyViolation

# Optional Anthropic SDK
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


SYSTEM_PROMPT = f"""You are an expert Traffic Systems Data Analyst and AI SQL Agent.
Your job is to convert natural language queries about smart city traffic telemetry, signal phases, congestion, and emergency green-corridors into clean, read-only SQL queries.

Database Schema:
{get_schema_ddl()}

Rules:
1. Return ONLY the raw SQL query. Do not wrap in backticks or markdown, and do not provide introductory conversational text.
2. Only write read-only SELECT or WITH...SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, or ALTER.
3. Use sensible aggregations (AVG, MAX, COUNT) and ORDER BY / GROUP BY when asked for summaries or comparisons.
4. Join tables logically (e.g. traffic_metrics.intersection_id = intersections.id).
5. Default to sorting latest or highest relevance.
"""


def _generate_fallback_sql(question: str) -> str:
    """
    Intelligent semantic rule-based SQL generator for common traffic queries
    when Anthropic API key is not configured.
    """
    stripped = question.strip()
    upper_q = stripped.upper()

    # If the user passed raw SQL directly (e.g. testing queries or attacks), preserve it for the safety layer to evaluate
    if any(upper_q.startswith(cmd) for cmd in ["SELECT", "WITH", "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]):
        return stripped

    q = question.lower()

    if any(k in q for k in ["highest congestion", "most congested", "worst congestion", "highest delay", "bottleneck"]):
        return """
        SELECT i.name, tm.congestion_level, tm.queue_length, tm.waiting_time_sec, tm.avg_speed_kmh, tm.timestamp
        FROM traffic_metrics tm
        JOIN intersections i ON tm.intersection_id = i.id
        ORDER BY tm.queue_length DESC, tm.waiting_time_sec DESC
        LIMIT 5;
        """

    elif any(k in q for k in ["emergency", "ambulance", "corridor", "priority", "green wave"]):
        return """
        SELECT vehicle_id, vehicle_type, route, current_edge, priority_level, corridor_active, tls_adjusted, created_at, cleared_at
        FROM emergency_events
        ORDER BY created_at DESC
        LIMIT 10;
        """

    elif any(k in q for k in ["average waiting", "avg wait", "delay", "waiting time"]):
        return """
        SELECT i.name, ROUND(AVG(tm.waiting_time_sec), 2) AS avg_wait_seconds, ROUND(AVG(tm.vehicle_count), 1) AS avg_vehicles
        FROM traffic_metrics tm
        JOIN intersections i ON tm.intersection_id = i.id
        GROUP BY i.name
        ORDER BY avg_wait_seconds DESC;
        """

    elif any(k in q for k in ["speed", "fastest", "slowest"]):
        return """
        SELECT i.name, ROUND(AVG(tm.avg_speed_kmh), 2) AS avg_speed, MAX(tm.avg_speed_kmh) AS top_speed, MIN(tm.avg_speed_kmh) AS min_speed
        FROM traffic_metrics tm
        JOIN intersections i ON tm.intersection_id = i.id
        GROUP BY i.name
        ORDER BY avg_speed ASC;
        """

    elif any(k in q for k in ["intersections", "signals", "status", "overview", "nodes"]):
        return """
        SELECT id, name, current_phase, phase_name, cycle_time_sec, status, last_updated
        FROM intersections
        ORDER BY id ASC;
        """

    elif any(k in q for k in ["throughput", "vehicle count", "traffic volume", "densest"]):
        return """
        SELECT i.name, SUM(tm.vehicle_count) AS total_vehicles_logged, ROUND(AVG(tm.vehicle_count), 1) AS avg_density_per_cycle
        FROM traffic_metrics tm
        JOIN intersections i ON tm.intersection_id = i.id
        GROUP BY i.name
        ORDER BY total_vehicles_logged DESC;
        """

    elif any(k in q for k in ["phase", "green extension", "cycle", "logs"]):
        return """
        SELECT spl.intersection_id, spl.phase_name, spl.duration_sec, spl.triggered_by_emergency, spl.timestamp
        FROM signal_phase_logs spl
        ORDER BY spl.timestamp DESC
        LIMIT 10;
        """

    else:
        # General telemetry view
        return """
        SELECT i.name, tm.vehicle_count, tm.avg_speed_kmh, tm.queue_length, tm.congestion_level, tm.waiting_time_sec, tm.timestamp
        FROM traffic_metrics tm
        JOIN intersections i ON tm.intersection_id = i.id
        ORDER BY tm.timestamp DESC
        LIMIT 10;
        """


def _generate_fallback_summary(question: str, rows: list, columns: list) -> str:
    """Generates natural language insight summary from result set."""
    if not rows:
        return "No matching traffic records found for the requested criteria."

    count = len(rows)
    first = rows[0]

    if "avg_wait_seconds" in first:
        return (
            f"Analyzed delay across {count} intersections. "
            f"**{first.get('name', 'Top intersection')}** exhibited the highest average wait time of **{first.get('avg_wait_seconds')}s** "
            f"with an average density of {first.get('avg_vehicles', 'N/A')} vehicles per cycle."
        )

    if "corridor_active" in first:
        active_count = sum(1 for r in rows if r.get("corridor_active"))
        return (
            f"Retrieved {count} emergency vehicle corridor logs. "
            f"Currently **{active_count} emergency corridor(s)** are active, routing prioritized green-waves through junctions."
        )

    if "queue_length" in first and "name" in first:
        return (
            f"Identified top congestion hotspot: **{first.get('name')}** with a peak queue length of **{first.get('queue_length')} vehicles** "
            f"and average travel speed of **{first.get('avg_speed_kmh')} km/h**."
        )

    if "total_vehicles_logged" in first:
        return (
            f"Analyzed traffic volume across {count} intersections. "
            f"Highest throughput recorded at **{first.get('name')}** ({first.get('total_vehicles_logged')} total vehicles logged)."
        )

    return f"Successfully retrieved {count} record(s) matching query. Top record: {list(first.items())[:3]}"


class TrafficNLSQLAgent:
    """Orchestrates Text-to-SQL generation, validation, and analytics response."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.client = None
        if self.api_key and ANTHROPIC_AVAILABLE:
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception:
                self.client = None

    def query(self, natural_language_prompt: str) -> Dict[str, Any]:
        """
        Processes a natural language prompt:
        1. Generates SQL via Claude or semantic engine.
        2. Validates SQL through Safety Layer.
        3. Executes SQL on Database.
        4. Synthesizes analytical summary.
        """
        start_time = time.time()
        sql_source = "Anthropic Claude 3.5" if self.client else "Semantic AI Engine (Local Mode)"
        raw_sql = ""

        # Step 1: SQL Generation
        if self.client:
            try:
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=300,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": natural_language_prompt}]
                )
                raw_sql = response.content[0].text.strip()
            except Exception as e:
                # Fallback to local semantic engine if API error occurs
                raw_sql = _generate_fallback_sql(natural_language_prompt)
                sql_source = f"Semantic Engine Fallback ({type(e).__name__})"
        else:
            raw_sql = _generate_fallback_sql(natural_language_prompt)

        # Step 2: Safety Validation
        try:
            safe_sql = validate_and_sanitize_sql(raw_sql)
            safety_passed = True
            safety_badge = "SHIELD_VERIFIED_READONLY"
            safety_message = "Query validated by AST Safety Layer: Read-only SELECT confirmed."
        except SQLSafetyViolation as violation:
            return {
                "success": False,
                "error": "Safety Violation",
                "message": str(violation),
                "raw_sql": raw_sql,
                "safety_passed": False,
                "safety_badge": "BLOCKED_UNSAFE",
                "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                "columns": [],
                "rows": [],
                "insight": f"Query blocked for security: {str(violation)}"
            }

        # Step 3: Database Execution
        try:
            columns, rows, engine_used = execute_safe_query(safe_sql)
        except Exception as db_err:
            return {
                "success": False,
                "error": "Database Execution Error",
                "message": str(db_err),
                "safe_sql": safe_sql,
                "safety_passed": True,
                "safety_badge": "DB_ERROR",
                "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                "columns": [],
                "rows": [],
                "insight": f"Database execution failed: {str(db_err)}"
            }

        # Step 4: Summarization
        if self.client and rows:
            try:
                summary_prompt = (
                    f"Summarize the following traffic telemetry data in 2 concise sentences for a traffic controller:\n"
                    f"User Question: '{natural_language_prompt}'\n"
                    f"Data: {rows[:5]}"
                )
                sum_resp = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=150,
                    messages=[{"role": "user", "content": summary_prompt}]
                )
                insight = sum_resp.content[0].text.strip()
            except Exception:
                insight = _generate_fallback_summary(natural_language_prompt, rows, columns)
        else:
            insight = _generate_fallback_summary(natural_language_prompt, rows, columns)

        exec_time = round((time.time() - start_time) * 1000, 2)

        return {
            "success": True,
            "question": natural_language_prompt,
            "generated_sql": safe_sql,
            "sql_source": sql_source,
            "safety_passed": True,
            "safety_badge": safety_badge,
            "safety_message": safety_message,
            "database_engine": engine_used,
            "execution_time_ms": exec_time,
            "row_count": len(rows),
            "columns": columns,
            "rows": rows,
            "insight": insight
        }
