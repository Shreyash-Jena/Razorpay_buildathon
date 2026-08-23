"""Processed intent hashes for replay protection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProcessedIntent(Base):
    __tablename__ = "processed_intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    intent_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nonce: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    mandate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
