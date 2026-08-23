"""Upsell recommendation model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Integer, String, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UpsellRecommendation(Base):
    __tablename__ = "upsell_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_sku: Mapped[str] = mapped_column(String(50), nullable=False)
    recommended_sku: Mapped[str] = mapped_column(String(50), nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    support_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    message: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
