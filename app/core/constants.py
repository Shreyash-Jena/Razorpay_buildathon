"""Enum constants used across the application."""

from __future__ import annotations

import enum


class OrderStatus(str, enum.Enum):
    """Order state machine — valid transitions enforced in service layer."""
    PENDING_EXTERNAL = "pending_external"
    CREATED = "created"
    CAPTURED = "captured"
    FAILED = "failed"
    EXPIRED = "expired"


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class WebhookStatus(str, enum.Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class UpsellStatus(str, enum.Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AuditOutcome(str, enum.Enum):
    SUCCESS = "success"
    BLOCKED_BY_POLICY_GATE = "blocked_by_policy_gate"
    FAILED = "failed"
    ERROR = "error"


class PolicyReasonCode(str, enum.Enum):
    """Structured reason codes for policy decisions."""
    INVALID_AGENT = "INVALID_AGENT"
    MANDATE_NOT_FOUND = "MANDATE_NOT_FOUND"
    MANDATE_REVOKED = "MANDATE_REVOKED"
    MANDATE_EXPIRED = "MANDATE_EXPIRED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    SKU_NOT_ALLOWED = "SKU_NOT_ALLOWED"
    CATEGORY_NOT_ALLOWED = "CATEGORY_NOT_ALLOWED"
    AMOUNT_EXCEEDS_LIMIT = "AMOUNT_EXCEEDS_LIMIT"
    VELOCITY_LIMIT_EXCEEDED = "VELOCITY_LIMIT_EXCEEDED"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    PRODUCT_INACTIVE = "PRODUCT_INACTIVE"
    AUTHORIZED = "AUTHORIZED"


# Valid order state transitions
VALID_ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING_EXTERNAL: {OrderStatus.CREATED, OrderStatus.FAILED},
    OrderStatus.CREATED: {OrderStatus.CAPTURED, OrderStatus.FAILED, OrderStatus.EXPIRED},
}
