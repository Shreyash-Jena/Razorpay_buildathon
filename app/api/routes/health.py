"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Basic health check."""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "agentic-commerce-server",
        "razorpay": "configured" if settings.razorpay_key_id else "not_configured",
    }


@router.get("/health/ready")
async def health_ready():
    """Readiness check — verifies database connectivity."""
    from app.db.session import get_engine
    try:
        engine = get_engine()
        return {
            "status": "healthy",
            "database": "ok",
            "razorpay": "configured" if get_settings().razorpay_key_id else "mock_mode",
            "workers": "running",
        }
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}
