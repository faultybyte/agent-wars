# Autonomous Logistics Agent Pipeline

An end-to-end autonomous logistics orchestration system.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│                   Logistics Handler                    │
│                  (Google ADK Runner)                   │
│                                                        │
│   ┌────────────────────────────────────────────────┐   │
│   │             Orchestrator Agent                 │   │
│   └──────┬───────────────────┬───────────────────┬─┘   │
│          │                   │                   │     │
│          ▼                   ▼                   ▼     │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────┐ │
│   │  Inventory   │    │   Routing    │    │ Exception│ │
│   │    Agent     │    │    Agent     │    │  Agent   │ │
│   └──────────────┘    └──────────────┘    └──────────┘ │
└───────────────────────────▲────────────────────────────┘
                            │ (JSON-RPC / Direct)
                   ┌────────┴────────┐
                   │   FastMCP Server│
                   └────────┬────────┘
                            │
               ┌────────────┴────────────┐
               │    FastAPI REST & UI   │
               │   (http://localhost:8000)│
               └─────────────────────────┘
```

### Components

1. **Autonomous ADK Agent (`src/agent_wars/agent_handler.py`)**:
   - `LogisticsOrchestrator`: Master agent managing the order lifecycle.
   - `InventoryAgent`: Sub-agent verifying catalog stock and warehouse quantities.
   - `DispatchAgent`: Sub-agent planning route feasibility, transit weather checks, and carrier booking.
   - `ExceptionAgent`: Sub-agent handling stock shortages, alternative SKU discovery, and route blockage rerouting.

2. **FastMCP Server (`src/agent_wars/mcp_server.py`)**:
   - Exposes tools via Model Context Protocol:
     - `check_inventory(sku)`
     - `check_route_weather(destination)`
     - `dispatch_order(order_id, sku, destination, quantity, carrier)`
     - `suggest_alternatives(sku)`
     - `flag_order_exception(order_id, destination, reason, alternative_suggestion)`
     - `list_products()`
     - `list_inventory()`
     - `get_shipment_status(order_id)`

3. **FastAPI Web Backend & Dashboard (`src/agent_wars/api.py`)**:
   - REST API endpoints (`/api/orders/process`, `/api/orders`, `/api/inventory`, `/api/products`, `/api/shipments`, `/api/health`).
   - FastMCP server mounted at `/mcp`.
   - Healthcheck & probe endpoints: `/api/health`, `/healthz`, `/livez`.
   - Swagger OpenAPI interactive documentation at `/docs`.
   - Rich real-time Single Page Application dashboard served at `/`.

4. **Relational Database (`src/agent_wars/database.py` / `inventory.db`)**:
   - Tables: `products`, `warehouses`, `inventory`, `orders`, `order_items`, `shipments`.
   - Configurable storage path via `DATABASE_PATH` for persistent volume mounts.

---

## Project Structure

```
agent-wars/
├── src/
│   └── agent_wars/
│       ├── __init__.py          # Package exports (app, mcp, orchestrator, main)
│       ├── agent_handler.py     # Google ADK autonomous multi-agent hierarchy
│       ├── api.py               # FastAPI backend, FastMCP mount, & web dashboard
│       ├── database.py          # SQLite relational database operations & schema
│       ├── mcp_server.py        # FastMCP server exposing logistics tools
│       └── setup_db.py          # Database initialization & test data seeding
├── tests/
│   └── test_pipeline.py         # Pytest automated unit and integration suite
├── main.py                      # Unified CLI & server entrypoint
├── render.yaml                  # Render deployment Blueprint specification
├── Dockerfile                   # Container build for Cloud Run / Docker
├── docker-compose.yml           # Multi-container orchestration with persistent volume
├── requirements.txt             # Clean dependencies for cloud builds
├── pyproject.toml               # Modern Python project configuration
├── .dockerignore                # Container build exclusions
├── .env.example                 # Environment variables reference
└── README.md                    # Project documentation
```

---

## Local Setup Instructions

Follow these step-by-step instructions to set up and run the project locally on your machine.

### 1. Prerequisites

- **Python**: Version `3.13` (or `3.11+`) installed. Verify with:
  ```bash
  python --version
  ```
- **Git**: Installed on your system.
- **Gemini API Key**: Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).

---

### 2. Clone the Repository

```bash
git clone https://github.com/your-username/agent-wars.git
cd agent-wars
```

---

### 3. Create & Activate a Virtual Environment

#### Option A: Using standard Python `venv`

- **On Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
  *(If PowerShell blocks script execution, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

- **On Windows (Command Prompt)**:
  ```cmd
  python -m venv .venv
  .\.venv\Scripts\activate.bat
  ```

- **On macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

#### Option B: Using `uv` (Fastest)

```bash
uv venv
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
```

---

### 4. Install Dependencies

Install the project in editable mode along with its dependencies:

#### Using `pip`:
```bash
pip install -e .
pip install -r requirements.txt
```

#### Or using `uv`:
```bash
uv sync
```

---

### 5. Configure Environment Variables

Create your local `.env` configuration file from the template:

- **On Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```

- **On macOS / Linux**:
  ```bash
  cp .env.example .env
  ```

Open `.env` in your editor and set your Gemini API Key:
```env
GEMINI_API_KEY="your-actual-gemini-api-key"
GEMINI_MODEL="gemini-flash-lite-latest"
PORT=8000
HOST="0.0.0.0"
```

---

### 6. Initialize the SQLite Database

Initialize and seed the database with test products, regional warehouses, and inventory balances:

```bash
python main.py db
```
Output:
```
Database initialized successfully at: .../inventory.db
Database initialized successfully with test inventory.
```

---

### 7. Run the Application

The unified [`main.py`](main.py) CLI supports all modes:

#### A. Start the Web Server & Interactive Dashboard (Default)
```bash
python main.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser:
- **Interactive UI Dashboard**: Explore live stats, trigger orders, view agent traces, and inspect database tables.
- **Swagger API Documentation**: Visit **[http://localhost:8000/docs](http://localhost:8000/docs)** for interactive OpenAPI docs.
- **FastMCP Endpoint**: Hosted at **`http://localhost:8000/mcp`** for Model Context Protocol clients.

#### B. Run the Autonomous Multi-Agent Pipeline CLI
```bash
python main.py agent
```
Executes all 3 core fulfillment scenarios:
1. **In-Stock Order (Chicago)** &rarr; Dispatched with tracking `TRK-ORD-001` via `STANDARD_EXPRESS`.
2. **Out-of-Stock Exception (Seattle)** &rarr; Discovers alternative SKU `ITEM-203` and flags exception.
3. **Route Weather Exception (Denver)** &rarr; Identifies blizzard mountain blockage and recommends air rerouting.

#### C. Run the FastMCP Server in Standalone Stdio Mode
```bash
python main.py mcp
```
Connects external MCP clients.

---

### 8. Run the Automated Test Suite

Run the full pytest integration test suite:

```bash
pytest tests/
```

---