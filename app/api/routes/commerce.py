"""Commerce API routes — order creation and lookup."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.order_service import OrderService
from app.schemas.orders import CreateOrderRequest, OrderResponse, OrderStatusResponse
from app.core.exceptions import (
    AgenticCommerceError,
    ProductNotFoundError,
    PaymentCreationError,
)

router = APIRouter(prefix="/orders", tags=["commerce"])


@router.post("", response_model=None)
async def create_order(
    req: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a purchase order.

    The request passes through the full authorization pipeline:
    Idempotency → Product → Policy Gate → Inventory → Razorpay → Audit
    """
    service = OrderService(db)
    try:
        result = await service.create_order(req)
        if isinstance(result, dict) and not result.get("success", True):
            raise HTTPException(status_code=403, detail=result)
        return result
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.to_error_envelope())
    except PaymentCreationError as e:
        raise HTTPException(status_code=502, detail=e.to_error_envelope())
    except AgenticCommerceError as e:
        raise HTTPException(status_code=400, detail=e.to_error_envelope())


@router.get("/{order_id}", response_model=OrderStatusResponse)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get order status by ID."""
    service = OrderService(db)
    order = await service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderStatusResponse(
        order_id=order.id,
        razorpay_order_id=order.razorpay_order_id or "",
        status=order.status,
        total_amount_paise=order.total_amount_paise,
        currency=order.currency,
    )
