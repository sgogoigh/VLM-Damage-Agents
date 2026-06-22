"""
FastAPI application factory for the Orchestrate claim-verifier backend.

Standalone service: the full multi-modal verification pipeline lives under
``app/core`` and is wired here behind a small, robust HTTP surface.

Run locally::

    cd backend
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.config import get_settings
from app.service import ClaimVerifierService


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    logger = logging.getLogger("orchestrate")
    logger.info("Starting up. Config: %s", settings.public_summary())
    if not settings.dataset_dir.exists():
        logger.warning("Dataset dir %s does not exist; reference data will be empty "
                       "and image paths will not resolve.", settings.dataset_dir)
    # Build the service once and share it across all requests.
    app.state.service = ClaimVerifierService(settings)
    try:
        yield
    finally:
        logger.info("Shutting down.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Orchestrate Claim Verifier",
        version="1.0.0",
        description="Multi-modal damage-claim evidence review (Gemini + Claude).",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"status": "ok", "message": "Orchestrate Claim Verifier API",
                "docs": "/docs", "api_prefix": settings.api_prefix}

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.exception_handler(ValueError)
    async def _value_error_handler(_request, exc: ValueError):  # pragma: no cover
        return JSONResponse(status_code=400, content={"detail": str(exc), "code": "bad_request"})

    return app


app = create_app()
