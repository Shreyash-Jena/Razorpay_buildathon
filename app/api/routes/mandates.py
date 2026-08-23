"""Mandate API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.mandate_service import MandateService
from app.schemas.mandates import CreateMandateRequest, MandateResponse

router = APIRouter(prefix="/mandates", tags=["mandates"])


@router.post("", response_model=None)
async def create_mandate(
    req: CreateMandateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new signed mandate for an agent.
    Returns the mandate details + the private key (shown only once).
    """
    service = MandateService(db)
    response, private_key = await service.create_mandate(req)
    await db.commit()
    return {
        **response.model_dump(),
        "private_key": private_key,
        "warning": "Store this private key securely. It will not be shown again.",
    }


@router.get("/{mandate_id}", response_model=MandateResponse)
async def get_mandate(
    mandate_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get mandate status. Never exposes private keys or signatures."""
    service = MandateService(db)
    mandate = await service.get_mandate(mandate_id)
    if mandate is None:
        raise HTTPException(status_code=404, detail="Mandate not found")

    scope = service.parse_scope(mandate)
    return MandateResponse(
        mandate_id=mandate.id,
        agent_id=mandate.agent_id,
        financial_ceiling_paise=mandate.financial_ceiling_paise,
        financial_ceiling_display=f"₹{mandate.financial_ceiling_paise / 100:,.2f}",
        scope=scope,
        max_transactions=mandate.max_transactions,
        is_active=mandate.is_active,
    )


@router.post("/{mandate_id}/revoke")
async def revoke_mandate(
    mandate_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Revoke a mandate immediately."""
    service = MandateService(db)
    success = await service.revoke_mandate(mandate_id)
    if not success:
        raise HTTPException(status_code=404, detail="Mandate not found")
    await db.commit()
    return {"success": True, "message": "Mandate revoked."}
