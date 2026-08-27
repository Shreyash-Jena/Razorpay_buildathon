import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import razorpay
from dotenv import load_dotenv, set_key

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(env_path)

KEY_ID = os.getenv("RAZORPAY_KEY_ID")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not KEY_ID or not KEY_SECRET:
    print("Error: RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set in .env")
    sys.exit(1)

client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))
app = FastAPI()

html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Generate B2C Token</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; text-align: center; padding-top: 50px; background: #f9f9f9;}
        .container { background: white; max-width: 600px; margin: 0 auto; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        button { margin-top: 20px; padding: 15px 30px; font-size: 18px; font-weight: bold; cursor: pointer; background: #3399cc; color: white; border: none; border-radius: 8px; transition: 0.2s; }
        button:hover { background: #267ba5; }
        .alert { background: #fff3cd; color: #856404; padding: 15px; border-radius: 6px; text-align: left; margin: 20px 0; border-left: 4px solid #ffeeba; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Razorpay B2C Token Generator</h2>
        <p>A new Customer ID has been generated for you:<br><strong>{{customer_id}}</strong></p>
        
        <div class="alert">
            <strong>⚠️ IMPORTANT:</strong> When the Razorpay window opens, you MUST check the <b>"Save Card for future payments"</b> checkbox, otherwise a Token ID will not be generated!
        </div>
        
        <p>Use any test card (e.g. <code>4111 1111 1111 1111</code>, any future expiry, any CVV).</p>
        
        <button id="rzp-button1">Pay ₹1.00 & Save Card</button>
    </div>
    
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <script>
    var options = {
        "key": "{{key_id}}",
        "name": "Agentic Commerce Demo",
        "description": "Vault card for B2C AI testing",
        "subscription_id": "{{subscription_id}}",
        "customer_id": "{{customer_id}}",
        "handler": function (response){
            window.location.href = "/success?payment_id=" + response.razorpay_payment_id + "&customer_id={{customer_id}}";
        },
        "prefill": {
            "name": "B2C AI Customer",
            "email": "b2c@buildathon.ai",
            "contact": "9999999999"
        },
        "theme": {
            "color": "#3399cc"
        }
    };
    var rzp1 = new Razorpay(options);
    document.getElementById('rzp-button1').onclick = function(e){
        rzp1.open();
        e.preventDefault();
    }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        import time
        # 1. Create a customer
        customer = client.customer.create({
            "name": "B2C AI Customer",
            "email": f"b2c_{int(time.time())}@buildathon.ai",
            "contact": "9999999999",
            "fail_existing": 0
        })
        customer_id = customer["id"]
        print(f"Created Customer: {customer_id}")

        # 2. Create a Mock Plan (Required to bypass the error)
        plan = client.plan.create({
            "period": "monthly",
            "interval": 1,
            "item": {
                "name": "AI Agent Authorization Plan",
                "amount": 100,  # ₹1.00
                "currency": "INR"
            }
        })
        plan_id = plan["id"]
        print(f"Created Plan: {plan_id}")

        # 3. Create the Subscription Mandate link
        subscription = client.subscription.create({
            "plan_id": plan_id,
            "customer_id": customer_id,
            "total_count": 12,
            "quantity": 1
        })
        subscription_id = subscription["id"]
        print(f"Created Subscription: {subscription_id}")

        # 4. Render HTML using subscription_id instead of order_id
        html = html_template.replace("{{key_id}}", KEY_ID)\
                            .replace("{{customer_id}}", customer_id)\
                            .replace("{{subscription_id}}", subscription_id)
        return html
    except Exception as e:
        return f"<h3>Error connecting to Razorpay:</h3><p>{e}</p>"

@app.get("/success", response_class=HTMLResponse)
def success(payment_id: str, customer_id: str):
    # Fetch payment to get the token_id
    payment = client.payment.fetch(payment_id)
    
    token_id = payment.get("token_id")
    if not token_id:
        return f"""
        <div style='font-family: sans-serif; text-align: center; margin-top: 50px;'>
            <h3 style='color: red;'>Payment succeeded, but no Token ID was found!</h3>
            <p>Did you forget to check the <b>'Save Card'</b> box in the checkout screen?</p>
            <br>
            <a href='/' style='padding: 10px 20px; background: #3399cc; color: white; text-decoration: none; border-radius: 5px;'>Try Again</a>
        </div>
        """
    
    # Update .env
    set_key(env_path, "RAZORPAY_B2C_KEY_ID", KEY_ID)
    set_key(env_path, "RAZORPAY_B2C_KEY_SECRET", KEY_SECRET)
    set_key(env_path, "RAZORPAY_B2C_CUSTOMER_ID", customer_id)
    set_key(env_path, "RAZORPAY_B2C_TOKEN_ID", token_id)
    
    print("\n" + "="*60)
    print("🎉 SUCCESS! B2C TOKEN GENERATED & SAVED 🎉")
    print(f"Customer ID: {customer_id}")
    print(f"Token ID:    {token_id}")
    print("The .env file has been automatically updated!")
    print("You can now kill this server (Ctrl+C) and run the end-to-end tests.")
    print("="*60 + "\n")
    
    return f"""
    <div style='font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'>
        <h2 style='color: #28a745;'>🎉 Success!</h2>
        <p>Successfully vaulted the test card.</p>
        <div style='background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;'>
            <p><strong>Customer ID:</strong> <code>{customer_id}</code></p>
            <p><strong>Token ID:</strong> <code>{token_id}</code></p>
        </div>
        <p>Your <code>.env</code> file has been <strong>automatically updated</strong> with these IDs, and your B2B API keys were automatically copied over to the B2C configuration.</p>
        <p style='color: #666;'>You can now close this tab and stop the terminal server (Ctrl+C).</p>
    </div>
    """

if __name__ == "__main__":
    print("\nStarting B2C Token Generator Server...")
    print("👉 Open your browser and go to: http://localhost:8001")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
