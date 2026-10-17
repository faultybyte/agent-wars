# Autonomous Logistics Agent Pipeline (Google ADK + FastMCP + FastAPI)

An end-to-end autonomous logistics orchestration system built with the **Google Agent Development Kit (ADK)**, **FastMCP (Model Context Protocol)**, **FastAPI**, and **SQLite**.

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

1. **Autonomous ADK Agent (`agent_handler.py`)**:
   - `LogisticsOrchestrator`: Main root agent coordinating the logistics workflow.
   - `InventoryAgent`: Sub-agent verifying catalog stock and warehouse quantities.
   - `DispatchAgent`: Sub-agent planning route feasibility, transit weather checks, and carrier booking.
   - `ExceptionAgent`: Sub-agent handling stock shortages, alternative SKU discovery, and route blockage rerouting.

2. **FastMCP Server (`mcp_server.py`)**:
   - Exposes tools via Model Context Protocol:
     - `check_inventory(sku)`
     - `check_route_weather(destination)`
     - `dispatch_order(order_id, sku, destination, quantity, carrier)`
     - `suggest_alternatives(sku)`
     - `flag_order_exception(order_id, destination, reason, alternative_suggestion)`
     - `list_products()`
     - `list_inventory()`
     - `get_shipment_status(order_id)`

3. **FastAPI Web Backend & Dashboard (`api.py`)**:
   - REST API endpoints (`/api/orders/process`, `/api/orders`, `/api/inventory`, `/api/products`, `/api/shipments`, `/api/health`).
   - FastMCP server mounted at `/mcp`.
   - Healthcheck & probe endpoints: `/api/health`, `/healthz`, `/livez`.
   - Swagger OpenAPI interactive documentation at `/docs`.
   - Rich real-time Single Page Application dashboard served at `/`.

4. **Relational Database (`database.py` / `inventory.db`)**:
   - Tables: `products`, `warehouses`, `inventory`, `orders`, `order_items`, `shipments`.
   - Configurable storage path via `DATABASE_PATH` for persistent volume mounts.

---

## Local Development Quickstart

### 1. Environment Setup

Ensure virtual environment `.venv` is activated:
```bash
# On Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

Set your Gemini API Key in `.env`:
```env
GEMINI_API_KEY="your-api-key"
```

### 2. Initialize Database

```bash
python setup_db.py
```

### 3. Run Autonomous Agent Test Pipeline

```bash
python agent_handler.py
```

Runs all 3 core test cases:
1. In-stock order (Chicago) &rarr; Dispatched with carrier and tracking number.
2. Out-of-stock order (Seattle) &rarr; Flagged exception with alternative item recommendation.
3. Route weather exception (Denver) &rarr; Flagged exception with air reroute recommendation.

### 4. Start the FastAPI Server & Web Dashboard

```bash
python main.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to view the interactive dashboard, trigger orders, inspect database tables, and view agent trace logs.

### 5. Run FastMCP Standalone (Stdio mode)

```bash
python mcp_server.py
```