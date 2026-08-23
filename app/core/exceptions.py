"""Domain exceptions — mapped to HTTP only at the API boundary."""

from __future__ import annotations


class AgenticCommerceError(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str, code: str, retryable: bool = False,
                 human_action_required: bool = False, metadata: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.human_action_required = human_action_required
        self.metadata = metadata or {}

    def to_error_envelope(self) -> dict:
        """Standard structured error response for agents."""
        return {
            "success": False,
            "error": {
                "code": self.code,
                "reason": self.message,
                "retryable": self.retryable,
                "human_action_required": self.human_action_required,
                "metadata": self.metadata,
            },
        }


class MandateViolationError(AgenticCommerceError):
    """Raised when a transaction violates the agent's mandate."""

    def __init__(self, message: str, code: str = "MANDATE_BREACH", **kwargs):
        super().__init__(message, code, **kwargs)


class SignatureVerificationError(AgenticCommerceError):
    """Raised when signed intent verification fails."""

    def __init__(self, message: str = "Invalid signature."):
        super().__init__(message, code="INVALID_SIGNATURE")


class ReplayDetectedError(AgenticCommerceError):
    """Raised on duplicate nonce/intent replay."""

    def __init__(self, message: str = "Replay detected. This intent was already processed."):
        super().__init__(message, code="REPLAY_DETECTED")


class OutOfStockError(AgenticCommerceError):
    """Raised when a product is out of stock."""

    def __init__(self, sku: str, substitute_sku: str | None = None):
        meta = {"sku": sku}
        if substitute_sku:
            meta["substitute_sku"] = substitute_sku
        super().__init__(
            f"Product {sku} is out of stock.",
            code="OUT_OF_STOCK",
            retryable=False,
            human_action_required=substitute_sku is not None,
            metadata=meta,
        )


class ProductNotFoundError(AgenticCommerceError):
    """Raised when a product SKU does not exist."""

    def __init__(self, sku: str):
        super().__init__(f"Product {sku} not found.", code="PRODUCT_NOT_FOUND")


class ProductInactiveError(AgenticCommerceError):
    """Raised when a product is inactive."""

    def __init__(self, sku: str):
        super().__init__(f"Product {sku} is inactive.", code="PRODUCT_INACTIVE")


class PaymentCreationError(AgenticCommerceError):
    """Raised when Razorpay order creation fails."""

    def __init__(self, message: str = "Failed to create payment order."):
        super().__init__(message, code="PAYMENT_CREATION_FAILED", retryable=True)


class DuplicateRequestError(AgenticCommerceError):
    """Raised on duplicate idempotency key."""

    def __init__(self, message: str = "Duplicate request."):
        super().__init__(message, code="DUPLICATE_REQUEST")


class WebhookVerificationError(AgenticCommerceError):
    """Raised when webhook signature verification fails."""

    def __init__(self, message: str = "Webhook signature verification failed."):
        super().__init__(message, code="WEBHOOK_VERIFICATION_FAILED")


class InsufficientSupportError(AgenticCommerceError):
    """Raised when graph data is too thin for a recommendation."""

    def __init__(self, message: str = "Insufficient data for recommendation."):
        super().__init__(message, code="INSUFFICIENT_SUPPORT")
