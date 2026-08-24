"""
Groq Agent Client — autonomous procurement agent using OpenAI/GPT-OSS-120B via Groq.

Replaces both the OpenAI and Anthropic clients. Since Groq's API is
OpenAI-compatible, tool calling format is identical to the OpenAI client.

Supports two personas:
  - "openai-demo-agent"   → ₹5,000 budget, keyboards + mouse + cables
  - "anthropic-demo-agent" → ₹2,500 budget, keyboards only

Usage:
  python clients/groq_agent.py
  GROQ_AGENT_ID=anthropic-demo-agent python clients/groq_agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

# Force UTF-8 output on Windows (fixes cp1252 encoding errors with ₹, ─, etc.)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq import Groq
from dotenv import load_dotenv

from clients.common.tools import TOOLS, SYSTEM_PROMPT
from clients.common.executor import execute_tool

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration — override via environment variables
# ---------------------------------------------------------------------------
AGENT_ID = os.environ.get("GROQ_AGENT_ID", "openai-demo-agent")
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Default goals per agent persona
AGENT_GOALS = {
    "openai-demo-agent": (
        "You are an autonomous procurement agent. "
        "Your budget is Rs.5,000. Scope: mechanical keyboards, mice, and cables. "
        "Search the catalog and attempt to purchase the 'Premium Mechanical Keyboard' (SKU: KB007) which costs Rs. 7,999. "
        "Verify it is in stock, and create an order. "
        "Since it exceeds your budget, you will be blocked. You MUST then use request_budget_increase to appeal to the Finance Agent. "
        "Once approved, retry the order. After the order succeeds, simulate the payment and check for upsells. "
        "Explain every decision you make."
    ),
    "anthropic-demo-agent": (
        "You are an autonomous procurement agent. "
        "Your budget is Rs.2,500. Scope: mechanical keyboards only. "
        "Search the catalog, pick the best mechanical keyboard within your budget, "
        "verify it is in stock, and create an order. Explain every decision you make."
    ),
}


def get_groq_tools() -> list[dict]:
    """
    Convert our provider-agnostic tool definitions into Groq/OpenAI
    function-calling format (type: function wrapper).
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in TOOLS
    ]


async def run_agent(
    user_goal: str,
    mandate_id: str,
    max_turns: int = 12,
) -> None:
    """
    Main agentic loop using the Groq SDK (OpenAI-compatible interface).

    The loop follows the standard tool-calling pattern:
      1. Send messages to the model
      2. If the model returns tool_calls → execute them → append results → repeat
      3. If the model returns a plain text message → print and exit
    """
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY not set. Add it to your .env file.")
        return

    client = Groq(api_key=GROQ_API_KEY)
    tools = get_groq_tools()

    print(f"\n{'='*65}")
    print(f"[GROQ AGENT]  Model: {MODEL}")
    print(f"   Agent ID  : {AGENT_ID}")
    print(f"   Mandate   : {mandate_id}")
    print(f"   Goal      : {user_goal[:80]}...")
    print(f"{'='*65}\n")

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal},
    ]

    for turn in range(max_turns):
        print(f"── Turn {turn + 1} ──────────────────────────────────────────────")

        # Call the Groq model
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=1,
            max_completion_tokens=2048,
            top_p=1,
            reasoning_effort="medium",
        )

        msg = response.choices[0].message

        # ── Case 1: Model wants to call one or more tools ──
        if msg.tool_calls:
            # Append the assistant message (with tool_calls) to history
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            # Execute each tool call and append the results
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)

                print(f"   [TOOL] {fn_name}")
                print(f"      Args   : {json.dumps(fn_args, indent=5).strip()}")

                # HTTP call to our FastAPI server
                result = await execute_tool(fn_name, fn_args, AGENT_ID, mandate_id)

                print(f"      Result   : {json.dumps(result, indent=5)[:600].strip()}")
                print()

                # Append the tool result in OpenAI/Groq format
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": json.dumps(result),
                })

        # ── Case 2: Model produced a final text response ──
        elif msg.content:
            print(f"\n[FINAL RESPONSE]\n")
            print(msg.content)
            print()
            break

        # Safety: stop_reason = stop with no content means the model is done
        if response.choices[0].finish_reason == "stop":
            if msg.content:
                print(f"\n[FINAL RESPONSE]\n{msg.content}\n")
            break

    print(f"{'='*65}")
    print(f"[DONE] Groq Agent completed in {turn + 1} turn(s).")
    print(f"{'='*65}\n")


async def main():
    """
    Entry point — validate server connectivity, then run the agent.
    The mandate_id is read from an environment variable set after seeding.
    """
    import httpx

    # Verify server is reachable
    try:
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
            resp = await client.get("/health")
            if resp.status_code != 200:
                raise RuntimeError("bad status")
    except Exception:
        print("[ERROR] Server not running. Start it with:")
        print("   uvicorn app.main:app --reload")
        return

    # Resolve mandate ID from environment
    env_key = "OPENAI_MANDATE_ID" if AGENT_ID == "openai-demo-agent" else "ANTHROPIC_MANDATE_ID"
    mandate_id = os.environ.get(env_key, "")

    if not mandate_id:
        print(f"[WARN] No {env_key} set. Run the seed script first:")
        print("   python scripts/seed_catalog.py")
        print(f"   Then add {env_key} to your .env file.")
        return

    goal = AGENT_GOALS.get(AGENT_ID, AGENT_GOALS["openai-demo-agent"])

    await run_agent(
        user_goal=goal,
        mandate_id=mandate_id,
    )


if __name__ == "__main__":
    asyncio.run(main())
