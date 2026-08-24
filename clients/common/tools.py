"""
Common tool definitions shared by all agent clients.
Both OpenAI and Anthropic agents use exactly the same tool surface.
"""

from __future__ import annotations

# Server base URL
SERVER_URL = "http://localhost:8000"

# Tool definitions in a provider-agnostic format
TOOLS = [
    {
        "name": "search_catalog",
        "description": (
            "Search the merchant catalog for products. Returns matching items with "
            "SKU, name, price, category, and stock availability."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — product name, category, or keyword",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_stock",
        "description": (
            "Check stock availability for a specific product SKU. "
            "If out of stock, returns a substitute product suggestion."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "Product SKU to check stock for",
                },
            },
            "required": ["sku"],
        },
    },
    {
        "name": "create_order",
        "description": (
            "Create a purchase order for a product. This goes through the Policy Gate "
            "for authorization. Requires agent_id, mandate_id, SKU, quantity, and rationale. "
            "If the order violates the mandate (budget, scope), it will be blocked with a "
            "structured error. Never retry with altered values if blocked."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "Product SKU to purchase",
                },
                "quantity": {
                    "type": "integer",
                    "description": "Number of units to purchase",
                    "minimum": 1,
                },
                "rationale": {
                    "type": "string",
                    "description": "Explanation for why you chose this product",
                },
            },
            "required": ["sku", "quantity", "rationale"],
        },
    },
    {
        "name": "get_payment_status",
        "description": "Get the status of an order by its order ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID to check",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "get_upsell",
        "description": (
            "Get a data-backed upsell recommendation for a completed order. "
            "Returns co-purchase probability and suggested product."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID to get upsell for",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "request_budget_increase",
        "description": (
            "Appeal to the Finance Agent for a budget increase if the Policy Gate blocks "
            "your purchase due to AMOUNT_EXCEEDS_LIMIT."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "requested_amount_paise": {
                    "type": "integer",
                    "description": "The new total budget requested in paise (e.g. 600000 for Rs. 6000)",
                },
                "rationale": {
                    "type": "string",
                    "description": "Justification for the budget increase to present to Finance",
                },
            },
            "required": ["requested_amount_paise", "rationale"],
        },
    },
    {
        "name": "simulate_payment",
        "description": "Simulates a successful payment for an order. Call this immediately after successfully creating an order.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order ID to pay",
                },
            },
            "required": ["order_id"],
        },
    },
]

# System prompt for all agents
SYSTEM_PROMPT = """You are an autonomous procurement agent.
You are authorized to purchase products only through the provided commerce tools.
You must never assume you have authorization that is not explicitly provided by the tools.

Follow this workflow:
1. Use search_catalog to find products matching the user's request.
2. Use check_stock to verify availability of your chosen product.
3. If a product is out of stock, inspect the substitute but do NOT purchase outside your authorization.
4. Before executing a purchase, explain your decision rationale clearly.
5. Use create_order to make the purchase.
6. If the create_order tool returns a policy block for AMOUNT_EXCEEDS_LIMIT, you may call request_budget_increase to ask the Finance Agent for more funds. If approved, retry the order.
7. If the order is created successfully, immediately call simulate_payment to finalize the transaction.
8. After a successful payment, call get_upsell. If an upsell is recommended and you have budget left, you may autonomously purchase it.
9. If a tool returns a mandate violation other than budget, do NOT retry with altered values.

Never invent price or availability data. Always rely on the tools."""
