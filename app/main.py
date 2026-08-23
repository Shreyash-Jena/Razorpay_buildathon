"""
Agentic Commerce Server — Main Application

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

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — startup and shutdown."""
    settings = get_settings()
    setup_logging(debug=settings.debug)

    # Startup
    await init_db()

    yield

    # Shutdown
    await close_db()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Agentic Commerce Server",
        description=(
            "Universal Agentic Interoperability Server — "
            "MCP-compatible commerce tools for autonomous AI agents. "
            "Built for the Razorpay AI Buildathon."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from app.api.routes.health import router as health_router
    from app.api.routes.catalog import router as catalog_router
    from app.api.routes.commerce import router as commerce_router
    from app.api.routes.mandates import router as mandates_router
    from app.api.routes.audit import router as audit_router
    from app.api.routes.webhooks import router as webhook_router
    from app.api.routes.webhooks import upsell_router

    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(commerce_router)
    app.include_router(mandates_router)
    app.include_router(audit_router)
    app.include_router(webhook_router)
    app.include_router(upsell_router)

    # Admin routes
    from app.api.routes.admin import router as admin_router
    app.include_router(admin_router)

    return app


# Create the app instance
app = create_app()
