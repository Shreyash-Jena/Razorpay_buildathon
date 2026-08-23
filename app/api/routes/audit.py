"""Audit trail API routes — read only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/trail")
async def get_audit_trail(
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the audit trail. Read-only — no update/delete endpoints exist.
    """
    service = AuditService(db)
    entries = await service.get_trail(agent_id=agent_id, limit=limit)
    return {
        "success": True,
        "entries": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                "agent_id": e.agent_id,
                "tool_invoked": e.tool_invoked,
                "outcome": e.outcome,
                "rationale": e.rationale,
                "error_code": e.error_code,
                "order_id": e.order_id,
                "razorpay_order_id": e.razorpay_order_id,
                "hash": e.current_log_hash,
            }
            for e in entries
        ],
        "total": len(entries),
    }


@router.get("/verify")
async def verify_chain(db: AsyncSession = Depends(get_db)):
    """Verify the hash chain integrity of the flight recorder."""
    service = AuditService(db)
    return await service.verify_chain()
