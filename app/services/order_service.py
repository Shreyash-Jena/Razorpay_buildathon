"""
Order service — orchestrates the full purchase flow.

Flow: Validate → Policy Gate → Reserve Inventory → Razorpay → Persist → Audit
Uses two-transaction pattern to avoid holding DB locks during external API calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.order import Order, OrderItem
from app.db.models.product import Product
from app.core.constants import OrderStatus, AuditOutcome
from app.core.exceptions import (
    ProductNotFoundError,
    DuplicateRequestError,
    PaymentCreationError,
)
from app.services.policy_gate import PolicyGate, AgentContext, PurchaseIntent
from app.services.inventory_service import InventoryService
from app.services.audit_service import AuditService
from app.integrations.razorpay_client import RazorpayClient
from app.schemas.orders import CreateOrderRequest, OrderResponse
from app.core.logging import get_logger

logger = get_logger("order_service")


class OrderService:
    """Orchestrates order creation through the full authorization pipeline."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.policy_gate = PolicyGate(db)
        self.inventory_service = InventoryService(db)
        self.audit_service = AuditService(db)
        self.razorpay = RazorpayClient()

    async def create_order(self, req: CreateOrderRequest) -> OrderResponse | dict:
        """
        Full order creation pipeline:
        1. Check idempotency
        2. Load product
        3. Calculate authoritative total (NEVER trust agent-provided amount)
        4. Policy Gate authorization
        5. Reserve inventory
        6. Create local pending order
        7. Call Razorpay
        8. Persist Razorpay order ID
        9. Write audit event
        10. Return order
        """
        request_id = str(uuid.uuid4())

        # --- Step 1: Idempotency check ---
        idempotency_key = f"{req.agent_id}:{req.mandate_id}:{req.nonce}"
        existing = await self._check_idempotency(idempotency_key)
        if existing:
            logger.info("Duplicate request detected", idempotency_key=idempotency_key)
            return self._order_to_response(existing)

        # --- Step 2: Load product ---
        product = await self._get_product(req.sku)
        if product is None:
            raise ProductNotFoundError(req.sku)

        # --- Step 3: Authoritative price (NEVER trust agent amount) ---
        authoritative_total = product.price_paise * req.quantity

        # --- Step 4: Policy Gate ---
        agent_ctx = AgentContext(
            agent_id=req.agent_id,
            mandate_id=req.mandate_id,
            request_id=request_id,
        )
        intent = PurchaseIntent(
            sku=req.sku,
            quantity=req.quantity,
            nonce=req.nonce,
            timestamp=datetime.now(timezone.utc).isoformat(),
            signed_intent=req.signed_intent,
            rationale=req.rationale,
        )

        decision = await self.policy_gate.authorize(agent_ctx, intent)

        if not decision.allowed:
            # Log the blocked attempt
            await self.audit_service.log(
                agent_id=req.agent_id,
                tool_invoked="create_order",
                outcome=AuditOutcome.BLOCKED_BY_POLICY_GATE,
                input_payload={
                    "sku": req.sku,
                    "quantity": req.quantity,
                    "authoritative_amount": authoritative_total,
                },
                rationale=req.rationale,
                policy_result=decision.model_dump(),
                request_id=request_id,
                decision_id=decision.decision_id,
                mandate_id=req.mandate_id,
                error_code=decision.reason_code,
            )
            await self.db.commit()

            # Return structured error for the agent
            return {
                "success": False,
                "error": {
                    "code": decision.reason_code,
                    "reason": decision.reason,
                    "retryable": False,
                    "human_action_required": decision.reason_code in [
                        "AMOUNT_EXCEEDS_LIMIT", "SKU_NOT_ALLOWED"
                    ],
                    "metadata": decision.metadata,
                },
            }

        # --- Step 5: Reserve inventory ---
        await self.inventory_service.reserve_stock(req.sku, req.quantity)

        # --- Step 6: Create local pending order ---
        order_id = str(uuid.uuid4())
        receipt = f"rcpt_{order_id[:8]}"

        order = Order(
            id=order_id,
            agent_id=req.agent_id,
            mandate_id=req.mandate_id,
            total_amount_paise=authoritative_total,
            currency="INR",
            status=OrderStatus.PENDING_EXTERNAL.value,
            idempotency_key=idempotency_key,
            receipt=receipt,
        )
        order_item = OrderItem(
            order_id=order_id,
            product_id=product.id,
            sku=product.sku,
            quantity=req.quantity,
            unit_price_paise=product.price_paise,
            subtotal_paise=authoritative_total,
        )
        self.db.add(order)
        self.db.add(order_item)
        await self.db.flush()

        # --- Step 7: Call Razorpay ---
        try:
            rz_order = await self.razorpay.create_order(
                amount_paise=authoritative_total,
                currency="INR",
                receipt=receipt,
                notes={
                    "agent_id": req.agent_id,
                    "mandate_id": req.mandate_id,
                    "sku": req.sku,
                },
            )
            razorpay_order_id = rz_order.get("id", "")
        except PaymentCreationError:
            # Restore inventory on failure
            await self.inventory_service.restore_stock(req.sku, req.quantity)
            order.status = OrderStatus.FAILED.value
            await self.audit_service.log(
                agent_id=req.agent_id,
                tool_invoked="create_order",
                outcome=AuditOutcome.FAILED,
                input_payload={"sku": req.sku, "quantity": req.quantity},
                rationale=req.rationale,
                request_id=request_id,
                decision_id=decision.decision_id,
                mandate_id=req.mandate_id,
                error_code="PAYMENT_CREATION_FAILED",
                order_id=order_id,
            )
            await self.db.commit()
            raise

        # --- Step 8: Persist Razorpay order ID ---
        order.razorpay_order_id = razorpay_order_id
        order.transition_to(OrderStatus.CREATED)

        # --- Step 9: Audit success ---
        await self.audit_service.log(
            agent_id=req.agent_id,
            tool_invoked="create_order",
            outcome=AuditOutcome.SUCCESS,
            input_payload={
                "sku": req.sku,
                "quantity": req.quantity,
                "authoritative_amount": authoritative_total,
            },
            rationale=req.rationale,
            policy_result=decision.model_dump(),
            request_id=request_id,
            decision_id=decision.decision_id,
            mandate_id=req.mandate_id,
            order_id=order_id,
            razorpay_order_id=razorpay_order_id,
        )

        await self.db.commit()

        # --- Step 10: Return ---
        return self._order_to_response(order, product.sku, req.quantity)

    async def get_order(self, order_id: str) -> Order | None:
        """Fetch an order by ID."""
        from sqlalchemy.orm import selectinload
        stmt = select(Order).where(Order.id == order_id).options(selectinload(Order.items))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def simulate_payment(self, order_id: str) -> dict:
        """Simulate a successful Razorpay payment to trigger the rest of the flow."""
        order = await self.get_order(order_id)
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order.status != OrderStatus.CREATED.value:
            return {"success": False, "error": f"Cannot pay order in status {order.status}"}
            
        order.transition_to(OrderStatus.CAPTURED)
        await self.db.commit()
        
        logger.info("Simulated payment successful", order_id=order_id)
        return {"success": True, "order_id": order_id, "status": "captured"}

    async def get_order_by_razorpay_id(self, razorpay_order_id: str) -> Order | None:
        """Fetch an order by Razorpay order ID."""
        stmt = select(Order).where(Order.razorpay_order_id == razorpay_order_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # --- Private helpers ---

    async def _check_idempotency(self, key: str) -> Order | None:
        from sqlalchemy.orm import selectinload
        stmt = select(Order).where(Order.idempotency_key == key).options(selectinload(Order.items))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_product(self, sku: str) -> Product | None:
        stmt = select(Product).where(Product.sku == sku)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _order_to_response(self, order: Order, sku: str = "", quantity: int = 0) -> OrderResponse:
        return OrderResponse(
            success=True,
            order_id=order.id,
            razorpay_order_id=order.razorpay_order_id or "",
            agent_id=order.agent_id,
            sku=sku,
            quantity=quantity,
            total_amount_paise=order.total_amount_paise,
            total_display=f"Rs.{order.total_amount_paise / 100:,.2f}",
            currency=order.currency,
            status=order.status,
            receipt=order.receipt,
        )
