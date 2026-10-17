"""
FastAPI Backend with FastMCP Server and Autonomous ADK Agent Pipeline.
Provides REST API endpoints, mounted FastMCP protocol server, and an interactive dashboard.
"""

import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

try:
    from agent_wars.database import (
        init_db,
        list_products_db,
        list_inventory_db,
        list_orders_db,
        list_shipments_db,
        check_inventory_db,
    )
    from agent_wars.mcp_server import mcp
    from agent_wars.agent_handler import process_logistics_request
except ImportError:
    from database import (
        init_db,
        list_products_db,
        list_inventory_db,
        list_orders_db,
        list_shipments_db,
        check_inventory_db,
    )
    from mcp_server import mcp
    from agent_handler import process_logistics_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB on startup
    init_db(reset=False)
    yield


app = FastAPI(
    title="Autonomous Logistics Pipeline API",
    description="Google ADK Multi-Agent Logistics Orchestrator with FastMCP & SQLite Backend",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for external frontends or integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount FastMCP HTTP/SSE application directly onto FastAPI
try:
    mcp_app = mcp.http_app()
    app.mount("/mcp", mcp_app)
except Exception as e:
    print(f"Note: FastMCP mounting exception: {e}")


# =====================================================================
# Request / Response Models
# =====================================================================

class ProcessOrderRequest(BaseModel):
    prompt: Optional[str] = Field(None, description="Natural language prompt for the ADK orchestrator agent")
    order_id: Optional[str] = Field(None, description="Order identifier, e.g. ORD-001")
    sku: Optional[str] = Field(None, description="Product SKU, e.g. ITEM-101")
    destination: Optional[str] = Field(None, description="Destination city or state, e.g. Chicago")
    quantity: Optional[int] = Field(1, description="Quantity to order")
    session_id: Optional[str] = Field(None, description="Session ID for conversation persistence")


class McpCallRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the MCP tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments dictionary for the tool")


# =====================================================================
# REST Endpoints
# =====================================================================

@app.get("/api/health")
@app.get("/healthz")
@app.get("/livez")
async def health_check():
    """Health check endpoint reporting API, database, and MCP readiness."""
    try:
        products = list_products_db()
        db_status = "HEALTHY"
        products_count = len(products)
    except Exception as e:
        db_status = f"ERROR: {e}"
        products_count = 0

    return {
        "status": "ONLINE",
        "service": "Autonomous Logistics Pipeline",
        "database": db_status,
        "products_in_catalog": products_count,
        "mcp_mounted_path": "/mcp",
        "docs_url": "/docs"
    }


@app.get("/api/products")
async def get_products():
    """Retrieve master product catalog."""
    return list_products_db()


@app.get("/api/inventory")
async def get_inventory(sku: Optional[str] = None):
    """Retrieve inventory balances across warehouses, optionally filtered by SKU."""
    if sku:
        return check_inventory_db(sku)
    return list_inventory_db()


@app.get("/api/orders")
async def get_orders():
    """Retrieve order history and shipment statuses."""
    return list_orders_db()


@app.get("/api/shipments")
async def get_shipments():
    """Retrieve all dispatched shipments and tracking numbers."""
    return list_shipments_db()


@app.post("/api/orders/process")
async def process_order(req: ProcessOrderRequest):
    """
    Process an order through the Google ADK Autonomous Multi-Agent Pipeline.
    Supports either a natural language prompt or structured parameters.
    """
    if req.prompt:
        user_prompt = req.prompt.strip()
    elif req.order_id and req.sku and req.destination:
        qty_str = f" (quantity: {req.quantity})" if req.quantity and req.quantity > 1 else ""
        user_prompt = f"Process order #{req.order_id} for SKU {req.sku}{qty_str} to {req.destination}"
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'prompt' or ('order_id', 'sku', 'destination') must be provided."
        )

    result = await process_logistics_request(
        user_prompt=user_prompt,
        session_id=req.session_id
    )

    result["updated_orders"] = list_orders_db()
    result["updated_inventory"] = list_inventory_db()
    return result


@app.post("/api/mcp/call")
async def call_mcp_tool(req: McpCallRequest):
    """Directly invoke a registered FastMCP tool via HTTP."""
    tool_fn = getattr(mcp, "call_tool", None)
    if callable(tool_fn):
        try:
            res = await mcp.call_tool(req.tool_name, req.arguments)
            if hasattr(res, "content"):
                text_content = [item.text for item in res.content if hasattr(item, "text")]
                return {
                    "tool": req.tool_name,
                    "arguments": req.arguments,
                    "result_text": "\n".join(text_content),
                    "raw": str(res)
                }
            return {"tool": req.tool_name, "arguments": req.arguments, "result": str(res)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Tool call failed: {e}")
    else:
        raise HTTPException(status_code=500, detail="FastMCP call_tool is not available on this instance.")


@app.post("/api/db/reset")
async def reset_database():
    """Reset SQLite database with initial test dataset."""
    init_db(reset=True)
    return {
        "status": "SUCCESS",
        "message": "Database successfully reset with sample inventory and products.",
        "inventory": list_inventory_db()
    }


# =====================================================================
# Interactive UI Dashboard (Single-Page App)
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve rich interactive web dashboard for logistics control and agent monitoring."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Autonomous Logistics Agent Pipeline</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
    body { background-color: #0f172a; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .card { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
    .card-header { background-color: #1e293b; border-bottom: 1px solid #334155; font-weight: 600; }
    .btn-primary { background-color: #3b82f6; border-color: #3b82f6; }
    .btn-primary:hover { background-color: #2563eb; }
    .table { color: #f1f5f9; }
    .table-dark { background-color: #1e293b; }
    .badge-success { background-color: #10b981; }
    .badge-warning { background-color: #f59e0b; color: #1e293b; }
    .badge-danger { background-color: #ef4444; }
    .badge-info { background-color: #06b6d4; }
    pre { background-color: #090d16; color: #38bdf8; padding: 14px; border-radius: 8px; border: 1px solid #334155; max-height: 400px; overflow-y: auto; font-size: 0.88rem; }
    .stat-number { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .tool-chip { display: inline-block; padding: 3px 8px; margin: 2px; font-size: 0.75rem; border-radius: 4px; background: #334155; color: #94a3b8; }
    .nav-tabs .nav-link { color: #94a3b8; border: none; }
    .nav-tabs .nav-link.active { background: #1e293b; color: #38bdf8; border-bottom: 2px solid #38bdf8; }
  </style>
</head>
<body class="p-3 p-md-4">
  <div class="container-fluid max-w-7xl">
    <!-- Header -->
    <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
      <div>
        <h2 class="fw-bold mb-1"><i class="bi bi-robot text-primary me-2"></i>Autonomous Logistics Pipeline</h2>
        <p class="text-secondary mb-0">Google ADK Autonomous Multi-Agent Hierarchy &bull; FastMCP Protocol &bull; SQLite Database</p>
      </div>
      <div class="d-flex gap-2">
        <a href="/docs" target="_blank" class="btn btn-outline-info btn-sm"><i class="bi bi-journal-code me-1"></i>Swagger Docs</a>
        <button onclick="resetDb()" class="btn btn-outline-warning btn-sm"><i class="bi bi-arrow-counterclockwise me-1"></i>Reset DB</button>
        <button onclick="refreshData()" class="btn btn-outline-light btn-sm"><i class="bi bi-arrow-repeat me-1"></i>Refresh</button>
      </div>
    </div>

    <!-- Quick Stats -->
    <div class="row g-3 mb-4">
      <div class="col-6 col-md-3">
        <div class="card p-3">
          <div class="text-secondary small">Total Products</div>
          <div class="stat-number" id="stat-products">-</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card p-3">
          <div class="text-secondary small">Total Orders</div>
          <div class="stat-number" id="stat-orders">-</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card p-3">
          <div class="text-secondary small">Active Shipments</div>
          <div class="stat-number" id="stat-shipments">-</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="card p-3">
          <div class="text-secondary small">MCP Interface</div>
          <div class="stat-number text-success" style="font-size: 1.5rem;"><i class="bi bi-check-circle me-1"></i>Active</div>
        </div>
      </div>
    </div>

    <div class="row g-4">
      <!-- Left Column: Agent Execution -->
      <div class="col-lg-6">
        <div class="card">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span><i class="bi bi-cpu text-info me-2"></i>Order Execution (ADK Multi-Agent)</span>
            <span class="badge bg-primary">Google ADK</span>
          </div>
          <div class="card-body">
            <!-- Preset Quick Buttons -->
            <div class="mb-3">
              <label class="form-label small text-secondary">Quick Test Scenarios:</label>
              <div class="d-flex flex-wrap gap-2">
                <button onclick="setPrompt('Process order #ORD-001 for SKU ITEM-101 to Chicago')" class="btn btn-sm btn-outline-success">
                  <i class="bi bi-box-seam me-1"></i>In-Stock (Chicago)
                </button>
                <button onclick="setPrompt('Process order #ORD-002 for SKU ITEM-202 to Seattle')" class="btn btn-sm btn-outline-danger">
                  <i class="bi bi-exclamation-triangle me-1"></i>Out-of-Stock (Seattle)
                </button>
                <button onclick="setPrompt('Process order #ORD-003 for SKU ITEM-101 to Denver')" class="btn btn-sm btn-outline-warning">
                  <i class="bi bi-cloud-snow me-1"></i>Blizzard Exception (Denver)
                </button>
              </div>
            </div>

            <!-- Prompt Input -->
            <div class="mb-3">
              <label class="form-label small text-secondary">Natural Language Order Prompt:</label>
              <textarea id="prompt-input" rows="3" class="form-control bg-dark text-light border-secondary" placeholder="e.g. Process order #ORD-004 for SKU ITEM-101 to Atlanta"></textarea>
            </div>

            <div class="d-flex justify-content-between align-items-center mb-3">
              <span class="small text-secondary"><i class="bi bi-info-circle me-1"></i>Runs Orchestrator, InventoryAgent, DispatchAgent, ExceptionAgent</span>
              <button id="btn-submit" onclick="executeAgent()" class="btn btn-primary px-4">
                <span id="btn-spinner" class="spinner-border spinner-border-sm me-1 d-none"></span>
                <i class="bi bi-play-fill me-1"></i>Execute Order
              </button>
            </div>

            <!-- Agent Trace Log -->
            <div class="mt-4">
              <label class="form-label small text-secondary d-flex justify-content-between">
                <span>Agent Execution Trace & Tool Invocations:</span>
                <span id="exec-status" class="badge bg-secondary">Idle</span>
              </label>
              <pre id="trace-output">// Execution output and tool calls will appear here...</pre>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Database State & MCP -->
      <div class="col-lg-6">
        <ul class="nav nav-tabs mb-3" id="dataTabs" role="tablist">
          <li class="nav-item">
            <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-orders">Orders History</button>
          </li>
          <li class="nav-item">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-inventory">Warehouse Inventory</button>
          </li>
          <li class="nav-item">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-shipments">Shipments & Tracking</button>
          </li>
          <li class="nav-item">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-mcp">Direct MCP Tester</button>
          </li>
        </ul>

        <div class="tab-content">
          <!-- Orders Tab -->
          <div class="tab-pane fade show active" id="tab-orders">
            <div class="card p-3">
              <div class="table-responsive">
                <table class="table table-dark table-hover table-sm">
                  <thead>
                    <tr><th>Order #</th><th>Destination</th><th>Status</th><th>Tracking</th></tr>
                  </thead>
                  <tbody id="orders-table-body">
                    <tr><td colspan="4" class="text-center text-secondary">Loading orders...</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Inventory Tab -->
          <div class="tab-pane fade" id="tab-inventory">
            <div class="card p-3">
              <div class="table-responsive">
                <table class="table table-dark table-hover table-sm">
                  <thead>
                    <tr><th>SKU</th><th>Product Name</th><th>Warehouse</th><th>Stock</th></tr>
                  </thead>
                  <tbody id="inventory-table-body">
                    <tr><td colspan="4" class="text-center text-secondary">Loading inventory...</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Shipments Tab -->
          <div class="tab-pane fade" id="tab-shipments">
            <div class="card p-3">
              <div class="table-responsive">
                <table class="table table-dark table-hover table-sm">
                  <thead>
                    <tr><th>Order #</th><th>Tracking #</th><th>Carrier</th><th>Status</th><th>Destination</th></tr>
                  </thead>
                  <tbody id="shipments-table-body">
                    <tr><td colspan="5" class="text-center text-secondary">Loading shipments...</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Direct MCP Tester Tab -->
          <div class="tab-pane fade" id="tab-mcp">
            <div class="card p-3">
              <div class="mb-3">
                <label class="form-label small text-secondary">Select MCP Tool:</label>
                <select id="mcp-tool-select" class="form-select bg-dark text-light border-secondary mb-2" onchange="updateMcpArgsPlaceholder()">
                  <option value="check_inventory">check_inventory(sku)</option>
                  <option value="check_route_weather">check_route_weather(destination)</option>
                  <option value="suggest_alternatives">suggest_alternatives(sku)</option>
                  <option value="list_products">list_products()</option>
                  <option value="list_inventory">list_inventory()</option>
                  <option value="get_shipment_status">get_shipment_status(order_id)</option>
                </select>
                <label class="form-label small text-secondary">Arguments (JSON):</label>
                <textarea id="mcp-args-input" rows="2" class="form-control bg-dark text-light border-secondary">{"sku": "ITEM-101"}</textarea>
              </div>
              <button onclick="invokeMcpTool()" class="btn btn-outline-info btn-sm w-100 mb-3">Invoke MCP Tool</button>
              <pre id="mcp-output">// Tool results will appear here...</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    function setPrompt(text) {
      document.getElementById('prompt-input').value = text;
    }

    function updateMcpArgsPlaceholder() {
      const tool = document.getElementById('mcp-tool-select').value;
      const argsBox = document.getElementById('mcp-args-input');
      if (tool === 'check_inventory' || tool === 'suggest_alternatives') {
        argsBox.value = '{"sku": "ITEM-101"}';
      } else if (tool === 'check_route_weather') {
        argsBox.value = '{"destination": "Denver"}';
      } else if (tool === 'get_shipment_status') {
        argsBox.value = '{"order_id": "ORD-001"}';
      } else {
        argsBox.value = '{}';
      }
    }

    async function refreshData() {
      try {
        const [ordersRes, invRes, shipRes, prodRes] = await Promise.all([
          fetch('/api/orders').then(r => r.json()),
          fetch('/api/inventory').then(r => r.json()),
          fetch('/api/shipments').then(r => r.json()),
          fetch('/api/products').then(r => r.json())
        ]);

        document.getElementById('stat-products').innerText = prodRes.length || 0;
        document.getElementById('stat-orders').innerText = ordersRes.length || 0;
        document.getElementById('stat-shipments').innerText = shipRes.length || 0;

        const ordersBody = document.getElementById('orders-table-body');
        if (ordersRes.length === 0) {
          ordersBody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary">No orders recorded yet.</td></tr>';
        } else {
          ordersBody.innerHTML = ordersRes.map(o => `
            <tr>
              <td class="fw-bold">${o.order_number}</td>
              <td>${o.destination}</td>
              <td><span class="badge ${o.status === 'DISPATCHED' ? 'bg-success' : o.status === 'EXCEPTION' ? 'bg-danger' : 'bg-warning'}">${o.status}</span></td>
              <td><code>${o.tracking_number || '-'}</code></td>
            </tr>
          `).join('');
        }

        const invBody = document.getElementById('inventory-table-body');
        invBody.innerHTML = invRes.map(i => `
          <tr>
            <td><code>${i.sku}</code></td>
            <td>${i.product_name}</td>
            <td>${i.warehouse_code}</td>
            <td><span class="badge ${i.quantity > 0 ? 'bg-info' : 'bg-secondary'}">${i.quantity}</span></td>
          </tr>
        `).join('');

        const shipBody = document.getElementById('shipments-table-body');
        if (shipRes.length === 0) {
          shipBody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary">No active shipments.</td></tr>';
        } else {
          shipBody.innerHTML = shipRes.map(s => `
            <tr>
              <td>${s.order_number}</td>
              <td><code>${s.tracking_number}</code></td>
              <td>${s.carrier}</td>
              <td><span class="badge bg-success">${s.status}</span></td>
              <td>${s.destination}</td>
            </tr>
          `).join('');
        }
      } catch (e) {
        console.error("Error refreshing data:", e);
      }
    }

    async function executeAgent() {
      const prompt = document.getElementById('prompt-input').value.trim();
      if (!prompt) {
        alert("Please enter or select an order prompt.");
        return;
      }

      const btn = document.getElementById('btn-submit');
      const spinner = document.getElementById('btn-spinner');
      const statusBadge = document.getElementById('exec-status');
      const trace = document.getElementById('trace-output');

      btn.disabled = true;
      spinner.classList.remove('d-none');
      statusBadge.className = 'badge bg-warning text-dark';
      statusBadge.innerText = 'Agent Running...';
      trace.innerText = `[Initiating ADK Multi-Agent Execution]...\nPrompt: "${prompt}"\n`;

      try {
        const res = await fetch('/api/orders/process', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: prompt })
        });
        const data = await res.json();

        statusBadge.className = data.status === 'SUCCESS' ? 'badge bg-success' : 'badge bg-danger';
        statusBadge.innerText = data.status;

        let log = `=== RESULT STATUS: ${data.status} (Model: ${data.model_used || 'ADK Default'}) ===\n\n`;
        if (data.tool_calls && data.tool_calls.length > 0) {
          log += "--- TOOLS CALLED BY AGENTS ---\n";
          data.tool_calls.forEach(tc => {
            log += `> [${tc.agent}] ${tc.tool}(${JSON.stringify(tc.args)})\n`;
          });
          log += "\n";
        }
        log += "--- FINAL AGENT SUMMARY ---\n" + data.final_response;
        trace.innerText = log;
        refreshData();
      } catch (err) {
        statusBadge.className = 'badge bg-danger';
        statusBadge.innerText = 'Error';
        trace.innerText = `Error processing order: ${err}`;
      } finally {
        btn.disabled = false;
        spinner.classList.add('d-none');
      }
    }

    async function invokeMcpTool() {
      const toolName = document.getElementById('mcp-tool-select').value;
      const argsRaw = document.getElementById('mcp-args-input').value;
      const outBox = document.getElementById('mcp-output');

      let args = {};
      try {
        args = JSON.parse(argsRaw);
      } catch (e) {
        alert("Invalid JSON arguments.");
        return;
      }

      outBox.innerText = `Calling MCP tool '${toolName}'...`;
      try {
        const res = await fetch('/api/mcp/call', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool_name: toolName, arguments: args })
        });
        const data = await res.json();
        outBox.innerText = JSON.stringify(data, null, 2);
      } catch (e) {
        outBox.innerText = `MCP Invocation Error: ${e}`;
      }
    }

    async function resetDb() {
      if (!confirm("Reset database to initial test state?")) return;
      await fetch('/api/db/reset', { method: 'POST' });
      alert("Database reset successfully.");
      refreshData();
    }

    setPrompt('Process order #ORD-001 for SKU ITEM-101 to Chicago');
    refreshData();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


def main() -> None:
    """Run server from CLI."""
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Launching Autonomous Logistics Pipeline on http://{host}:{port}")
    uvicorn.run("agent_wars.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

