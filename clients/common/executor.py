"""
Tool execution — HTTP calls to the MCP server.
Shared by all agent clients.
"""

from __future__ import annotations

import uuid
import httpx

from clients.common.tools import SERVER_URL


async def execute_tool(
    tool_name: str,
    arguments: dict,
    agent_id: str,
    mandate_id: str,
) -> dict:
    """Execute a tool by calling the MCP server API."""

    async with httpx.AsyncClient(base_url=SERVER_URL, timeout=30.0) as client:
        if tool_name == "search_catalog":
            resp = await client.get("/catalog/search", params={"query": arguments["query"]})
            return resp.json()

        elif tool_name == "check_stock":
            resp = await client.get(f"/catalog/{arguments['sku']}/stock")
            return resp.json()

        elif tool_name == "create_order":
            payload = {
                "agent_id": agent_id,
                "mandate_id": mandate_id,
                "sku": arguments["sku"],
                "quantity": arguments.get("quantity", 1),
                "rationale": arguments.get("rationale", ""),
                "nonce": str(uuid.uuid4()),
                "signed_intent": "",  # Demo mode — signature optional
                "payment_mode": "b2c" if agent_id.startswith("anthropic") else "b2b",
            }
            resp = await client.post("/orders", json=payload)
            try:
                data = resp.json()
            except Exception:
                return {"success": False, "error": {"code": "SERVER_ERROR", "reason": f"HTTP {resp.status_code}: {resp.text[:200]}"}}
            if resp.status_code == 403:
                return data.get("detail", data)
            return data

        elif tool_name == "get_payment_status":
            resp = await client.get(f"/orders/{arguments['order_id']}")
            try:
                return resp.json()
            except Exception:
                return {"error": f"HTTP {resp.status_code}"}

        elif tool_name == "get_upsell":
            resp = await client.get(f"/upsells/{arguments['order_id']}")
            try:
                return resp.json()
            except Exception:
                return {"error": f"HTTP {resp.status_code}"}

        elif tool_name == "request_budget_increase":
            payload = {
                "requested_amount_paise": arguments["requested_amount_paise"],
                "rationale": arguments["rationale"],
            }
            resp = await client.post(f"/mandates/{mandate_id}/request_budget_increase", json=payload)
            try:
                data = resp.json()
                if resp.status_code == 400:
                    return data.get("detail", data)
                return data
            except Exception:
                return {"error": f"HTTP {resp.status_code}"}
                
        elif tool_name == "simulate_payment":
            payload = {"order_id": arguments["order_id"]}
            resp = await client.post("/orders/simulate_payment", json=payload)
            try:
                return resp.json()
            except Exception:
                return {"error": f"HTTP {resp.status_code}"}

        else:
            return {"error": f"Unknown tool: {tool_name}"}
