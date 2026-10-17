"""
FastMCP Server for Logistics Operations.
Exposes logistics tools over the Model Context Protocol (MCP) as specified in context.txt.
"""

import json
from typing import Any, Dict, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

try:
    from agent_wars.database import (
        check_inventory_db,
        dispatch_order_db,
        find_alternative_products_db,
        flag_order_exception_db,
        list_inventory_db,
        list_orders_db,
        list_products_db,
        list_shipments_db,
    )
except ImportError:
    from database import (
        check_inventory_db,
        dispatch_order_db,
        find_alternative_products_db,
        flag_order_exception_db,
        list_inventory_db,
        list_orders_db,
        list_products_db,
        list_shipments_db,
    )

# Initialize FastMCP server instance
mcp = FastMCP("Logistics-MCP-Server")


@mcp.tool()
def check_inventory(sku: str) -> str:
    """Check stock availability for a given item SKU across all warehouses."""
    result = check_inventory_db(sku)
    return json.dumps(result, indent=2)


@mcp.tool()
def check_route_weather(destination: str) -> str:
    """Check weather and road transit conditions for a shipping destination."""
    dest_lower = destination.lower()
    if "denver" in dest_lower or "blizzard" in dest_lower or "aspen" in dest_lower:
        result = {
            "destination": destination,
            "status": "BLOCKED",
            "passable": False,
            "weather": "Severe Winter Storm / Heavy Blizzard",
            "hazard": "Interstate transit corridor closed to freight trucks",
            "recommendation": "Flag order exception and reroute via Southern Air Hub or delay dispatch"
        }
    elif "miami" in dest_lower or "hurricane" in dest_lower:
        result = {
            "destination": destination,
            "status": "WARNING",
            "passable": True,
            "weather": "Tropical Storm Watch",
            "hazard": "Potential 24-48h road transit delay",
            "recommendation": "Assign expedited air carrier AIR_EXPRESS_PRIORITY"
        }
    else:
        result = {
            "destination": destination,
            "status": "CLEAR",
            "passable": True,
            "weather": "Clear / Mild",
            "hazard": "None",
            "recommendation": "STANDARD_EXPRESS ground dispatch optimal"
        }
    return json.dumps(result, indent=2)


@mcp.tool()
def dispatch_order(
    order_id: str,
    sku: str,
    destination: str,
    quantity: int = 1,
    carrier: str = "STANDARD_EXPRESS"
) -> str:
    """Book transport, allocate stock, and record dispatch for an order."""
    result = dispatch_order_db(
        order_id=order_id,
        sku=sku,
        destination=destination,
        quantity=quantity,
        carrier=carrier
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def suggest_alternatives(sku: str) -> str:
    """Find alternative items or inter-warehouse transfers when an item is out of stock."""
    result = find_alternative_products_db(sku)
    return json.dumps(result, indent=2)


@mcp.tool()
def flag_order_exception(
    order_id: str,
    destination: str,
    reason: str,
    alternative_suggestion: str
) -> str:
    """Flag an order with EXCEPTION status and record the suggested alternative."""
    result = flag_order_exception_db(
        order_id=order_id,
        destination=destination,
        reason=reason,
        alternative_suggestion=alternative_suggestion
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def list_products() -> str:
    """List all products in the master catalog."""
    products = list_products_db()
    return json.dumps(products, indent=2)


@mcp.tool()
def list_inventory() -> str:
    """List current stock balances across all warehouses."""
    inv = list_inventory_db()
    return json.dumps(inv, indent=2)


@mcp.tool()
def get_shipment_status(order_id: str) -> str:
    """Look up shipment and dispatch status for an order."""
    shipments = list_shipments_db()
    matching = [s for s in shipments if s.get("order_number") == order_id]
    if matching:
        return json.dumps(matching[0], indent=2)
    return json.dumps({"order_id": order_id, "status": "NOT_FOUND"}, indent=2)


if __name__ == "__main__":
    print("Starting Logistics-MCP-Server...")
    mcp.run()

