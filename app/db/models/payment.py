"""Payment model — tracks Razorpay payment state."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    razorpay_payment_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)
    razorpay_order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="created")
    method: Mapped[str] = mapped_column(String(50), default="")
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_event_id: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
