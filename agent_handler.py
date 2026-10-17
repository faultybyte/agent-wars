"""
Google ADK Agent Handler for Logistics Orchestration.
Orchestrates autonomous multi-agent logistics workflows matching context.txt.
Uses Google ADK LlmAgent, InMemorySessionService, and Runner.
"""

import asyncio
import os
import re
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow._retry_config import RetryConfig
from google.genai import types

from database import (
    check_inventory_db,
    dispatch_order_db,
    find_alternative_products_db,
    flag_order_exception_db,
    init_db,
)

# Active Gemini Models with automatic resilient fallback
PREFERRED_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
FALLBACK_MODELS = [
    PREFERRED_MODEL,
    "gemini-3.1-flash-lite-preview",
    "gemini-3.5-flash"
]
# Remove duplicates while preserving order
FALLBACK_MODELS = list(dict.fromkeys(FALLBACK_MODELS))
AGENT_RETRY = RetryConfig(max_attempts=3, initial_delay=2.0, backoff_factor=2.0)


# =====================================================================
# 1. Direct Agent Tools Matching MCP Capabilities
# =====================================================================

def tool_check_inventory(sku: str) -> dict:
    """
    Check stock availability and quantities for a given item SKU across all warehouses.
    Returns whether the SKU is in stock, total quantity, and per-warehouse breakdown.
    """
    return check_inventory_db(sku)


def tool_check_route_weather(destination: str) -> dict:
    """
    Check weather and freight transport feasibility for a shipping destination.
    Identifies hazardous weather conditions, road closures, and carrier recommendations.
    """
    dest_lower = destination.lower()
    if "denver" in dest_lower or "blizzard" in dest_lower or "aspen" in dest_lower:
        return {
            "destination": destination,
            "status": "BLOCKED",
            "passable": False,
            "weather": "Severe Winter Storm / Heavy Blizzard Warning",
            "hazard": "Interstate mountain transit corridor closed to freight trucks",
            "recommendation": "Flag order exception and reroute via Southern Air Hub or delay road dispatch"
        }
    elif "miami" in dest_lower or "hurricane" in dest_lower:
        return {
            "destination": destination,
            "status": "WARNING",
            "passable": True,
            "weather": "Tropical Storm Alert",
            "hazard": "Potential 24-48h road transit delay",
            "recommendation": "Assign expedited carrier AIR_EXPRESS_PRIORITY"
        }
    else:
        return {
            "destination": destination,
            "status": "CLEAR",
            "passable": True,
            "weather": "Clear / Favorable transit conditions",
            "hazard": "None",
            "recommendation": "STANDARD_EXPRESS ground dispatch optimal"
        }


def tool_dispatch_order(
    order_id: str,
    sku: str,
    destination: str,
    quantity: int = 1,
    carrier: str = "STANDARD_EXPRESS"
) -> dict:
    """
    Book transport, deduct stock from warehouse inventory, and record shipment.
    Returns status, tracking number, carrier, and remaining inventory.
    """
    return dispatch_order_db(
        order_id=order_id,
        sku=sku,
        destination=destination,
        quantity=quantity,
        carrier=carrier
    )


def tool_find_alternatives(sku: str) -> dict:
    """
    Look for alternative products in stock or stock available in other regional warehouses.
    Used when a requested SKU is out of stock at the primary warehouse.
    """
    return find_alternative_products_db(sku)


def tool_flag_order_exception(
    order_id: str,
    destination: str,
    reason: str,
    alternative_suggestion: str
) -> dict:
    """
    Flag an order in the database with EXCEPTION status and record the suggested alternative.
    """
    return flag_order_exception_db(
        order_id=order_id,
        destination=destination,
        reason=reason,
        alternative_suggestion=alternative_suggestion
    )


# =====================================================================
# 2. Agent Factory with Configurable Model
# =====================================================================

def build_logistics_agent(model_name: str) -> LlmAgent:
    """Build the multi-agent hierarchy with the given Gemini model."""
    inventory_agent = LlmAgent(
        name="InventoryAgent",
        model=model_name,
        description="Specialized agent for stock checks and inventory balances.",
        instruction=(
            "You verify stock availability. Call tool_check_inventory when asked. "
            "Report stock status, quantities, and warehouse availability clearly."
        ),
        tools=[tool_check_inventory],
        retry_config=AGENT_RETRY
    )

    dispatch_agent = LlmAgent(
        name="DispatchAgent",
        model=model_name,
        description="Specialized agent for route planning, transit weather check, and shipment dispatch.",
        instruction=(
            "You organize shipping and dispatch. First verify route weather using tool_check_route_weather. "
            "If clear or passable, call tool_dispatch_order to book transport and record the shipment. "
            "If blocked, report the weather hazard."
        ),
        tools=[tool_check_route_weather, tool_dispatch_order],
        retry_config=AGENT_RETRY
    )

    exception_agent = LlmAgent(
        name="ExceptionAgent",
        model=model_name,
        description="Specialized agent for resolving stockouts, weather route blockages, and customer alternatives.",
        instruction=(
            "You handle exceptions when stock is unavailable or routes are blocked. "
            "Call tool_find_alternatives to discover alternate items or warehouse transfers, "
            "and flag the exception in the database using tool_flag_order_exception."
        ),
        tools=[tool_find_alternatives, tool_flag_order_exception],
        retry_config=AGENT_RETRY
    )

    orchestrator = LlmAgent(
        name="LogisticsOrchestrator",
        model=model_name,
        description="Master logistics orchestrator coordinating inventory, dispatch, routing, and exception resolution.",
        instruction=(
            "You are the master Logistics Orchestrator managing logistics fulfillment: "
            "1. First check inventory availability using tool_check_inventory. "
            "2. If in stock: Check destination weather using tool_check_route_weather. "
            "   - If route is passable, book shipment using tool_dispatch_order and assign carrier. "
            "   - If route is BLOCKED by severe weather, call tool_flag_order_exception and recommend alternative scheduling or rerouting. "
            "3. If out of stock: Call tool_find_alternatives to identify compatible items or stock transfers, "
            "   call tool_flag_order_exception, and provide actionable recommendations to the user. "
            "Always summarize the final outcome clearly with Order ID, SKU, Destination, Carrier, and Tracking Number (or exception details)."
        ),
        tools=[tool_check_inventory, tool_check_route_weather, tool_dispatch_order, tool_find_alternatives, tool_flag_order_exception],
        sub_agents=[inventory_agent, dispatch_agent, exception_agent],
        retry_config=AGENT_RETRY
    )

    return orchestrator


# =====================================================================
# 3. Runner & Pipeline Execution Setup
# =====================================================================

_session_service = InMemorySessionService()


def get_logistics_runner(model_name: str) -> Runner:
    """Create an ADK Runner initialized with the LogisticsOrchestrator agent."""
    agent = build_logistics_agent(model_name)
    return Runner(
        agent=agent,
        app_name="SimpleLogistics",
        session_service=_session_service,
        auto_create_session=True
    )


async def process_logistics_request(
    user_prompt: str,
    session_id: Optional[str] = None,
    user_id: str = "warehouse_manager"
) -> Dict[str, Any]:
    """
    Process an incoming logistics request through the Google ADK Autonomous Agent pipeline.
    Tries preferred model and automatically fails over if a model quota limit is reached.
    """
    if not session_id:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

    print(f"\n=======================================================")
    print(f"--- Processing Logistics Request: '{user_prompt}' ---")
    print(f"Session: {session_id} | User: {user_id}")
    print(f"=======================================================")

    last_error = ""

    for model_name in FALLBACK_MODELS:
        print(f"--> Attempting execution with model: '{model_name}'")
        runner = get_logistics_runner(model_name)
        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)]
        )

        tool_calls = []
        tool_responses = []
        messages = []
        final_output_parts = []

        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
            ):
                # Capture tool calls
                if hasattr(event, "get_function_calls") and callable(event.get_function_calls):
                    calls = event.get_function_calls()
                    if calls:
                        for c in calls:
                            tool_calls.append({
                                "agent": event.author or "unknown",
                                "tool": c.name,
                                "args": c.args
                            })
                            print(f"  [Tool Call] {event.author} -> {c.name}({c.args})")

                # Capture tool responses
                if hasattr(event, "get_function_responses") and callable(event.get_function_responses):
                    resps = event.get_function_responses()
                    if resps:
                        for r in resps:
                            tool_responses.append({
                                "agent": event.author or "unknown",
                                "tool": r.name,
                                "response": r.response
                            })
                            print(f"  [Tool Response] {r.name}: {r.response}")

                # Capture model text content
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            messages.append({
                                "author": event.author,
                                "text": part.text
                            })
                            is_final = False
                            if hasattr(event, "is_final_response") and callable(event.is_final_response):
                                is_final = event.is_final_response()

                            if is_final or event.author == "LogisticsOrchestrator":
                                final_output_parts.append(part.text)

            # Assemble final text response
            if final_output_parts:
                final_text = "\n\n".join(final_output_parts).strip()
            elif messages:
                final_text = messages[-1]["text"].strip()
            else:
                final_text = "Logistics request processed successfully."

            print(f"\n[Agent Final Output - Model: {model_name}]:\n{final_text}\n")

            return {
                "status": "SUCCESS",
                "model_used": model_name,
                "prompt": user_prompt,
                "session_id": session_id,
                "final_response": final_text,
                "tool_calls": tool_calls,
                "tool_responses": tool_responses,
                "timeline": messages
            }

        except Exception as e:
            last_error = str(e)
            print(f"Model '{model_name}' encountered error: {last_error}")
            if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error or "Quota exceeded" in last_error or "404" in last_error:
                print(f"Quota / availability issue with '{model_name}'. Trying next fallback model...")
                continue
            else:
                break

    return {
        "status": "ERROR",
        "prompt": user_prompt,
        "session_id": session_id,
        "error": last_error,
        "final_response": f"Logistics processing failed across available models: {last_error}",
        "tool_calls": [],
        "tool_responses": []
    }


# =====================================================================
# 4. CLI Self-Test Runner
# =====================================================================

async def main():
    init_db(reset=True)

    print("\n================ TEST CASE 1: In-Stock Order ================")
    res1 = await process_logistics_request("Process order #ORD-001 for SKU ITEM-101 to Chicago")

    print("\n================ TEST CASE 2: Out-of-Stock Order ================")
    res2 = await process_logistics_request("Process order #ORD-002 for SKU ITEM-202 to Seattle")

    print("\n================ TEST CASE 3: Route Weather Exception ================")
    res3 = await process_logistics_request("Process order #ORD-003 for SKU ITEM-101 to Denver")


if __name__ == "__main__":
    asyncio.run(main())
