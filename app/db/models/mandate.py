"""Mandate model — cryptographic authorization for agent spending."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Mandate(Base):
    __tablename__ = "mandates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    principal_id: Mapped[str] = mapped_column(String(100), nullable=False)
    financial_ceiling_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    # Typed scope as JSON string: {"sku": [...], "category": [...], "vendor": [...]}
    scope_type: Mapped[str] = mapped_column(String(50), default="combined")
    scope_values: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    max_transactions: Mapped[int] = mapped_column(Integer, default=10)
    velocity_window_seconds: Mapped[int] = mapped_column(Integer, default=86400)  # 24 hours
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    # Ed25519 signature of the canonical mandate payload
    signature: Mapped[str] = mapped_column(Text, default="")
    # Public key for verification
    public_key: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
