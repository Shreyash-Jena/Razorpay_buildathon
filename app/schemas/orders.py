"""Pydantic schemas for orders."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    agent_id: str = Field(..., description="Agent identifier")
    mandate_id: str = Field(..., description="Mandate UUID")
    sku: str = Field(..., description="Product SKU to purchase")
    quantity: int = Field(..., ge=1, le=100, description="Quantity to purchase")
    rationale: str = Field(default="", description="Agent's reasoning for this purchase")
    nonce: str = Field(..., description="Unique nonce for replay protection")
    signed_intent: str = Field(default="", description="Ed25519 signature of canonical intent")
    payment_mode: str = Field(default="b2b", description="b2b (Smart Collect) or b2c (Tokenized)")


class OrderResponse(BaseModel):
    success: bool = True
    order_id: str = ""
    razorpay_order_id: str = ""
    agent_id: str = ""
    sku: str = ""
    quantity: int = 0
    total_amount_paise: int = 0
    total_display: str = ""
    currency: str = "INR"
    status: str = ""
    receipt: str = ""
    virtual_account_id: str = ""
    payment_mode: str = "b2b"


class OrderStatusResponse(BaseModel):
    success: bool = True
    order_id: str
    razorpay_order_id: str = ""
    status: str
    total_amount_paise: int
    currency: str = "INR"
