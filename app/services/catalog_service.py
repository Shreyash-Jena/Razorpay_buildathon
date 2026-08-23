"""Catalog service — product search using PostgreSQL ILIKE + category matching."""

from __future__ import annotations

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product
from app.schemas.catalog import ProductResponse, SearchResponse


class CatalogService:
    """Search the merchant catalog. No business logic beyond discovery."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(self, query: str, limit: int = 20) -> SearchResponse:
        """
        Search products by name, description, category, or SKU.
        Uses ILIKE for fuzzy matching with simple relevance scoring.
        """
        search_term = f"%{query.lower()}%"

        stmt = (
            select(Product)
            .where(
                Product.is_active == True,  # noqa: E712
                or_(
                    func.lower(Product.name).like(search_term),
                    func.lower(Product.description).like(search_term),
                    func.lower(Product.category).like(search_term),
                    func.lower(Product.sku).like(search_term),
                ),
            )
            .order_by(Product.price_paise.asc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        products = result.scalars().all()

        items = [ProductResponse.from_db(p) for p in products]
        return SearchResponse(items=items, total=len(items))

    async def get_by_sku(self, sku: str) -> Product | None:
        """Fetch a single product by SKU."""
        stmt = select(Product).where(Product.sku == sku)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[Product]:
        """Fetch all active products."""
        stmt = select(Product).where(Product.is_active == True).order_by(Product.category, Product.name)  # noqa: E712
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
