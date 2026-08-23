"""Admin routes — seed data and rebuild graph. Protected behind admin key."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin(x_admin_key: str = Header(default="")):
    """Verify admin API key."""
    settings = get_settings()
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.post("/seed", dependencies=[Depends(verify_admin)])
async def seed_database(db: AsyncSession = Depends(get_db)):
    """Seed the database with demo data."""
    from scripts.seed_catalog import seed_all
    result = await seed_all(db)
    await db.commit()
    return result


@router.post("/rebuild-graph", dependencies=[Depends(verify_admin)])
async def rebuild_graph(db: AsyncSession = Depends(get_db)):
    """Rebuild the co-purchase graph from order history."""
    from app.services.upsell_service import UpsellService
    service = UpsellService(db)
    graph = await service.build_graph()
    return {
        "success": True,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
    }
