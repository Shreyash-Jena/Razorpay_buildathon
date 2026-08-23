"""Import all models so SQLAlchemy registers them."""

from app.db.models.product import Product
from app.db.models.order import Order, OrderItem
from app.db.models.mandate import Mandate
from app.db.models.audit_log import AuditLog
from app.db.models.payment import Payment
from app.db.models.webhook_event import WebhookEvent
from app.db.models.upsell import UpsellRecommendation
from app.db.models.processed_intent import ProcessedIntent

__all__ = [
    "Product",
    "Order",
    "OrderItem",
    "Mandate",
    "AuditLog",
    "Payment",
    "WebhookEvent",
    "UpsellRecommendation",
    "ProcessedIntent",
]
