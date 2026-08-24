"""Structured JSON logging configuration with graceful fallback to stdlib."""

from __future__ import annotations

import logging

try:
    import structlog

    def setup_logging(debug: bool = False) -> None:
        """Configure structured logging with structlog."""
        log_level = logging.DEBUG if debug else logging.INFO
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    def get_logger(name: str | None = None):
        """Get a structured logger instance."""
        return structlog.get_logger(name)

except ModuleNotFoundError:
    # Graceful fallback — structlog not installed, use stdlib
    def setup_logging(debug: bool = False) -> None:  # type: ignore[misc]
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    def get_logger(name: str | None = None):  # type: ignore[misc]
        return logging.getLogger(name or "app")
