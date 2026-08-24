from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.order_service import OrderService
from app.core.config import get_settings

router = APIRouter(tags=["checkout"])

@router.get("/checkout/{order_id}", response_class=HTMLResponse)
async def render_checkout(
    order_id: str,
    request: Request,
    mock: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Render the Razorpay Checkout widget for an order."""
    service = OrderService(db)
    order = await service.get_order(order_id)
    if not order or not order.razorpay_order_id:
        raise HTTPException(status_code=404, detail="Order not found or not initialized with Razorpay")

    settings = get_settings()
    razorpay_key = settings.razorpay_key_id
    razorpay_secret = settings.razorpay_key_secret

    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/orders/verify_payment"

    if mock:
        # Generate valid mock signature
        import hmac, hashlib
        mock_payment_id = "pay_mock123456789"
        msg = f"{order.razorpay_order_id}|{mock_payment_id}"
        mock_signature = hmac.new(
            razorpay_secret.encode(), 
            msg.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Mock Checkout</title></head>
        <body>
            <div id="payment-success-marker" style="display:none;">Success</div>
            <button id="mock-pay-button" onclick="pay()">Simulate Payment</button>
            <script>
            function pay() {{
                fetch("{callback_url}", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        "order_id": "{order.id}",
                        "razorpay_payment_id": "{mock_payment_id}",
                        "razorpay_order_id": "{order.razorpay_order_id}",
                        "razorpay_signature": "{mock_signature}"
                    }})
                }}).then(res => res.json()).then(data => {{
                    if(data.success) document.getElementById('payment-success-marker').style.display = 'block';
                }});
            }}
            </script>
        </body>
        </html>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Razorpay Checkout Simulation</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f9f9f9; }}
            .loader {{ border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            .message {{ margin-left: 15px; font-size: 16px; color: #555; }}
            .container {{ display: flex; align-items: center; background: white; padding: 20px 40px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="loader"></div>
            <div class="message">Initializing Secure Checkout...</div>
        </div>

        <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
        <script>
            var options = {{
                "key": "{razorpay_key}",
                "amount": "{order.total_amount_paise}",
                "currency": "{order.currency}",
                "name": "Agentic Commerce",
                "description": "Test Transaction",
                "order_id": "{order.razorpay_order_id}",
                "handler": function (response) {{
                    document.querySelector('.message').innerText = "Verifying payment...";
                    fetch("{callback_url}", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{
                            "order_id": "{order.id}",
                            "razorpay_payment_id": response.razorpay_payment_id,
                            "razorpay_order_id": response.razorpay_order_id,
                            "razorpay_signature": response.razorpay_signature
                        }})
                    }}).then(res => res.json())
                      .then(data => {{
                          if(data.success) {{
                              document.querySelector('.message').innerText = "Payment Successful!";
                              document.querySelector('.loader').style.display = 'none';
                              // Append a success element for playwright to detect
                              var successDiv = document.createElement("div");
                              successDiv.id = "payment-success-marker";
                              document.body.appendChild(successDiv);
                          }} else {{
                              document.querySelector('.message').innerText = "Verification failed.";
                          }}
                      }}).catch(err => {{
                          document.querySelector('.message').innerText = "Error verifying payment.";
                      }});
                }},
                "prefill": {{
                    "name": "Test User",
                    "email": "test@example.com",
                    "contact": "9999999999"
                }},
                "theme": {{
                    "color": "#3399cc"
                }}
            }};
            var rzp1 = new Razorpay(options);
            rzp1.on('payment.failed', function (response){{
                alert("Payment Failed");
            }});
            
            // Auto open the checkout when the page loads
            window.onload = function() {{
                rzp1.open();
            }};
        </script>
    </body>
    </html>
    """
    return html_content
