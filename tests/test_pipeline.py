"""
Unit and integration tests for the Autonomous Logistics Pipeline.
"""

import pytest
from fastapi.testclient import TestClient

from agent_wars.database import (
    init_db,
    check_inventory_db,
    find_alternative_products_db,
    dispatch_order_db,
    flag_order_exception_db,
    list_products_db,
    list_inventory_db,
    list_orders_db,
)
from agent_wars.mcp_server import mcp, check_route_weather
from agent_wars.api import app


@pytest.fixture(autouse=True)
def setup_database():
    """Reset database to fresh seed state before tests."""
    init_db(reset=True)


def test_database_inventory_and_alternatives():
    """Verify stock lookup and alternative recommendation logic."""
    item101 = check_inventory_db("ITEM-101")
    assert item101["found"] is True
    assert item101["in_stock"] is True
    assert item101["total_quantity"] == 50

    item202 = check_inventory_db("ITEM-202")
    assert item202["found"] is True
    assert item202["in_stock"] is False
    assert item202["total_quantity"] == 0

    alts = find_alternative_products_db("ITEM-202")
    rec_skus = [a["sku"] for a in alts["recommended_alternatives"]]
    assert "ITEM-203" in rec_skus


def test_database_dispatch_and_exception():
    """Verify order dispatch and exception recording in SQLite."""
    res = dispatch_order_db("TEST-001", "ITEM-101", "Chicago", quantity=1)
    assert res["status"] == "SUCCESS"
    assert res["tracking_number"] == "TRK-TEST-001"
    assert res["remaining_stock"] == 49

    exc = flag_order_exception_db("TEST-002", "Denver", "Blizzard", "Hold dispatch")
    assert exc["status"] == "EXCEPTION_RECORDED"

    orders = list_orders_db()
    order_nums = [o["order_number"] for o in orders]
    assert "TEST-001" in order_nums
    assert "TEST-002" in order_nums


def test_mcp_tools():
    """Verify FastMCP tools work as expected."""
    weather_clear = check_route_weather("Chicago")
    assert "CLEAR" in weather_clear
    assert "STANDARD_EXPRESS" in weather_clear

    weather_blocked = check_route_weather("Denver")
    assert "BLOCKED" in weather_blocked


def test_fastapi_endpoints():
    """Verify FastAPI endpoints and health probes."""
    client = TestClient(app)

    res_health = client.get("/healthz")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ONLINE"

    res_prods = client.get("/api/products")
    assert res_prods.status_code == 200
    assert len(res_prods.json()) >= 2

    res_inv = client.get("/api/inventory")
    assert res_inv.status_code == 200
    assert len(res_inv.json()) >= 2

