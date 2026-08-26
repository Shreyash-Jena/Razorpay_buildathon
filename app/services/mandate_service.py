"""Mandate service — CRUD + Ed25519 signing for agent authorization."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.mandate import Mandate
from app.schemas.mandates import CreateMandateRequest, MandateResponse, MandateScope
from app.core.security import CryptoService
from app.core.exceptions import AgenticCommerceError
from app.core.logging import get_logger

logger = get_logger("mandate_service")

class MandateService:
    """Manage agent mandates — the authorization contracts from human principals."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_mandate(self, req: CreateMandateRequest) -> tuple[MandateResponse, str]:
        """
        Create a new signed mandate.
        Returns (MandateResponse, private_key_b64) — the private key is only
        returned once at creation for the agent to use.
        """
        private_key, public_key = CryptoService.generate_keypair()
        mandate_id = str(uuid.uuid4())

        scope_dict = req.scope.model_dump()
        scope_json = json.dumps(scope_dict)

        # Build canonical payload and sign
        mandate_data = {
            "agent_id": req.agent_id,
            "principal_id": req.principal_id,
            "financial_ceiling_paise": req.financial_ceiling_paise,
            "scope_values": scope_json,
            "max_transactions": req.max_transactions,
            "velocity_window_seconds": req.velocity_window_seconds,
        }
        canonical = CryptoService.build_mandate_canonical(mandate_data)
        signature = CryptoService.sign(canonical, private_key)

        expires_at = None
        if req.expires_in_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours)

        mandate = Mandate(
            id=mandate_id,
            agent_id=req.agent_id,
            principal_id=req.principal_id,
            financial_ceiling_paise=req.financial_ceiling_paise,
            scope_values=scope_json,
            max_transactions=req.max_transactions,
            velocity_window_seconds=req.velocity_window_seconds,
            expires_at=expires_at,
            signature=signature,
            public_key=public_key,
        )

        self.db.add(mandate)
        await self.db.flush()

        response = MandateResponse(
            mandate_id=mandate_id,
            agent_id=req.agent_id,
            financial_ceiling_paise=req.financial_ceiling_paise,
            financial_ceiling_display=f"₹{req.financial_ceiling_paise / 100:,.2f}",
            scope=req.scope,
            max_transactions=req.max_transactions,
            is_active=True,
        )

        return response, private_key

    async def get_mandate(self, mandate_id: str) -> Mandate | None:
        """Fetch a mandate by ID."""
        stmt = select(Mandate).where(Mandate.id == mandate_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_mandate_for_agent(self, agent_id: str) -> Mandate | None:
        """Fetch the active mandate for an agent."""
        stmt = (
            select(Mandate)
            .where(Mandate.agent_id == agent_id, Mandate.is_active == True)  # noqa: E712
            .order_by(Mandate.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def revoke_mandate(self, mandate_id: str) -> bool:
        """Revoke a mandate immediately."""
        mandate = await self.get_mandate(mandate_id)
        if mandate is None:
            return False
        mandate.is_active = False
        mandate.revoked_at = datetime.now(timezone.utc)
        return True

    def parse_scope(self, mandate: Mandate) -> MandateScope:
        """Parse the stored scope JSON into a typed object."""
        try:
            scope_dict = json.loads(mandate.scope_values)
            return MandateScope(**scope_dict)
        except Exception:
            return MandateScope()

    async def request_budget_increase(self, mandate_id: str, requested_amount_paise: int, rationale: str) -> dict:
        """
        Agent-to-Agent negotiation. 
        Procurement Agent asks Finance Agent (LLM) for a budget increase.
        """
        mandate = await self.get_mandate(mandate_id)
        if mandate is None or not mandate.is_active:
            return {"success": False, "error": "Mandate not found or inactive"}

        logger.info(
            "Finance Agent evaluating budget request", 
            requested_amount=requested_amount_paise, 
            rationale=rationale
        )

        try:
            # Mocking Finance Agent for Video Demonstration
            logger.info("Finance Agent evaluating (MOCKED FOR DEMO)", rationale=rationale)
            import asyncio
            await asyncio.sleep(1) # simulate delay
            
            # Auto-approve
            mandate.financial_ceiling_paise = requested_amount_paise
            await self.db.commit()
            return {
                "success": True, 
                "approved": True, 
                "new_budget_paise": requested_amount_paise,
                "message": f"Finance Agent approved budget increase to Rs.{requested_amount_paise/100:,.2f}. Reason: Valid business need."
            }
        except Exception as e:
            logger.error("Error evaluating budget request via LLM", error=str(e))
            return {"success": False, "error": "Finance Agent evaluation failed."}
