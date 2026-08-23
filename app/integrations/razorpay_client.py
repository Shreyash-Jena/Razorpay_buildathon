"""
Razorpay adapter — isolated integration layer.

The business layer depends on this abstraction, not on razorpay.Client directly.
All calls use test-mode API keys.
"""

from __future__ import annotations

import hmac
import hashlib
import json

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import PaymentCreationError, WebhookVerificationError

logger = get_logger("razorpay_client")


class RazorpayClient:
    """Abstracted Razorpay adapter for testable, isolated integration."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Razorpay SDK client."""
        if self._client is None:
            if not self.settings.razorpay_key_id or not self.settings.razorpay_key_secret:
                logger.warning("Razorpay credentials not configured — using mock mode")
                return None
            try:
                import razorpay
                self._client = razorpay.Client(
                    auth=(self.settings.razorpay_key_id, self.settings.razorpay_key_secret)
                )
            except Exception as e:
                logger.error("Failed to initialize Razorpay client", error=str(e))
                return None
        return self._client

    async def create_order(
        self,
        amount_paise: int,
        currency: str = "INR",
        receipt: str = "",
        notes: dict | None = None,
    ) -> dict:
        """
        Create a Razorpay order.
        Returns the order data dict or raises PaymentCreationError.
        """
        client = self._get_client()

        if client is None:
            # Mock mode — return a simulated order for demo
            import uuid
            mock_order_id = f"order_mock_{uuid.uuid4().hex[:12]}"
            logger.info("Mock Razorpay order created", order_id=mock_order_id, amount=amount_paise)
            return {
                "id": mock_order_id,
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt,
                "status": "created",
                "notes": notes or {},
            }

        try:
            order_data = {
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt,
                "notes": notes or {},
            }
            order = client.order.create(data=order_data)
            logger.info("Razorpay order created", order_id=order.get("id"), amount=amount_paise)
            return order
        except Exception as e:
            logger.error("Razorpay order creation failed", error=str(e))
            raise PaymentCreationError(f"Razorpay error: {str(e)}")

    async def fetch_order(self, order_id: str) -> dict:
        """Fetch an order from Razorpay."""
        client = self._get_client()
        if client is None:
            return {"id": order_id, "status": "created", "amount": 0, "currency": "INR"}
        try:
            return client.order.fetch(order_id)
        except Exception as e:
            logger.error("Failed to fetch Razorpay order", order_id=order_id, error=str(e))
            return {}

    async def fetch_payment(self, payment_id: str) -> dict:
        """Fetch a payment from Razorpay."""
        client = self._get_client()
        if client is None:
            return {"id": payment_id, "status": "captured", "amount": 0}
        try:
            return client.payment.fetch(payment_id)
        except Exception as e:
            logger.error("Failed to fetch payment", payment_id=payment_id, error=str(e))
            return {}

    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        """
        Verify Razorpay webhook signature.
        Uses HMAC-SHA256 with the webhook secret.
        """
        if not self.settings.razorpay_webhook_secret:
            logger.warning("Webhook secret not configured — skipping verification")
            return True

        try:
            expected = hmac.new(
                self.settings.razorpay_webhook_secret.encode("utf-8"),
                body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            logger.error("Webhook signature verification failed", error=str(e))
            return False
