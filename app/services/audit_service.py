"""
Audit service — append-only, hash-chained flight recorder.

Rules:
- No update methods.
- No delete methods.
- Hash chain: current_hash = SHA256(previous_hash + data).
"""

from __future__ import annotations

import json
import uuid
import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.core.constants import AuditOutcome


class AuditService:
    """
    Append-only flight recorder. NEVER provides update or delete.
    Each entry is hash-chained to the previous for tamper detection.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        agent_id: str,
        tool_invoked: str,
        outcome: AuditOutcome,
        input_payload: dict | None = None,
        rationale: str = "",
        policy_result: dict | None = None,
        request_id: str = "",
        decision_id: str = "",
        mandate_id: str = "",
        error_code: str = "",
        order_id: str = "",
        razorpay_order_id: str = "",
        action_type: str = "tool_call",
        normalized_intent: dict | None = None,
    ) -> AuditLog:
        """Append a new audit entry with hash chain."""

        # Get the hash of the previous entry
        previous_hash = await self._get_last_hash()

        # Compute current hash
        hash_input = (
            previous_hash
            + datetime.now(timezone.utc).isoformat()
            + agent_id
            + tool_invoked
            + json.dumps(input_payload or {}, sort_keys=True)
            + outcome.value
        )
        current_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        entry = AuditLog(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            request_id=request_id or str(uuid.uuid4()),
            decision_id=decision_id,
            agent_id=agent_id,
            mandate_id=mandate_id,
            tool_invoked=tool_invoked,
            action_type=action_type,
            input_payload=json.dumps(input_payload or {}),
            normalized_intent=json.dumps(normalized_intent or {}),
            rationale=rationale,
            policy_result=json.dumps(policy_result or {}),
            outcome=outcome.value,
            error_code=error_code,
            order_id=order_id,
            razorpay_order_id=razorpay_order_id,
            previous_log_hash=previous_hash,
            current_log_hash=current_hash,
        )

        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_trail(
        self,
        agent_id: str | None = None,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Retrieve audit trail — read only."""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        if agent_id:
            stmt = stmt.where(AuditLog.agent_id == agent_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def verify_chain(self) -> dict:
        """Verify the hash chain integrity."""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.asc())
        result = await self.db.execute(stmt)
        entries = list(result.scalars().all())

        if not entries:
            return {"valid": True, "entries_checked": 0}

        for i, entry in enumerate(entries):
            if i == 0:
                if entry.previous_log_hash != "GENESIS":
                    return {
                        "valid": False,
                        "broken_at": entry.id,
                        "reason": "First entry does not have GENESIS hash",
                    }
            else:
                if entry.previous_log_hash != entries[i - 1].current_log_hash:
                    return {
                        "valid": False,
                        "broken_at": entry.id,
                        "reason": "Hash chain broken — possible tampering",
                    }

        return {"valid": True, "entries_checked": len(entries)}

    async def _get_last_hash(self) -> str:
        """Get the hash of the most recent audit entry."""
        stmt = select(AuditLog.current_log_hash).order_by(AuditLog.timestamp.desc()).limit(1)
        result = await self.db.execute(stmt)
        last_hash = result.scalar_one_or_none()
        return last_hash or "GENESIS"
