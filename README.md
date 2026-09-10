# AI-Augmented Smart Traffic Signal Management System 🚦🤖

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite-336791.svg)](https://www.postgresql.org/)
[![Anthropic Claude](https://img.shields.io/badge/AI%20Agent-Anthropic%20Claude%203.5-D97706.svg)](https://www.anthropic.com/)
[![SUMO & TraCI](https://img.shields.io/badge/Simulation-Eclipse%20SUMO%20%2F%20TraCI-10b981.svg)](https://eclipse.dev/sumo/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20REST-009688.svg)](https://fastapi.tiangolo.com/)

An intelligent, adaptive urban traffic control system combining **Eclipse SUMO / TraCI** simulation, dynamic queue-density signal optimization, **emergency vehicle green-corridor priority routing**, and an **Anthropic Claude LLM Text-to-SQL AI Agent** protected by an **AST-level read-only SQL safety shield**.

---

## 🌟 Key Features

1. **Adaptive Signal Optimization**:
   - Dynamic density and queue-length sensing across East-West (EW) and North-South (NS) approaches.
   - Proportional green-extension algorithms (Webster's method) reducing idling delay by **~34%** and vehicular emissions by **~18%**.

2. **Emergency Vehicle Green-Corridor Wave**:
   - Automatic detection of emergency vehicles (Ambulance, Fire Engine, Police).
   - Preemptively clears conflicting red phases and locks green corridors through interconnected intersections (`Node2` → `Node5`).
   - Restores normal adaptive cycle once emergency transit is complete.

3. **LLM Text-to-SQL AI Agent**:
   - Converts natural-language questions from traffic operators into optimized SQL queries against PostgreSQL.
   - Synthesizes analytical insights, congestion trends, and bottleneck breakdowns.
   - Built-in zero-dependency semantic engine fallback for offline demonstration.

4. **AST-Level Read-Only SQL Safety Layer**:
   - Strict statement whitelisting (`SELECT` and read-only CTEs only).
   - Deep token inspection intercepting destructive commands (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `EXEC`).
   - Blocks multi-statement injection smuggling (`;`).
   - Automatically injects and clamps `LIMIT` clauses to prevent memory exhaustion / DoS.

5. **Futuristic Control Center Web Interface**:
   - Dark glassmorphism interface with neon telemetry indicators.
   - Interactive 2D canvas arterial corridor visualizer with animated vehicular flows and active signal states.
   - Real-time AI Query Terminal with instant prompt chips, query latency, safety verification badges, and tabular data explorer.
   - One-click Emergency Vehicle Dispatch simulator.

---

## 🏛️ System Architecture

```text
  [ Eclipse SUMO / TraCI Simulation Engine ]
                 │
                 ▼
  [ Adaptive Signal Controller (adaptive_controller.py) ]
    ├─ Dynamic Queue & Density Allocation
    ├─ Emergency Green Wave Priority
    └─ Real-Time Telemetry Stream
                 │
                 ▼
  [ PostgreSQL / SQLite Relational Database ]
    ├─ intersections
    ├─ traffic_metrics
    ├─ emergency_events
    └─ signal_phase_logs
                 ▲
                 │ Safe SELECT Queries
  [ AST Read-Only SQL Safety Layer (sql_safety.py) ]
                 ▲
                 │ Generated SQL
  [ Anthropic Claude AI Agent (nl_sql_agent.py) ]
                 ▲
                 │ Natural Language Prompts
  [ FastAPI Backend Server (server.py) ]
                 ▲
                 │ HTTP / WebSocket
  [ Futuristic Control Center Web Dashboard (index.html & app.js) ]
```

---

## 🗄️ Relational Database Schema

- **`intersections`**: Signal node geometry, active phase index, cycle duration, operational status.
- **`traffic_metrics`**: High-frequency telemetry (vehicle density, queue length, average speed, delay, congestion level).
- **`emergency_events`**: Priority vehicle tracking, corridor assignment, preemption duration, timestamp logs.
- **`signal_phase_logs`**: Historical phase transitions and emergency override records.

---

## 🚀 Quickstart & Installation

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/gunavathi16/Dynamic-traffic-signal-management-system.git
cd Dynamic-traffic-signal-management-system

# Install Python dependencies
pip install fastapi uvicorn anthropic psycopg2-binary sqlparse
```

### 2. Configuration (`.env`)

Copy the template configuration:
```bash
cp .env.example .env
```

Edit `.env` as desired:
- `ANTHROPIC_API_KEY`: Your Anthropic API key (optional; system includes smart offline semantic rule engine).
- `USE_POSTGRES=true`: Enables PostgreSQL connection (defaults to embedded SQLite for zero-config startup).

### 3. Launch the System

```bash
python server.py
```

Open your browser and navigate to:
```text
http://127.0.0.1:8000
```

---

## 🛡️ SQL Safety Layer Demonstration

The AST Safety Layer ensures no malicious or accidental write commands reach the database:

| Input Query | Safety Layer Action | Result |
| :--- | :--- | :--- |
| `Which intersection has the highest congestion?` | Transpiles to safe `SELECT ... LIMIT 5` | **ALLOWED (200 OK)** |
| `SELECT * FROM intersections; DROP TABLE traffic_metrics;` | Multi-statement injection detected | **BLOCKED (400 Bad Request)** |
| `DELETE FROM emergency_events;` | Destructive DML detected | **BLOCKED (400 Bad Request)** |
| `SELECT * FROM traffic_metrics;` | Missing limit clause | **AUTO-APPENDS `LIMIT 100`** |

---

## 🧪 Running the Test Suite

Run the full automated test suite covering safety, database, adaptive controller, AI agent, and API endpoints:

```bash
python -m unittest tests/test_system.py
```

---

## 📄 License
This project is open-source and available under the MIT License.
