"""Catalog API routes — search and stock check."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.catalog_service import CatalogService
from app.services.inventory_service import InventoryService
from app.schemas.catalog import SearchResponse, StockResponse
from app.core.exceptions import ProductNotFoundError

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/search", response_model=SearchResponse)
async def search_catalog(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search the merchant catalog by name, category, or SKU."""
    service = CatalogService(db)
    return await service.search(query, limit=limit)


@router.get("/{sku}/stock", response_model=StockResponse)
async def check_stock(
    sku: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Check stock availability for a product.
    If out of stock, returns a deterministic substitute.
    """
    service = InventoryService(db)
    return await service.check_stock(sku)
