# Agentic Commerce: Universal Interoperability Server

![Agentic Commerce](https://img.shields.io/badge/Platform-Agentic%20Commerce-blue?style=for-the-badge)
![Security](https://img.shields.io/badge/Security-11--Layer-red?style=for-the-badge)
![Audit](https://img.shields.io/badge/Audit-Immutable%20Flight%20Recorder-green?style=for-the-badge)

Welcome to the future of autonomous transactions. As AI agents evolve from conversational assistants into autonomous actors, they require the ability to interact with real-world commerce. However, giving an LLM unfettered access to a corporate bank account or a user's credit card is fundamentally unsafe. 

This project solves the "Agentic Commerce problem." We haven't just built a checkout flow; we have engineered a **Universal Interoperability Server**—a zero-trust middleware gateway that acts as the cryptographic and semantic bridge between autonomous AI agents and legacy financial infrastructure (Razorpay). 

At its core, this platform enforces absolute safety through an **11-Layer Security Engine** and records every LLM decision in an **Immutable Flight Recorder**. Advanced features like B2B/B2C payment routing and the LLM-powered Upsell Engine are built *on top* of this bulletproof core.

---

## 🏗️ Architecture & Core Components

The system is designed as a strict, unidirectional pipeline. An AI agent cannot interact directly with the database or Razorpay. It must cryptographically sign its intent and pass it through the gateway.

### 1. The Interoperability Gateway (The Core)
The central nervous system of the platform. It intercepts standardized tool calls from *any* LLM (OpenAI, Anthropic, Gemini, Groq) and normalizes them. It provides a standard set of interoperable tools:
- `search_catalog`
- `check_stock`
- `create_order`
- `simulate_payment`
- `get_upsell`
- `request_budget_increase`

### 2. The 11-Layer Policy Engine (Security)
Before any API call is allowed to touch the commerce layer, it must survive the Policy Engine. This is an algorithmic gauntlet that evaluates the agent's cryptographic signature, budget, and semantic scope. If any layer fails, the transaction is rejected *before* it happens.

### 3. The Immutable Flight Recorder (Audit Log)
AI agents hallucinate, make mistakes, and execute tasks autonomously while humans sleep. We built a blockchain-inspired "Flight Recorder" that logs every single action, intent, and payload. Each log entry is cryptographically hashed using the previous log's hash (`SHA-256(previous_hash + current_payload)`). If a malicious actor alters a database record to hide an unauthorized AI purchase, the hash chain breaks, instantly flagging the tamper.

### 4. The Commerce & Payments Engine
Once the Policy Engine approves the intent, the Commerce Engine reserves the inventory and interfaces with the Razorpay Client. It intelligently routes the transaction based on the principal type (B2B Corporate vs. B2C Individual).

### 5. The Dynamic Upsell & Finance Agents (Extensibility)
Built on top of the secure core are autonomous sub-agents. 
- **The Upsell Engine**: A payment-agnostic layer that intercepts successful checkouts and dynamically recommends co-purchases to the AI based on historical data.
- **The Finance Agent**: If a procurement AI runs out of budget but finds a critical upsell, it can query the Finance Agent (a separate LLM persona). The Finance Agent evaluates the rationale and autonomously expands the cryptographic budget ceiling in real-time.

---

## 🛡️ The 11-Layer Security Protocol

Every single `create_order` request made by an AI is subjected to the following 11-layer gauntlet:

1. **Cryptographic Identity Verification**: The agent must provide a valid `Mandate ID` and an RSA signature of its payload. The server verifies this against the public key stored on file.
2. **Temporal Validity**: The mandate is checked against its `issued_at` and `expires_at` timestamps. Expired or revoked mandates are instantly blocked.
3. **Idempotency Locking**: The server generates an idempotency key (`agent_id:mandate_id:nonce`). This prevents replay attacks or "LLM stutter" where an agent accidentally fires the tool call twice.
4. **Velocity Controls**: The engine checks the number of transactions the agent has made within a rolling velocity window to prevent runaway loops (e.g., max 5 transactions per 24 hours).
5. **Strict SKU & Scope Verification**: The agent's requested purchase is semantically mapped against its allowed scope. If a "Keyboard Procurement Agent" tries to buy a laptop, the engine throws a `SKU_NOT_ALLOWED` error.
6. **Financial Ceiling Enforcement**: The engine calculates the current order value, sums it with the agent's historical spend on this mandate, and compares it to the hardcoded `financial_ceiling_paise`. 
7. **Inventory Concurrency Verification**: Real-time database locks ensure the item is actually in stock, preventing the agent from buying out-of-stock items and causing refund nightmares.
8. **Autonomous Finance Gateways**: If the budget is exceeded, the transaction is halted. The agent is forced to use a secondary `request_budget_increase` tool to justify the overage to an autonomous LLM Finance Auditor.
9. **Zero-Trust B2B Routing (Virtual Accounts)**: For B2B mandates, the agent is never given a credit card. The system provisions a Razorpay Smart Collect Virtual Account dynamically. The actual transfer of funds remains physically controlled by a human corporate finance team making a bank transfer.
10. **Tokenized B2C Mandates**: For B2C mandates, the agent uses a secure, pre-authorized Token ID mapped to the Razorpay Recurring Payments API. The card details are completely invisible and inaccessible to the LLM context window.
11. **Immutable Cryptographic Hashing**: Regardless of success or failure, the entire evaluation state, rationale, and outcome are chained into the Flight Recorder.

---

## 💻 Tech Stack

- **Backend Framework**: FastAPI (Python) - High performance, async, type-safe API routing.
- **Database**: SQLite with SQLAlchemy (Async) - Relational mapping for products, orders, mandates, and the audit ledger.
- **LLM Integrations**: OpenAI, Anthropic, Groq (via official Python SDKs) - For agent simulation and the Finance Agent evaluation.
- **Payments Infrastructure**: Razorpay APIs 
  - *Smart Collect* (Virtual Accounts / B2B)
  - *Recurring Payments* (Tokenized Mandates / B2C)
- **Security**: Cryptography (`cryptography.hazmat`) for RSA signature generation and verification. `hashlib` for SHA-256 ledger chaining.

---

## 🔄 Flow of Information

1. **Prompt**: The AI Agent receives a prompt (e.g., "Buy me a mechanical keyboard and any recommended accessories").
2. **Tool Execution**: The Agent uses `search_catalog` and `check_stock`, gathering contextual data.
3. **Intent Generation**: The Agent constructs a JSON payload for `create_order` and cryptographically signs it using its private key.
4. **Gateway Ingestion**: The FastAPI server receives the signed payload.
5. **Policy Engine Evaluation**: The server passes the payload through the 11-Layer Security Protocol. 
6. **Outcome A (Rejection)**: If a layer fails (e.g., out of budget), the transaction is blocked, hashed into the Flight Recorder, and an error string is returned to the Agent's context window.
7. **Outcome B (Approval)**: The transaction is approved. The stock is decremented.
8. **Payment Routing**: 
   - If B2B: The Razorpay Client generates a Virtual Account via Smart Collect.
   - If B2C: The Razorpay Client hits the S2S Recurring API with the vaulted Token ID.
9. **Upsell Injection**: The Upsell Engine intercepts the success response, appending a dynamic product recommendation.
10. **Final Hashing**: The final success state is hashed into the Flight Recorder.
11. **Agent Context**: The AI agent receives the success confirmation, the Razorpay payment instructions, and the upsell prompt, allowing it to continue its reasoning loop.

---

## 🛣️ Comprehensive Scenarios

Because this is a universal interoperability server, it handles all permutation of edge cases. Here are the fully tested end-to-end scenarios the platform supports:

### The B2B Scenarios (Human-in-the-Loop)
*In B2B, the principal is a corporation. The agent procures, but a human must ultimately wire the funds to the generated Razorpay Virtual Account.*

- **Scenario 1: The Flawless Procurement**
  The agent searches for a valid item within its scope and budget. It creates the order. The server generates a Razorpay Virtual Account. The agent notifies the human finance team to transfer funds to that account.
- **Scenario 2: The Rejection by Scope**
  An agent explicitly scoped to "Office Supplies" attempts to buy "Gaming Laptops". The Policy Engine intercepts the semantic mismatch and hard-blocks the tool execution, returning a `SKU_NOT_ALLOWED` error to the LLM.
- **Scenario 3: The Rejection by Budget**
  An agent attempts to buy 10 keyboards. The total exceeds the 5,000 INR mandate limit. The Policy Engine blocks the transaction with an `AMOUNT_EXCEEDS_LIMIT` error.
- **Scenario 4: The Out-of-Stock Reality**
  The agent attempts to procure an item that another agent just bought the last unit of. The database concurrency check fails, returning an `OUT_OF_STOCK` error, forcing the agent to find an alternative.
- **Scenario 5: The Autonomous Upsell & Budget Expansion**
  The agent successfully buys a keyboard. The Upsell Engine injects a recommendation for a gaming mouse. The agent attempts to buy the mouse but hits its budget ceiling. The agent autonomously invokes `request_budget_increase`, submitting a business rationale ("Need the mouse to complete the workstation"). The autonomous LLM Finance Agent evaluates the rationale, approves it, and dynamically rewrites the cryptographic budget ceiling. The agent retries the mouse purchase and succeeds.

### The B2C Scenarios (Zero-Click Server-to-Server)
*In B2C, the principal is an individual. The agent must checkout autonomously without asking the user to manually transfer funds or click a payment link.*

- **Scenario 6: The Vaulted Token Capture**
  The consumer has previously vaulted their card with Razorpay, generating a secure `Token ID`. The agent creates an order for a valid consumer good. Because the mandate is flagged as B2C, the server bypasses the Virtual Account logic. It immediately pings the Razorpay Recurring Payments API using the secure Token ID, capturing the funds instantly on the backend. The agent receives a successful `captured` receipt instantly, achieving true autonomous, zero-click agentic commerce. 

---
*Built for the Razorpay Buildathon by Shreyash Jena.*
