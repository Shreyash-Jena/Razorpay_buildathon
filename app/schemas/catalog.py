"""Pydantic schemas for catalog operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductResponse(BaseModel):
    sku: str
    name: str
    description: str = ""
    price_paise: int
    price_display: str = ""
    category: str
    stock_available: bool
    stock_count: int = 0

    @classmethod
    def from_db(cls, product) -> "ProductResponse":
        return cls(
            sku=product.sku,
            name=product.name,
            description=product.description,
            price_paise=product.price_paise,
            price_display=f"₹{product.price_paise / 100:,.2f}",
            category=product.category,
            stock_available=product.stock_count > 0,
            stock_count=product.stock_count,
        )


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)


class SearchResponse(BaseModel):
    success: bool = True
    items: list[ProductResponse] = []
    total: int = 0


class StockResponse(BaseModel):
    success: bool = True
    status: str  # IN_STOCK or OUT_OF_STOCK
    sku: str
    stock_count: int = 0
    substitute_sku: str | None = None
    substitute_name: str | None = None
    substitute_price_paise: int | None = None
