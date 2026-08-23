"""
Policy Gate — the most important module.

FINANCIAL SECURITY INVARIANT:
No execution capable of creating, modifying, or authorizing a financial
transaction may reach Razorpay without passing through the Policy Gate.

The LLM is an untrusted decision-making client.
The Policy Gate is the source of authorization truth.
The database is the source of merchant truth.
Razorpay is the source of payment truth.
The Flight Recorder is the source of accountability evidence.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.mandate import Mandate
from app.db.models.order import Order
from app.db.models.product import Product
from app.db.models.processed_intent import ProcessedIntent
from app.core.constants import PolicyReasonCode, OrderStatus
from app.core.security import CryptoService
from app.core.config import get_settings
from app.core.exceptions import (
    MandateViolationError,
    SignatureVerificationError,
    ReplayDetectedError,
    OutOfStockError,
    ProductNotFoundError,
    ProductInactiveError,
)
from app.schemas.mandates import PolicyDecision, MandateScope


@dataclass
class AgentContext:
    """Normalized agent request context."""
    agent_id: str
    mandate_id: str
    request_id: str
    session_id: str = ""
    model_provider: str = ""
    model_name: str = ""


@dataclass
class PurchaseIntent:
    """What the agent wants to do."""
    sku: str
    quantity: int
    nonce: str
    timestamp: str
    signed_intent: str = ""
    rationale: str = ""


class PolicyGate:
    """
    Server-side authorization — 11-step evaluation pipeline.

    Order of checks:
    1. Authenticate Agent
    2. Resolve Mandate
    3. Verify Signature (optional for demo)
    4. Check Mandate Active
    5. Check Expiry
    6. Check Scope
    7. Check Product Availability
    8. Calculate Authoritative Price
    9. Check Financial Ceiling
    10. Check Velocity
    11. Check Replay Protection
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def authorize(
        self,
        agent_context: AgentContext,
        intent: PurchaseIntent,
    ) -> PolicyDecision:
        """
        Run the full policy evaluation pipeline.
        Returns a PolicyDecision — NEVER raises for policy violations.
        Policy violations are returned as structured denials.
        """
        decision_id = str(uuid.uuid4())

        # --- Step 1: Validate agent ID ---
        if not agent_context.agent_id:
            return self._deny(decision_id, agent_context, intent, 0,
                              PolicyReasonCode.INVALID_AGENT, "Missing agent identity.")

        # --- Step 2: Resolve mandate ---
        mandate = await self._resolve_mandate(agent_context.mandate_id)
        if mandate is None:
            return self._deny(decision_id, agent_context, intent, 0,
                              PolicyReasonCode.MANDATE_NOT_FOUND,
                              f"Mandate {agent_context.mandate_id} not found.")

        # --- Step 3: Verify signature (lenient for demo — allow empty) ---
        if intent.signed_intent:
            product = await self._get_product(intent.sku)
            if product:
                authoritative_amount = product.price_paise * intent.quantity
                intent_data = {
                    "agent_id": agent_context.agent_id,
                    "mandate_id": agent_context.mandate_id,
                    "sku": intent.sku,
                    "quantity": intent.quantity,
                    "amount_paise": authoritative_amount,
                    "currency": "INR",
                    "timestamp": intent.timestamp,
                    "nonce": intent.nonce,
                }
                canonical = CryptoService.build_intent_canonical(intent_data)
                if not CryptoService.verify(canonical, intent.signed_intent, mandate.public_key):
                    return self._deny(decision_id, agent_context, intent,
                                      mandate.financial_ceiling_paise,
                                      PolicyReasonCode.INVALID_SIGNATURE,
                                      "Signed intent verification failed.")

        # --- Step 4: Check mandate active ---
        if not mandate.is_active:
            return self._deny(decision_id, agent_context, intent,
                              mandate.financial_ceiling_paise,
                              PolicyReasonCode.MANDATE_REVOKED,
                              "Mandate has been revoked.")

        # --- Step 5: Check expiry ---
        if mandate.expires_at:
            now = datetime.now(timezone.utc)
            expires_at = mandate.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now > expires_at:
                return self._deny(decision_id, agent_context, intent,
                                  mandate.financial_ceiling_paise,
                                  PolicyReasonCode.MANDATE_EXPIRED,
                                  "Mandate has expired.")

        # --- Step 6: Check scope ---
        scope = self._parse_scope(mandate)
        product = await self._get_product(intent.sku)

        if product is None:
            return self._deny(decision_id, agent_context, intent,
                              mandate.financial_ceiling_paise,
                              PolicyReasonCode.SKU_NOT_ALLOWED,
                              f"Product {intent.sku} not found.")

        if not product.is_active:
            return self._deny(decision_id, agent_context, intent,
                              mandate.financial_ceiling_paise,
                              PolicyReasonCode.PRODUCT_INACTIVE,
                              f"Product {intent.sku} is inactive.")

        if not self._check_scope(scope, product):
            return self._deny(decision_id, agent_context, intent,
                              mandate.financial_ceiling_paise,
                              PolicyReasonCode.SKU_NOT_ALLOWED,
                              f"Product {intent.sku} (category: {product.category}) "
                              f"is outside mandate scope.")

        # --- Step 7: Check product availability ---
        if product.stock_count < intent.quantity:
            return self._deny(decision_id, agent_context, intent,
                              mandate.financial_ceiling_paise,
                              PolicyReasonCode.OUT_OF_STOCK,
                              f"Insufficient stock for {intent.sku}. "
                              f"Available: {product.stock_count}, Requested: {intent.quantity}")

        # --- Step 8: Calculate authoritative price (NEVER trust agent-provided amount) ---
        if intent.quantity <= 0:
            return self._deny(decision_id, agent_context, intent,
                              mandate.financial_ceiling_paise,
                              PolicyReasonCode.INVALID_QUANTITY,
                              "Quantity must be positive.")

        authoritative_amount = product.price_paise * intent.quantity

        # --- Step 9: Check financial ceiling ---
        # Also check cumulative spending
        total_spent = await self._get_total_spent(agent_context.agent_id, agent_context.mandate_id)
        remaining = mandate.financial_ceiling_paise - total_spent

        if authoritative_amount > remaining:
            return self._deny(
                decision_id, agent_context, intent,
                mandate.financial_ceiling_paise,
                PolicyReasonCode.AMOUNT_EXCEEDS_LIMIT,
                f"Amount ₹{authoritative_amount / 100:,.2f} exceeds remaining budget "
                f"₹{remaining / 100:,.2f} (ceiling: ₹{mandate.financial_ceiling_paise / 100:,.2f}, "
                f"already spent: ₹{total_spent / 100:,.2f}).",
                metadata={
                    "requested_amount_paise": authoritative_amount,
                    "remaining_paise": remaining,
                    "total_spent_paise": total_spent,
                },
            )

        # --- Step 10: Check velocity ---
        window_start = datetime.now(timezone.utc) - timedelta(
            seconds=mandate.velocity_window_seconds
        )
        tx_count = await self._get_transaction_count(
            agent_context.agent_id, agent_context.mandate_id, window_start
        )
        if tx_count >= mandate.max_transactions:
            return self._deny(decision_id, agent_context, intent,
                              mandate.financial_ceiling_paise,
                              PolicyReasonCode.VELOCITY_LIMIT_EXCEEDED,
                              f"Transaction velocity exceeded. "
                              f"{tx_count}/{mandate.max_transactions} in window.")

        # --- Step 11: Check replay protection ---
        if intent.nonce:
            is_replay = await self._check_replay(intent.nonce)
            if is_replay:
                return self._deny(decision_id, agent_context, intent,
                                  mandate.financial_ceiling_paise,
                                  PolicyReasonCode.REPLAY_DETECTED,
                                  "This intent has already been processed.")

            # Record the nonce
            intent_data = {
                "agent_id": agent_context.agent_id,
                "mandate_id": agent_context.mandate_id,
                "sku": intent.sku,
                "quantity": intent.quantity,
                "amount_paise": authoritative_amount,
                "nonce": intent.nonce,
            }
            canonical = CryptoService.canonicalize(intent_data)
            intent_hash = CryptoService.hash_intent(canonical)

            processed = ProcessedIntent(
                intent_hash=intent_hash,
                nonce=intent.nonce,
                agent_id=agent_context.agent_id,
                mandate_id=agent_context.mandate_id,
            )
            self.db.add(processed)

        # --- AUTHORIZED ---
        return PolicyDecision(
            allowed=True,
            decision_id=decision_id,
            reason_code=PolicyReasonCode.AUTHORIZED.value,
            reason="Transaction authorized.",
            mandate_id=agent_context.mandate_id,
            agent_id=agent_context.agent_id,
            requested_amount_paise=authoritative_amount,
            financial_ceiling_paise=mandate.financial_ceiling_paise,
            metadata={"authoritative_amount_paise": authoritative_amount},
        )

    # --- Private helpers ---

    async def _resolve_mandate(self, mandate_id: str) -> Mandate | None:
        stmt = select(Mandate).where(Mandate.id == mandate_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_product(self, sku: str) -> Product | None:
        stmt = select(Product).where(Product.sku == sku)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _parse_scope(self, mandate: Mandate) -> MandateScope:
        try:
            scope_dict = json.loads(mandate.scope_values)
            return MandateScope(**scope_dict)
        except Exception:
            return MandateScope()

    def _check_scope(self, scope: MandateScope, product: Product) -> bool:
        """Check if a product is within the mandate's scope."""
        # If no scope restrictions, everything is allowed
        has_sku_scope = len(scope.sku) > 0
        has_category_scope = len(scope.category) > 0

        if not has_sku_scope and not has_category_scope:
            return True

        # Check SKU whitelist
        if has_sku_scope and product.sku in scope.sku:
            return True

        # Check category whitelist
        if has_category_scope and product.category in scope.category:
            return True

        # If scopes are defined but product doesn't match any
        return False

    async def _get_total_spent(self, agent_id: str, mandate_id: str) -> int:
        """Get total amount spent under this mandate (non-failed orders)."""
        stmt = select(func.coalesce(func.sum(Order.total_amount_paise), 0)).where(
            Order.agent_id == agent_id,
            Order.mandate_id == mandate_id,
            Order.status.notin_([OrderStatus.FAILED.value, OrderStatus.EXPIRED.value]),
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _get_transaction_count(
        self, agent_id: str, mandate_id: str, window_start: datetime
    ) -> int:
        """Count transactions in the velocity window."""
        stmt = select(func.count()).select_from(Order).where(
            Order.agent_id == agent_id,
            Order.mandate_id == mandate_id,
            Order.created_at >= window_start,
            Order.status != OrderStatus.FAILED.value,
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _check_replay(self, nonce: str) -> bool:
        """Check if a nonce has been used before."""
        stmt = select(ProcessedIntent).where(ProcessedIntent.nonce == nonce)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _deny(
        self,
        decision_id: str,
        ctx: AgentContext,
        intent: PurchaseIntent,
        ceiling: int,
        reason_code: PolicyReasonCode,
        reason: str,
        metadata: dict | None = None,
    ) -> PolicyDecision:
        """Build a structured denial."""
        return PolicyDecision(
            allowed=False,
            decision_id=decision_id,
            reason_code=reason_code.value,
            reason=reason,
            mandate_id=ctx.mandate_id,
            agent_id=ctx.agent_id,
            requested_amount_paise=0,
            financial_ceiling_paise=ceiling,
            metadata=metadata or {},
        )
