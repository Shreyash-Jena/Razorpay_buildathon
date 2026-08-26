import asyncio
import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.common.executor import execute_tool

OPENAI_MANDATE_ID = "b7042ac0-1c11-446f-b3d2-3ad050026697"
ANTHROPIC_MANDATE_ID = "b29e83db-ee84-4e4b-9651-03d7aa741a39"
OPENAI_AGENT = "openai-demo-agent"
ANTHROPIC_AGENT = "anthropic-demo-agent"

async def test_scenario_a():
    print("\n--- Scenario A: Valid Purchase & Upsell (OpenAI) ---")
    
    # 1. Search Catalog
    print("[1] Searching for keyboards...")
    search_res = await execute_tool("search_catalog", {"query": "keyboard"}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Search Result:", len(search_res), "items found.")
    
    # KB001 - Mechanical RGB Keyboard (3499 INR)
    # 2. Check Stock
    print("[2] Checking stock for KB001...")
    stock_res = await execute_tool("check_stock", {"sku": "KB001"}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Stock:", stock_res.get("stock_count", 0))

    # 3. Create Order
    print("[3] Creating order for KB001...")
    order_res = await execute_tool("create_order", {"sku": "KB001", "quantity": 1, "rationale": "Buying for work."}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Order Result:", json.dumps(order_res, ensure_ascii=False))
    assert order_res.get("success") == True
    order_id = order_res.get("order_id")

    # 4. Simulate Payment
    print("[4] Simulating payment for order", order_id)
    pay_res = await execute_tool("simulate_payment", {"order_id": order_id}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Payment Result:", json.dumps(pay_res, ensure_ascii=False))
    assert pay_res.get("success") == True
    print("\n" + "="*80)
    print("USER ACTION REQUIRED: Please log in to Razorpay Dashboard (Test Mode).")
    print(f"Go to Smart Collect -> Customer Identifiers -> Find Virtual Account ID: {order_res.get('virtual_account_id')}")
    print("Click 'Make a Test Payment' to simulate the bank transfer and see the order transition to paid.")
    print("="*80 + "\n")

    # 5. Get Upsell
    print("[5] Getting upsell for order", order_id)
    upsell_res = await execute_tool("get_upsell", {"order_id": order_id}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    # Safely print without UnicodeEncodeError on Windows
    print("Upsell Result:", json.dumps(upsell_res, ensure_ascii=False))
    assert upsell_res.get("has_recommendation") == True

    # 6. Buy Upsell (Should be MOUSE002, 2499 INR)
    rec_sku = upsell_res["recommendation"]["recommended_sku"]
    print(f"[6] Buying upsell {rec_sku}...")
    upsell_order_res = await execute_tool("create_order", {"sku": rec_sku, "quantity": 1, "rationale": "Buying recommended upsell."}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Upsell Order Result:", json.dumps(upsell_order_res, ensure_ascii=False))
    # It will fail budget because 3499 + 2499 > 5000
    assert upsell_order_res.get("success") == False
    assert upsell_order_res.get("error", {}).get("code") == "AMOUNT_EXCEEDS_LIMIT"

    # 7. Request Budget Increase
    print("[7] Requesting budget increase to 10000 INR...")
    increase_res = await execute_tool("request_budget_increase", {"rationale": "Need more budget for upsell", "requested_amount_paise": 1000000}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Budget Increase Result:", json.dumps(increase_res, ensure_ascii=False))
    if isinstance(increase_res, dict) and increase_res.get("success"):
        print("Budget Increased!")
    else:
        print("Budget Increase failed (possibly due to LLM). Continuing test...")

    # 8. Buy Upsell Again
    print("[8] Buying upsell again...")
    upsell_order_res2 = await execute_tool("create_order", {"sku": rec_sku, "quantity": 1, "rationale": "Buying recommended upsell."}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Upsell Order Result (Retry):", json.dumps(upsell_order_res2, ensure_ascii=False))
    assert upsell_order_res2.get("success") == True
    
    print("Scenario A Passed!\n")


async def test_scenario_b():
    print("\n--- Scenario B: Budget Limit Rejection (OpenAI) ---")
    
    # 1. Try to buy KB004 (6999 INR)
    # OpenAI mandate was increased to 10000 INR, spent ~6000, so remaining is ~4000.
    # KB004 is in scope but exceeds remaining budget.
    print("[1] Attempting to buy KB004...")
    order_res = await execute_tool("create_order", {"sku": "KB004", "quantity": 1, "rationale": "Need a premium keyboard."}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Order Result:", order_res)
    
    assert order_res.get("success") == False
    assert order_res.get("error", {}).get("code") == "AMOUNT_EXCEEDS_LIMIT"
    print("Scenario B Passed!\n")


async def test_scenario_c():
    print("\n--- Scenario C: Scope Rejection (Anthropic) ---")
    
    # 1. Try to buy a Mouse (MOUSE001)
    # Anthropic mandate scope is only "mechanical-keyboards"
    print("[1] Attempting to buy MOUSE001...")
    order_res = await execute_tool("create_order", {"sku": "MOUSE001", "quantity": 1, "rationale": "Buying mouse."}, ANTHROPIC_AGENT, ANTHROPIC_MANDATE_ID)
    print("Order Result:", json.dumps(order_res, ensure_ascii=False))
    
    assert order_res.get("success") == False
    assert order_res.get("error", {}).get("code") == "SKU_NOT_ALLOWED"
    print("Scenario C Passed!\n")

async def test_scenario_d():
    print("\n--- Scenario D: Out of Stock (Anthropic) ---")
    
    # Request 99 (Pydantic max is 100, KB001 stock is 17)
    print("[1] Attempting to buy 99 of KB001...")
    order_res = await execute_tool("create_order", {"sku": "KB001", "quantity": 99, "rationale": "Bulk order."}, OPENAI_AGENT, OPENAI_MANDATE_ID)
    print("Order Result:", order_res)
    
    assert order_res.get("success") == False
    assert order_res.get("error", {}).get("code") == "OUT_OF_STOCK"
    print("Scenario D Passed!\n")

async def test_scenario_e():
    print("\n--- Scenario E: Valid B2C Purchase with Tokenized Mandate (Anthropic) ---")
    
    print("[1] Creating order for KB002...")
    order_res = await execute_tool("create_order", {"sku": "KB002", "quantity": 1, "rationale": "Buying valid B2C keyboard."}, ANTHROPIC_AGENT, ANTHROPIC_MANDATE_ID)
    print("Order Result:", json.dumps(order_res, ensure_ascii=False))
    assert order_res.get("success") == True
    order_id = order_res.get("order_id")
    
    # B2C orders won't have virtual_account_id
    assert not order_res.get("virtual_account_id")
    assert order_res.get("payment_mode") == "b2c"

    print("[2] Simulating S2S B2C Tokenized payment for order", order_id)
    pay_res = await execute_tool("simulate_payment", {"order_id": order_id}, ANTHROPIC_AGENT, ANTHROPIC_MANDATE_ID)
    print("Payment Result:", json.dumps(pay_res, ensure_ascii=False))
    assert pay_res.get("success") == True
    assert pay_res.get("method") == "agent_s2s_recurring"
    
    print("\n" + "="*80)
    print("USER ACTION REQUIRED: Please log in to your B2C Razorpay Dashboard (Test Mode).")
    print(f"Check the 'Transactions' tab to see the payment of {order_res.get('total_display')} instantly captured via the tokenized card!")
    print("="*80 + "\n")
    
    print("Scenario E Passed!\n")

async def main():
    try:
        await test_scenario_a()
        print("\n" + "="*80 + "\n")
        await test_scenario_b()
        print("\n" + "="*80 + "\n")
        await test_scenario_c()
        print("\n" + "="*80 + "\n")
        await test_scenario_d()
        print("\n" + "="*80 + "\n")
        await test_scenario_e()
        print("All End-to-End Scenarios Passed successfully!")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
