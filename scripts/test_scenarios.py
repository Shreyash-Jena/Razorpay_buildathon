import asyncio
import os
import subprocess
import sqlite3

def run_agent(agent_id, goal):
    print(f"\n{'='*80}\nSCENARIO: {agent_id} -> {goal}\n{'='*80}")
    env = os.environ.copy()
    env["GROQ_AGENT_ID"] = agent_id
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = "."
    
    # We pass the goal via an environment variable to override AGENT_GOALS
    env["OVERRIDE_GOAL"] = goal
    
    proc = subprocess.run(
        ["python", "clients/groq_agent.py"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(proc.stdout)
    if proc.stderr:
        print("ERRORS:")
        print(proc.stderr)

def main():
    # 1. Happy path: Anthropic agent (budget Rs 2500, scope: keyboards) buys a budget keyboard
    run_agent(
        "anthropic-demo-agent", 
        "Buy the 'Budget Mechanical Keyboard' (SKU: KB003) which costs Rs. 1,999. It is within your Rs. 2,500 budget and scope."
    )
    
    # 5. Upsell Graph Test: OpenAI agent (budget Rs 5000) buys KB001 and gets upsell recommendation for MOUSE001
    run_agent(
        "openai-demo-agent",
        "Buy the 'Mechanical RGB Keyboard' (SKU: KB001) which costs Rs. 3,499. You have Rs. 5,000 budget."
    )

if __name__ == "__main__":
    main()
