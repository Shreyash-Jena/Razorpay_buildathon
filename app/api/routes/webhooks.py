"""Webhook and Upsell API routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.webhook_event import WebhookEvent
from app.db.models.order import Order, OrderItem
from app.db.models.payment import Payment
from app.core.constants import OrderStatus, PaymentStatus, WebhookStatus
from app.services.upsell_service import UpsellService
from app.integrations.razorpay_client import RazorpayClient
from app.core.logging import get_logger

logger = get_logger("webhooks")

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Razorpay webhook receiver.
    Flow: Verify Signature → Validate → Deduplicate → Persist → ACK 200 → Process async
    """
    body = await request.body()
    body_str = body.decode("utf-8")

    # Parse event
    try:
        event_data = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = event_data.get("event", "") + "_" + str(event_data.get("payload", {}).get(
        "payment", {}).get("entity", {}).get("id", "unknown"))
    event_type = event_data.get("event", "unknown")

    # Verify signature (lenient if not configured)
    signature = request.headers.get("X-Razorpay-Signature", "")
    rz_client = RazorpayClient()
    sig_verified = rz_client.verify_webhook_signature(body_str, signature)

    # Deduplicate
    existing = await db.execute(
        select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    )
    if existing.scalar_one_or_none():
        logger.info("Duplicate webhook ignored", event_id=event_id)
        return {"status": "already_processed"}

    # Persist event
    webhook_event = WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payload=body_str,
        signature_verified=sig_verified,
        processing_status=WebhookStatus.RECEIVED.value,
    )
    db.add(webhook_event)
    await db.flush()

    # Process based on event type
    try:
        if event_type == "payment.captured":
            await _process_payment_captured(db, event_data, webhook_event)
        elif event_type == "payment.failed":
            await _process_payment_failed(db, event_data, webhook_event)

        webhook_event.processing_status = WebhookStatus.PROCESSED.value
        webhook_event.processed_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.error("Webhook processing failed", event_id=event_id, error=str(e))
        webhook_event.processing_status = WebhookStatus.FAILED.value
        webhook_event.error_message = str(e)

    await db.commit()
    return {"status": "ok"}


async def _process_payment_captured(
    db: AsyncSession,
    event_data: dict,
    webhook_event: WebhookEvent,
):
    """Process payment.captured → update order → trigger upsell."""
    payment_entity = event_data.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_payment_id = payment_entity.get("id", "")
    razorpay_order_id = payment_entity.get("order_id", "")
    amount = payment_entity.get("amount", 0)

    # Create/update payment record
    payment = Payment(
        razorpay_payment_id=razorpay_payment_id,
        razorpay_order_id=razorpay_order_id,
        amount_paise=amount,
        status=PaymentStatus.CAPTURED.value,
        method=payment_entity.get("method", ""),
        captured_at=datetime.now(timezone.utc),
        raw_event_id=webhook_event.event_id,
    )
    db.add(payment)

    # Update order status
    stmt = select(Order).where(Order.razorpay_order_id == razorpay_order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order and order.status == OrderStatus.CREATED.value:
        order.transition_to(OrderStatus.CAPTURED)

        # Trigger upsell analysis
        if order.items:
            upsell_service = UpsellService(db)
            source_sku = order.items[0].sku
            await upsell_service.get_recommendation(
                source_sku=source_sku,
                source_order_id=order.id,
            )

        logger.info("Payment captured and upsell triggered",
                     order_id=order.id, razorpay_order_id=razorpay_order_id)


async def _process_payment_failed(
    db: AsyncSession,
    event_data: dict,
    webhook_event: WebhookEvent,
):
    """Process payment.failed → update order status."""
    payment_entity = event_data.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_order_id = payment_entity.get("order_id", "")

    stmt = select(Order).where(Order.razorpay_order_id == razorpay_order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if order and order.status == OrderStatus.CREATED.value:
        order.transition_to(OrderStatus.FAILED)
        logger.info("Payment failed", order_id=order.id)


# --- Upsell endpoints ---

upsell_router = APIRouter(prefix="/upsells", tags=["upsells"])


@upsell_router.get("/{order_id}")
async def get_upsell(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get upsell recommendation for a completed order."""
    service = UpsellService(db)
    rec = await service.get_upsell(order_id)
    if rec is None:
        return {"success": True, "has_recommendation": False}
    return {
        "success": True,
        "has_recommendation": True,
        "recommendation": {
            "id": rec.id,
            "source_sku": rec.source_sku,
            "recommended_sku": rec.recommended_sku,
            "co_purchase_probability": rec.probability,
            "support_count": rec.support_count,
            "message": rec.message,
            "status": rec.status,
        },
    }


@upsell_router.post("/{upsell_id}/accept")
async def accept_upsell(
    upsell_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Accept an upsell recommendation."""
    service = UpsellService(db)
    success = await service.accept_upsell(upsell_id)
    if not success:
        raise HTTPException(status_code=404, detail="Upsell not found or not in PROPOSED state")
    await db.commit()
    return {"success": True, "message": "Upsell accepted. Must pass Policy Gate before purchase."}


@upsell_router.post("/{upsell_id}/reject")
async def reject_upsell(
    upsell_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Reject an upsell recommendation."""
    service = UpsellService(db)
    success = await service.reject_upsell(upsell_id)
    if not success:
        raise HTTPException(status_code=404, detail="Upsell not found or not in PROPOSED state")
    await db.commit()
    return {"success": True, "message": "Upsell rejected."}
