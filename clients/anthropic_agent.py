"""
Anthropic Agent Client — autonomous procurement agent using Claude 3.5 Haiku.

Connects to the Universal MCP Commerce Server and uses the exact same
tool definitions as the OpenAI agent to prove interoperability.
"""

from __future__ import annotations

import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from clients.common.tools import TOOLS, SYSTEM_PROMPT
from clients.common.executor import execute_tool

load_dotenv()

# Agent configuration
AGENT_ID = "anthropic-demo-agent"
MODEL = "claude-3-5-haiku-latest"


def get_anthropic_tools() -> list[dict]:
    """Convert our tool definitions to Anthropic tool-use format."""
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["parameters"],
        }
        for tool in TOOLS
    ]


async def run_agent(
    user_goal: str,
    mandate_id: str,
    max_turns: int = 10,
) -> None:
    """Run the Anthropic agent loop."""
    client = AsyncAnthropic()

    print(f"\n{'='*60}")
    print(f"🤖 Anthropic Agent ({MODEL})")
    print(f"   Agent ID: {AGENT_ID}")
    print(f"   Mandate:  {mandate_id}")
    print(f"   Goal:     {user_goal}")
    print(f"{'='*60}\n")

    messages = [
        {"role": "user", "content": user_goal},
    ]

    tools = get_anthropic_tools()

    for turn in range(max_turns):
        print(f"── Turn {turn + 1} ──")

        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
        )

        # Process the response content blocks
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Check for tool use
        tool_uses = [b for b in assistant_content if b.type == "tool_use"]
        text_blocks = [b for b in assistant_content if b.type == "text"]

        # Print any text the model produced
        for block in text_blocks:
            if block.text.strip():
                print(f"   💬 {block.text[:300]}")

        if tool_uses:
            tool_results = []
            for tool_use in tool_uses:
                fn_name = tool_use.name
                fn_args = tool_use.input

                print(f"   🔧 Tool: {fn_name}")
                print(f"      Args: {json.dumps(fn_args, indent=2)}")

                # Execute tool against the MCP server
                result = await execute_tool(fn_name, fn_args, AGENT_ID, mandate_id)

                print(f"      Result: {json.dumps(result, indent=2)[:500]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            # No tool calls — final response
            for block in text_blocks:
                if block.text.strip():
                    print(f"\n📋 Agent Response:\n{block.text}\n")
            break

        if response.stop_reason == "end_turn":
            for block in text_blocks:
                if block.text.strip():
                    print(f"\n📋 Agent Response:\n{block.text}\n")
            break

    print(f"{'='*60}")
    print(f"✅ Anthropic Agent completed in {turn + 1} turns")
    print(f"{'='*60}\n")


async def main():
    """Run the demo scenario."""
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        resp = await client.get(f"/catalog/search", params={"query": "keyboard"})
        if resp.status_code != 200:
            print("❌ Server not running. Start it with: uvicorn app.main:app --reload")
            return

    mandate_id = os.environ.get("ANTHROPIC_MANDATE_ID", "")

    if not mandate_id:
        print("⚠️  No ANTHROPIC_MANDATE_ID set. Run the seed script first.")
        print("   Use: python scripts/seed_catalog.py")
        print("   Then set ANTHROPIC_MANDATE_ID from the output.")
        return

    await run_agent(
        user_goal=(
            "You are an autonomous procurement agent. "
            "Your budget is ₹2,500. "
            "Buy the best mechanical keyboard available in the catalog. "
            "Explain your reasoning."
        ),
        mandate_id=mandate_id,
    )


if __name__ == "__main__":
    asyncio.run(main())
