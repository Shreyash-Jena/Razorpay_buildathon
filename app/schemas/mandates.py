"""Pydantic schemas for mandates."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MandateScope(BaseModel):
    """Typed scope representation."""
    sku: list[str] = Field(default_factory=list)
    category: list[str] = Field(default_factory=list)
    vendor: list[str] = Field(default_factory=list)


class CreateMandateRequest(BaseModel):
    agent_id: str
    principal_id: str = "human-principal"
    financial_ceiling_paise: int = Field(..., gt=0)
    scope: MandateScope = Field(default_factory=MandateScope)
    max_transactions: int = Field(default=10, ge=1)
    velocity_window_seconds: int = Field(default=86400)
    expires_in_hours: int | None = Field(default=24)


class MandateResponse(BaseModel):
    success: bool = True
    mandate_id: str = ""
    agent_id: str = ""
    financial_ceiling_paise: int = 0
    financial_ceiling_display: str = ""
    scope: MandateScope = Field(default_factory=MandateScope)
    max_transactions: int = 0
    is_active: bool = True


class PolicyDecision(BaseModel):
    """Every policy evaluation produces this structured result."""
    allowed: bool
    decision_id: str = ""
    reason_code: str = ""
    reason: str = ""
    mandate_id: str = ""
    agent_id: str = ""
    requested_amount_paise: int = 0
    financial_ceiling_paise: int = 0
    metadata: dict = Field(default_factory=dict)
