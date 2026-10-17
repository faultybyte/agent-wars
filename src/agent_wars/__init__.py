"""
Autonomous Logistics Agent Package.
Google ADK Multi-Agent Orchestration + FastMCP Protocol + FastAPI Backend.
"""

from agent_wars.database import init_db
from agent_wars.mcp_server import mcp
from agent_wars.agent_handler import (
    orchestrator,
    inventory_agent,
    dispatch_agent,
    exception_agent,
    process_logistics_request,
)
from agent_wars.api import app, main

__all__ = [
    "app",
    "mcp",
    "orchestrator",
    "inventory_agent",
    "dispatch_agent",
    "exception_agent",
    "process_logistics_request",
    "init_db",
    "main",
]
