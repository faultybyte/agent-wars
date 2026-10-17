"""
Database module for the Logistics Agent system.
Implements the relational schema specified in context.txt using SQLite.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow database path to be overridden via environment variable
DB_PATH = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent.parent.parent / "inventory.db")))


def get_db_connection() -> sqlite3.Connection:
    """Return a database connection with Row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(reset: bool = False) -> None:
    """Initialize the SQLite database with tables and sample data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if reset:
        cursor.executescript("""
        DROP TABLE IF EXISTS shipments;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS inventory;
        DROP TABLE IF EXISTS warehouses;
        DROP TABLE IF EXISTS products;
        """)

    cursor.executescript("""
    -- 1. Master Product Catalog
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        unit_price REAL DEFAULT 0.00,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 2. Warehouse Locations
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        location TEXT NOT NULL
    );

    -- 3. Inventory Balances
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        warehouse_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE,
        UNIQUE(product_id, warehouse_id)
    );

    -- 4. Customer / System Orders
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        destination TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 5. Items in an Order
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    );

    -- 6. Dispatch & Tracking Records
    CREATE TABLE IF NOT EXISTS shipments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER UNIQUE NOT NULL,
        warehouse_id INTEGER NOT NULL,
        tracking_number TEXT UNIQUE NOT NULL,
        carrier TEXT NOT NULL DEFAULT 'STANDARD_EXPRESS',
        status TEXT NOT NULL DEFAULT 'IN_TRANSIT',
        dispatched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE RESTRICT
    );

    -- Seed Base Catalog
    INSERT OR IGNORE INTO products (sku, name, description, unit_price) VALUES
        ('ITEM-101', 'Industrial Widget A', 'Standard high-grade industrial widget', 29.99),
        ('ITEM-102', 'Industrial Widget A (V2)', 'Compatible upgraded widget alternative', 34.50),
        ('ITEM-202', 'Precision Bolt B', 'Precision engineered structural bolt', 4.50),
        ('ITEM-203', 'Precision Bolt B - Heavy Duty', 'Heavy-duty certified alternative for ITEM-202', 5.20);

    -- Seed Warehouses
    INSERT OR IGNORE INTO warehouses (code, name, location) VALUES
        ('WH-EAST', 'East Coast Distribution Center', 'New York, NY'),
        ('WH-MIDWEST', 'Midwest Hub', 'Chicago, IL'),
        ('WH-WEST', 'West Coast Fulfillment Center', 'Seattle, WA');

    -- Seed Inventory
    -- Product 1 (ITEM-101) in WH-EAST: 50 in stock
    INSERT OR IGNORE INTO inventory (product_id, warehouse_id, quantity)
    SELECT p.id, w.id, 50 FROM products p, warehouses w WHERE p.sku = 'ITEM-101' AND w.code = 'WH-EAST';

    -- Product 2 (ITEM-102) in WH-EAST: 30 in stock
    INSERT OR IGNORE INTO inventory (product_id, warehouse_id, quantity)
    SELECT p.id, w.id, 30 FROM products p, warehouses w WHERE p.sku = 'ITEM-102' AND w.code = 'WH-EAST';

    -- Product 3 (ITEM-202) in WH-EAST: 0 in stock (out of stock as specified)
    INSERT OR IGNORE INTO inventory (product_id, warehouse_id, quantity)
    SELECT p.id, w.id, 0 FROM products p, warehouses w WHERE p.sku = 'ITEM-202' AND w.code = 'WH-EAST';

    -- Product 4 (ITEM-203) in WH-EAST: 25 in stock (available alternative for ITEM-202)
    INSERT OR IGNORE INTO inventory (product_id, warehouse_id, quantity)
    SELECT p.id, w.id, 25 FROM products p, warehouses w WHERE p.sku = 'ITEM-203' AND w.code = 'WH-EAST';
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully at:", DB_PATH)


def check_inventory_db(sku: str) -> Dict[str, Any]:
    """Query inventory levels for a SKU across warehouses."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT p.id AS product_id, p.sku, p.name, p.unit_price,
           w.code AS warehouse_code, w.name AS warehouse_name, w.location,
           COALESCE(i.quantity, 0) AS quantity
    FROM products p
    LEFT JOIN inventory i ON p.id = i.product_id
    LEFT JOIN warehouses w ON i.warehouse_id = w.id
    WHERE p.sku = ?
    """, (sku,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            "sku": sku,
            "found": False,
            "in_stock": False,
            "total_quantity": 0,
            "warehouses": [],
            "message": f"Product SKU '{sku}' not found in catalog."
        }

    total_qty = sum(r["quantity"] for r in rows if r["quantity"] is not None)
    warehouse_breakdown = [
        {
            "warehouse_code": r["warehouse_code"],
            "warehouse_name": r["warehouse_name"],
            "location": r["location"],
            "quantity": r["quantity"]
        }
        for r in rows if r["warehouse_code"] is not None
    ]

    return {
        "sku": sku,
        "found": True,
        "product_name": rows[0]["name"],
        "unit_price": rows[0]["unit_price"],
        "in_stock": total_qty > 0,
        "total_quantity": total_qty,
        "warehouses": warehouse_breakdown
    }


def find_alternative_products_db(sku: str) -> Dict[str, Any]:
    """Find available alternatives or inter-warehouse stock for an out-of-stock SKU."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Look for items in stock in other warehouses for the same SKU
    cursor.execute("""
    SELECT w.code, w.name, w.location, i.quantity
    FROM products p
    JOIN inventory i ON p.id = i.product_id
    JOIN warehouses w ON i.warehouse_id = w.id
    WHERE p.sku = ? AND i.quantity > 0
    """, (sku,))
    other_warehouses = [dict(r) for r in cursor.fetchall()]

    # Look for compatible alternative SKUs
    alternatives = []
    if "ITEM-202" in sku:
        alt_sku = "ITEM-203"
    elif "ITEM-101" in sku:
        alt_sku = "ITEM-102"
    else:
        alt_sku = None

    if alt_sku:
        cursor.execute("""
        SELECT p.sku, p.name, p.unit_price, w.code as warehouse_code, i.quantity
        FROM products p
        JOIN inventory i ON p.id = i.product_id
        JOIN warehouses w ON i.warehouse_id = w.id
        WHERE p.sku = ? AND i.quantity > 0
        """, (alt_sku,))
        alternatives = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "requested_sku": sku,
        "stock_in_other_warehouses": other_warehouses,
        "recommended_alternatives": alternatives
    }


def dispatch_order_db(
    order_id: str,
    sku: str,
    destination: str,
    quantity: int = 1,
    carrier: str = "STANDARD_EXPRESS",
    preferred_warehouse: Optional[str] = None
) -> Dict[str, Any]:
    """
    Book transport, deduct stock, update order and shipments in SQLite database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, name FROM products WHERE sku = ?", (sku,))
        prod = cursor.fetchone()
        if not prod:
            return {"status": "FAILED", "reason": f"Product SKU {sku} does not exist"}

        product_id = prod["id"]

        if preferred_warehouse:
            cursor.execute("""
            SELECT i.id, i.warehouse_id, i.quantity, w.code, w.name
            FROM inventory i
            JOIN warehouses w ON i.warehouse_id = w.id
            WHERE i.product_id = ? AND w.code = ? AND i.quantity >= ?
            """, (product_id, preferred_warehouse, quantity))
        else:
            cursor.execute("""
            SELECT i.id, i.warehouse_id, i.quantity, w.code, w.name
            FROM inventory i
            JOIN warehouses w ON i.warehouse_id = w.id
            WHERE i.product_id = ? AND i.quantity >= ?
            ORDER BY i.quantity DESC LIMIT 1
            """, (product_id, quantity))

        inv = cursor.fetchone()
        if not inv:
            cursor.execute("""
            INSERT INTO orders (order_number, destination, status)
            VALUES (?, ?, 'OUT_OF_STOCK')
            ON CONFLICT(order_number) DO UPDATE SET status = 'OUT_OF_STOCK'
            """, (order_id, destination))
            conn.commit()
            return {
                "status": "FAILED",
                "reason": f"Insufficient stock for SKU {sku}. Quantity requested: {quantity}",
                "order_id": order_id
            }

        inv_id = inv["id"]
        warehouse_id = inv["warehouse_id"]
        warehouse_code = inv["code"]
        current_qty = inv["quantity"]

        new_qty = current_qty - quantity
        cursor.execute("UPDATE inventory SET quantity = ? WHERE id = ?", (new_qty, inv_id))

        cursor.execute("""
        INSERT INTO orders (order_number, destination, status)
        VALUES (?, ?, 'DISPATCHED')
        ON CONFLICT(order_number) DO UPDATE SET destination = ?, status = 'DISPATCHED'
        """, (order_id, destination, destination))

        cursor.execute("SELECT id FROM orders WHERE order_number = ?", (order_id,))
        order_db_id = cursor.fetchone()["id"]

        cursor.execute("""
        INSERT INTO order_items (order_id, product_id, quantity)
        VALUES (?, ?, ?)
        """, (order_db_id, product_id, quantity))

        tracking_number = f"TRK-{order_id}"
        cursor.execute("""
        INSERT INTO shipments (order_id, warehouse_id, tracking_number, carrier, status)
        VALUES (?, ?, ?, ?, 'IN_TRANSIT')
        ON CONFLICT(order_id) DO UPDATE SET tracking_number = ?, carrier = ?, status = 'IN_TRANSIT'
        """, (order_db_id, warehouse_id, tracking_number, carrier, tracking_number, carrier))

        conn.commit()

        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "sku": sku,
            "quantity": quantity,
            "destination": destination,
            "warehouse": warehouse_code,
            "carrier": carrier,
            "tracking_number": tracking_number,
            "remaining_stock": new_qty
        }
    except Exception as e:
        conn.rollback()
        return {"status": "ERROR", "reason": str(e), "order_id": order_id}
    finally:
        conn.close()


def flag_order_exception_db(
    order_id: str,
    destination: str,
    reason: str,
    alternative_suggestion: str
) -> Dict[str, Any]:
    """Flag an order with EXCEPTION status and record reason."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO orders (order_number, destination, status)
    VALUES (?, ?, 'EXCEPTION')
    ON CONFLICT(order_number) DO UPDATE SET destination = ?, status = 'EXCEPTION'
    """, (order_id, destination, destination))
    conn.commit()
    conn.close()

    return {
        "status": "EXCEPTION_RECORDED",
        "order_id": order_id,
        "destination": destination,
        "reason": reason,
        "alternative_suggestion": alternative_suggestion
    }


def list_products_db() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def list_inventory_db() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT i.id, p.sku, p.name as product_name, w.code as warehouse_code,
           w.name as warehouse_name, w.location, i.quantity, i.updated_at
    FROM inventory i
    JOIN products p ON i.product_id = p.id
    JOIN warehouses w ON i.warehouse_id = w.id
    ORDER BY p.sku, w.code
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def list_orders_db() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT o.id, o.order_number, o.destination, o.status, o.created_at,
           s.tracking_number, s.carrier, s.status as shipment_status
    FROM orders o
    LEFT JOIN shipments s ON o.id = s.order_id
    ORDER BY o.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def list_shipments_db() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.id, o.order_number, w.code as origin_warehouse, s.tracking_number,
           s.carrier, s.status, s.dispatched_at, o.destination
    FROM shipments s
    JOIN orders o ON s.order_id = o.id
    JOIN warehouses w ON s.warehouse_id = w.id
    ORDER BY s.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


if __name__ == "__main__":
    init_db(reset=True)

