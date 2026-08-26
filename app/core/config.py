"""
Core configuration — loaded from environment variables.

FINANCIAL SECURITY INVARIANT:
No execution capable of creating, modifying, or authorizing a financial
transaction may reach Razorpay without passing through the Policy Gate.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # --- Razorpay (Test Mode) ---
    razorpay_key_id: str = Field(default="", description="Razorpay test-mode key ID")
    razorpay_key_secret: str = Field(default="", description="Razorpay test-mode secret")
    razorpay_webhook_secret: str = Field(default="", description="Razorpay webhook secret")
    
    razorpay_b2c_key_id: str = Field(default="", description="Razorpay test-mode key ID for B2C")
    razorpay_b2c_key_secret: str = Field(default="", description="Razorpay test-mode secret for B2C")
    razorpay_b2c_customer_id: str = Field(default="", description="Razorpay B2C customer ID")
    razorpay_b2c_token_id: str = Field(default="", description="Razorpay B2C token ID")

    # --- LLM Agent API Keys ---
    openai_api_key: str = Field(default="", description="OpenAI API key")
    anthropic_api_key: str = Field(default="", description="Anthropic API key")

    # --- Database ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///./agentic_commerce.db",
        description="Async SQLAlchemy database URL",
    )

    # --- Security ---
    admin_api_key: str = Field(default="admin-secret-key-change-me")

    # --- Server ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # --- Policy Gate Defaults ---
    intent_validity_seconds: int = Field(default=60, description="Signed intent max age")
    upsell_probability_threshold: float = Field(default=0.40)
    upsell_min_support: int = Field(default=20)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
