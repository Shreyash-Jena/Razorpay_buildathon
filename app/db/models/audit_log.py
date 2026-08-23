"""Audit log model — append-only, hash-chained flight recorder."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuditLog(Base):
    """
    Immutable flight recorder.

    Rules:
    - Application layer: No update/delete methods exist.
    - Cryptographic layer: Hash chain ensures tamper detection.
    """
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36), default="")
    decision_id: Mapped[str] = mapped_column(String(36), default="")
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    mandate_id: Mapped[str] = mapped_column(String(36), default="")
    tool_invoked: Mapped[str] = mapped_column(String(100), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), default="tool_call")
    input_payload: Mapped[str] = mapped_column(Text, default="{}")
    normalized_intent: Mapped[str] = mapped_column(Text, default="{}")
    rationale: Mapped[str] = mapped_column(Text, default="")
    policy_result: Mapped[str] = mapped_column(Text, default="{}")
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    error_code: Mapped[str] = mapped_column(String(50), default="")
    order_id: Mapped[str] = mapped_column(String(36), default="")
    razorpay_order_id: Mapped[str] = mapped_column(String(100), default="")
    # Hash chain for tamper detection
    previous_log_hash: Mapped[str] = mapped_column(String(64), default="GENESIS")
    current_log_hash: Mapped[str] = mapped_column(String(64), nullable=False)
