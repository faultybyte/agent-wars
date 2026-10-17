"""
Database initialization script for the Logistics System.
Initializes SQLite database populated with schema and test data.
"""

try:
    from agent_wars.database import init_db
except ImportError:
    from database import init_db

if __name__ == "__main__":
    init_db(reset=True)
    print("Database initialized successfully with test inventory.")

