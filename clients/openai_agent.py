"""
OpenAI Agent Client — autonomous procurement agent using GPT-4o-mini.

Connects to the Universal MCP Commerce Server and uses the exact same
tool definitions as the Anthropic agent to prove interoperability.
"""

from __future__ import annotations

import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import AsyncOpenAI
from dotenv import load_dotenv

from clients.common.tools import TOOLS, SYSTEM_PROMPT
from clients.common.executor import execute_tool

load_dotenv()

# Agent configuration
AGENT_ID = "openai-demo-agent"
MODEL = "gpt-4o-mini"


def get_openai_tools() -> list[dict]:
    """Convert our tool definitions to OpenAI function-calling format."""
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
    max_turns: int = 10,
) -> None:
    """Run the OpenAI agent loop."""
    client = AsyncOpenAI()

    print(f"\n{'='*60}")
    print(f"🤖 OpenAI Agent ({MODEL})")
    print(f"   Agent ID: {AGENT_ID}")
    print(f"   Mandate:  {mandate_id}")
    print(f"   Goal:     {user_goal}")
    print(f"{'='*60}\n")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal},
    ]

    tools = get_openai_tools()

    for turn in range(max_turns):
        print(f"── Turn {turn + 1} ──")

        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message

        # If the model wants to call tools
        if msg.tool_calls:
            messages.append(msg)

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"   🔧 Tool: {fn_name}")
                print(f"      Args: {json.dumps(fn_args, indent=2)}")

                # Execute tool against the MCP server
                result = await execute_tool(fn_name, fn_args, AGENT_ID, mandate_id)

                print(f"      Result: {json.dumps(result, indent=2)[:500]}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

        # If the model has a text response (final answer)
        elif msg.content:
            print(f"\n📋 Agent Response:\n{msg.content}\n")
            messages.append({"role": "assistant", "content": msg.content})
            break

        # No more actions
        if response.choices[0].finish_reason == "stop":
            if msg.content:
                print(f"\n📋 Agent Response:\n{msg.content}\n")
            break

    print(f"{'='*60}")
    print(f"✅ OpenAI Agent completed in {turn + 1} turns")
    print(f"{'='*60}\n")


async def main():
    """Run the demo scenario."""
    # First, get the mandate ID from the server
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        # Try to get existing mandate
        resp = await client.get(f"/catalog/search", params={"query": "keyboard"})
        if resp.status_code != 200:
            print("❌ Server not running. Start it with: uvicorn app.main:app --reload")
            return

    # The mandate_id will be provided by the seed script
    # For now, fetch from the server or use env var
    mandate_id = os.environ.get("OPENAI_MANDATE_ID", "")

    if not mandate_id:
        print("⚠️  No OPENAI_MANDATE_ID set. Run the seed script first.")
        print("   Use: python scripts/seed_catalog.py")
        print("   Then set OPENAI_MANDATE_ID from the output.")
        return

    await run_agent(
        user_goal=(
            "You are an autonomous procurement agent. "
            "Your budget is ₹5,000. "
            "Buy the best mechanical keyboard available in the catalog. "
            "Explain your reasoning."
        ),
        mandate_id=mandate_id,
    )


if __name__ == "__main__":
    asyncio.run(main())
