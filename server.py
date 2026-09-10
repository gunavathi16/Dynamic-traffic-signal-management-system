"""
Backend API Server for AI-Augmented Smart Traffic Signal Management System.
Powered by FastAPI, Uvicorn, PostgreSQL/SQLite, and Anthropic Claude Text-to-SQL agent.
"""

import os
import sys
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Internal modules
from db.db_manager import init_db, execute_safe_query, ACTIVE_ENGINE
from ai_agent.nl_sql_agent import TrafficNLSQLAgent, ANTHROPIC_AVAILABLE
from traffic_engine.adaptive_controller import traffic_controller

# Initialize Database
init_db()

# Initialize AI Agent
ai_agent = TrafficNLSQLAgent()

app = FastAPI(
    title="AI-Augmented Smart Traffic Signal Management System",
    description="Adaptive traffic signal optimization, emergency corridor routing, and Anthropic LLM Text-to-SQL agent.",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Request Models
class AIQueryRequest(BaseModel):
    query: str


class EmergencyDispatchRequest(BaseModel):
    vehicle_type: Optional[str] = "AMBULANCE"
    route: Optional[str] = "Main St Corridor (Node2 -> Node5)"


@app.get("/")
async def get_index():
    """Serves the main interactive dashboard."""
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Traffic Management System API is running."}


@app.get("/styles.css")
async def get_styles():
    return FileResponse(os.path.join(BASE_DIR, "styles.css"))


@app.get("/app.js")
async def get_app_js():
    return FileResponse(os.path.join(BASE_DIR, "app.js"))


@app.get("/LOGO1.jpg")
async def get_logo():
    logo_path = os.path.join(BASE_DIR, "LOGO1.jpg")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    raise HTTPException(status_code=404, detail="Logo not found")


@app.get("/api/status")
async def get_system_status():
    """Returns overarching system health, simulation step, and engine states."""
    controller_status = traffic_controller.get_status()
    return {
        "status": "OPERATIONAL",
        "database_engine": ACTIVE_ENGINE,
        "anthropic_available": ANTHROPIC_AVAILABLE,
        "anthropic_key_set": bool(ai_agent.client),
        "telemetry": controller_status
    }


@app.get("/api/intersections")
async def get_intersections():
    """Returns current real-time state for all managed intersections."""
    status = traffic_controller.get_status()
    return {
        "intersections": status["intersections"],
        "active_emergencies": status["active_emergencies"]
    }


@app.get("/api/metrics/recent")
async def get_recent_metrics():
    """Returns recent historical traffic metrics for chart visualizations."""
    query = """
    SELECT tm.id, tm.intersection_id, tm.timestamp, tm.vehicle_count, tm.avg_speed_kmh, tm.queue_length, tm.waiting_time_sec, i.name
    FROM traffic_metrics tm
    JOIN intersections i ON tm.intersection_id = i.id
    ORDER BY tm.id DESC
    LIMIT 20;
    """
    cols, rows, eng = execute_safe_query(query)
    return {"columns": cols, "metrics": rows, "engine": eng}


@app.post("/api/emergency/dispatch")
async def dispatch_emergency_vehicle(payload: EmergencyDispatchRequest):
    """Triggers an emergency vehicle and establishes green corridor priority."""
    em = traffic_controller.dispatch_emergency(
        vehicle_type=payload.vehicle_type or "AMBULANCE",
        route=payload.route or "Main St Corridor (Node2 -> Node5)"
    )
    return {
        "success": True,
        "message": f"Emergency corridor activated for {em['vehicle_id']} on {em['route']}",
        "event": em
    }


@app.post("/api/simulation/toggle")
async def toggle_simulation():
    """Toggles background simulation loop."""
    if traffic_controller.is_running:
        traffic_controller.stop_simulation()
        state = "PAUSED"
    else:
        traffic_controller.start_background_simulation()
        state = "RUNNING"
    return {"is_running": traffic_controller.is_running, "state": state}


@app.post("/api/ai/query")
async def process_ai_query(payload: AIQueryRequest):
    """Processes natural language questions into safe SQL and returns insights."""
    if not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query prompt cannot be empty.")

    result = ai_agent.query(payload.query.strip())
    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting AI Smart Traffic Signal Server on http://127.0.0.1:{port}...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
