"""
Automated Test Suite for AI-Augmented Smart Traffic Signal Management System.
Tests:
- Read-Only SQL Safety Layer (AST checks, attack injections, limit enforcement)
- Database Manager & Seeding
- Text-to-SQL AI Agent & Insight Generator
- Adaptive Traffic Controller & Emergency Green Corridor Preemption
- FastAPI REST API Endpoints
"""

import unittest
from fastapi.testclient import TestClient

from ai_agent.sql_safety import validate_and_sanitize_sql, SQLSafetyViolation
from ai_agent.nl_sql_agent import TrafficNLSQLAgent
from db.db_manager import (
    init_db, execute_safe_query, hash_password, verify_password,
    authenticate_admin, seed_admin_user
)
from traffic_engine.adaptive_controller import traffic_controller
from server import app


class TestSQLSafetyLayer(unittest.TestCase):
    def test_clean_select_allowed(self):
        sql = "SELECT id, name FROM intersections WHERE status = 'ACTIVE'"
        sanitized = validate_and_sanitize_sql(sql)
        self.assertIn("SELECT", sanitized)
        self.assertIn("LIMIT", sanitized)

    def test_block_drop_table(self):
        with self.assertRaises(SQLSafetyViolation):
            validate_and_sanitize_sql("DROP TABLE intersections;")

    def test_block_delete_statement(self):
        with self.assertRaises(SQLSafetyViolation):
            validate_and_sanitize_sql("DELETE FROM traffic_metrics WHERE queue_length > 0;")

    def test_block_update_statement(self):
        with self.assertRaises(SQLSafetyViolation):
            validate_and_sanitize_sql("UPDATE intersections SET status = 'DISABLED';")

    def test_block_multiple_statements(self):
        with self.assertRaises(SQLSafetyViolation):
            validate_and_sanitize_sql("SELECT * FROM intersections; DROP TABLE traffic_metrics;")

    def test_limit_clamp(self):
        sql = "SELECT * FROM traffic_metrics LIMIT 500"
        sanitized = validate_and_sanitize_sql(sql, max_limit=100)
        self.assertIn("LIMIT 100", sanitized)


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_intersections_seeded(self):
        cols, rows, eng = execute_safe_query("SELECT id, name FROM intersections")
        self.assertGreaterEqual(len(rows), 4)
        node_ids = [r["id"] for r in rows]
        self.assertIn("Node2", node_ids)
        self.assertIn("Node5", node_ids)


class TestAIAgent(unittest.TestCase):
    def setUp(self):
        self.agent = TrafficNLSQLAgent()

    def test_congestion_query(self):
        res = self.agent.query("Which intersection has the highest congestion?")
        self.assertTrue(res["success"])
        self.assertTrue(res["safety_passed"])
        self.assertIn("traffic_metrics", res["generated_sql"])
        self.assertGreater(len(res["rows"]), 0)

    def test_malicious_query_blocked(self):
        res = self.agent.query("DROP TABLE intersections;")
        self.assertFalse(res["safety_passed"])
        self.assertEqual(res["safety_badge"], "BLOCKED_UNSAFE")


class TestAdaptiveController(unittest.TestCase):
    def test_emergency_green_corridor(self):
        em = traffic_controller.dispatch_emergency("AMBULANCE", "Corridor Test")
        self.assertEqual(em["vehicle_type"], "AMBULANCE")

        # Verify Node2 and Node5 are in emergency override
        status = traffic_controller.get_status()
        corridor_nodes = [n for n in status["intersections"] if n["id"] in ("Node2", "Node5")]
        for n in corridor_nodes:
            self.assertTrue(n["emergency_override"])
            self.assertEqual(n["current_phase"], 0)  # EW Green hold


class TestAdminAuthentication(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_password_hash_and_verify(self):
        pw = "SuperSecretKey!2026"
        pw_hash, salt = hash_password(pw)
        self.assertTrue(verify_password(pw, pw_hash, salt))
        self.assertFalse(verify_password("WrongPassword", pw_hash, salt))

    def test_admin_authentication_success(self):
        # Default seeded admin
        admin = authenticate_admin("admin", "admin123")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["username"], "admin")
        self.assertEqual(admin["role"], "SUPER_ADMIN")

    def test_admin_authentication_failure(self):
        # Non-existent user
        self.assertIsNone(authenticate_admin("unknown_user", "admin123"))
        # Wrong password
        self.assertIsNone(authenticate_admin("admin", "wrongpassword!"))


class TestServerEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_status_endpoint(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "OPERATIONAL")
        self.assertIn("telemetry", data)

    def test_ai_query_endpoint(self):
        res = self.client.post("/api/ai/query", json={"query": "Show active emergency vehicles"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["safety_passed"])

    def test_login_page_served(self):
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        self.assertIn("INTELLIFLOW TOC", res.text)
        self.assertIn("Administrator ID", res.text)

    def test_simulation_page_served(self):
        res = self.client.get("/simulation")
        self.assertEqual(res.status_code, 200)
        self.assertIn("INTELLIFLOW", res.text)
        self.assertIn("Arterial Corridor Digital Twin Simulator", res.text)
        self.assertIn("AI Traffic Copilot", res.text)

    def test_simulation_page_with_node_param(self):
        res = self.client.get("/simulation?node=Node2")
        self.assertEqual(res.status_code, 200)
        self.assertIn("simNodeChips", res.text)
        self.assertIn("nodeInspectorCard", res.text)

    def test_admin_auth_flow(self):
        # Invalid credentials -> 401
        res_fail = self.client.post("/api/auth/login", json={"username": "admin", "password": "badpassword"})
        self.assertEqual(res_fail.status_code, 401)

        # Valid credentials -> 200 with token
        res_login = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(res_login.status_code, 200)
        body = res_login.json()
        self.assertTrue(body["success"])
        self.assertIn("token", body)
        token = body["token"]

        # Verify active session
        res_verify = self.client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_verify.status_code, 200)
        self.assertTrue(res_verify.json()["authenticated"])

        # Logout session
        res_logout = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_logout.status_code, 200)

        # Verify session is now revoked -> 401
        res_revoked = self.client.get("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_revoked.status_code, 401)


if __name__ == "__main__":
    unittest.main()

