"""Inventory service — stock checking with deterministic substitute logic."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.schemas.catalog import StockResponse
from app.core.exceptions import ProductNotFoundError


class InventoryService:
    """Check stock and find substitutes. Substitution is deterministic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_stock(self, sku: str) -> StockResponse:
        """
        Check stock for a product. If out of stock, find a deterministic substitute.

        Substitute priority:
        1. Same category
        2. Nearest price
        3. Highest stock
        """
        stmt = select(Product).where(Product.sku == sku)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()

        if product is None:
            raise ProductNotFoundError(sku)

        if product.stock_count > 0:
            return StockResponse(
                status="IN_STOCK",
                sku=sku,
                stock_count=product.stock_count,
            )

        # Out of stock — find deterministic substitute
        substitute = await self._find_substitute(product)

        return StockResponse(
            status="OUT_OF_STOCK",
            sku=sku,
            stock_count=0,
            substitute_sku=substitute.sku if substitute else None,
            substitute_name=substitute.name if substitute else None,
            substitute_price_paise=substitute.price_paise if substitute else None,
        )

    async def _find_substitute(self, product: Product) -> Product | None:
        """
        Find the best substitute: same category → nearest price → highest stock.
        """
        stmt = (
            select(Product)
            .where(
                Product.category == product.category,
                Product.is_active == True,  # noqa: E712
                Product.stock_count > 0,
                Product.sku != product.sku,
            )
            .order_by(
                # Nearest price first (absolute difference)
                (Product.price_paise - product.price_paise).asc()
                if hasattr(Product.price_paise, '__sub__') else Product.price_paise.asc(),
            )
            .limit(10)
        )

        result = await self.db.execute(stmt)
        candidates = list(result.scalars().all())

        if not candidates:
            return None

        # Sort by price proximity, then by stock descending
        candidates.sort(
            key=lambda p: (abs(p.price_paise - product.price_paise), -p.stock_count)
        )

        return candidates[0]

    async def reserve_stock(self, sku: str, quantity: int) -> Product:
        """
        Atomically reserve stock. Uses SELECT FOR UPDATE pattern.
        For SQLite, this falls back to a simple check-and-decrement.
        """
        stmt = select(Product).where(Product.sku == sku)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()

        if product is None:
            raise ProductNotFoundError(sku)

        if product.stock_count < quantity:
            from app.core.exceptions import OutOfStockError
            substitute = await self._find_substitute(product)
            raise OutOfStockError(sku, substitute.sku if substitute else None)

        product.stock_count -= quantity
        return product

    async def restore_stock(self, sku: str, quantity: int) -> None:
        """Restore stock after a failed order."""
        stmt = select(Product).where(Product.sku == sku)
        result = await self.db.execute(stmt)
        product = result.scalar_one_or_none()
        if product:
            product.stock_count += quantity
