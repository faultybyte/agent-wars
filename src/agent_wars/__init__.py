"""
Package entrypoint for agent-wars.
Launches the FastAPI backend and FastMCP server.
"""

import sys
import uvicorn


def main() -> None:
    """CLI entrypoint to run the Logistics Pipeline backend."""
    port = 8000
    host = "0.0.0.0"
    print(f"Starting Autonomous Logistics Agent Backend on http://localhost:{port}...")
    uvicorn.run("api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
