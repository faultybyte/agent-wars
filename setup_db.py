"""
Database initialization script for the Logistics System.
Initializes SQLite database 'inventory.db' populated with schema and test data.
"""

from database import init_db

if __name__ == "__main__":
    init_db(reset=True)
    print("Database initialized successfully with test inventory.")

