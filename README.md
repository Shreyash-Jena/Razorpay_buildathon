# Agentic Commerce Server

A Universal Agentic Interoperability Server providing MCP-compatible commerce tools for autonomous AI agents. Built for the Razorpay AI Buildathon (Track 1).

## Features

- **The Policy Gate**: 11-step authorization pipeline enforcing financial limits, scopes, velocity, and replay protection before any API calls reach Razorpay.
- **Flight Recorder**: Append-only, SHA-256 hash-chained audit ledger for tamper-evident accountability.
- **Agent Interoperability**: Agnostic tool definitions that work with any LLM. Includes demo clients for OpenAI (GPT-4o) and Anthropic (Claude 3.5).
- **NetworkX Graph Engine**: P(B|A) conditional probability upsell recommendations based on synthetic order history.
- **Ed25519 Cryptography**: Signed mandates and purchase intents.

## Setup & Local Run

1. **Install Dependencies:**
   ```bash
   pip install -e .
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY, ANTHROPIC_API_KEY, and Razorpay test credentials.
   ```

3. **Database Migration & Seed:**
   ```bash
   # Run migrations
   alembic upgrade head
   
   # Seed demo catalog, historical orders, and agent mandates
   python scripts/seed_catalog.py
   ```
   *Note: Save the `mandate_id` values printed by the seed script!*

4. **Start the Server:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Run the Agent Demos (in another terminal):**
   ```bash
   # Export the mandate ID from the seed step
   export OPENAI_MANDATE_ID="your-openai-mandate-id"
   python clients/openai_agent.py
   
   export ANTHROPIC_MANDATE_ID="your-anthropic-mandate-id"
   python clients/anthropic_agent.py
   ```

## Deployment (Zero-Cost on Render)

This project includes a `render.yaml` for zero-cost deployment on Render.com.

1. Push this repository to GitHub.
2. Log in to [Render](https://render.com/).
3. Click "New" -> "Blueprint".
4. Connect your GitHub repository.
5. Render will automatically provision a free Web Service (FastAPI) and run the `alembic upgrade head` and `seed_catalog.py` scripts during deployment.
