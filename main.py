"""
Single CLI and server entrypoint for the Autonomous Logistics Agent.

Usage:
  python main.py          # Start the FastAPI server & web dashboard (default)
  python main.py agent    # Run the autonomous ADK multi-agent pipeline
  python main.py mcp      # Run the FastMCP server in standalone stdio mode
  python main.py db       # Initialize/reset the SQLite test database
"""

import sys
import asyncio


def run_server():
    from agent_wars.api import main as server_main
    server_main()


def run_agent():
    from agent_wars.agent_handler import main as agent_main
    asyncio.run(agent_main())


def run_mcp():
    from agent_wars.mcp_server import mcp
    print("Starting FastMCP server in stdio mode...")
    mcp.run()


def run_db():
    from agent_wars.setup_db import init_db
    init_db(reset=True)
    print("Database initialized successfully with test inventory.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower().strip()
        if cmd in ("agent", "test", "run"):
            run_agent()
        elif cmd in ("mcp", "server"):
            run_mcp()
        elif cmd in ("db", "init", "setup"):
            run_db()
        elif cmd in ("api", "web", "start"):
            run_server()
        else:
            print(f"Unknown command: '{cmd}'. Running default server...")
            run_server()
    else:
        run_server()
