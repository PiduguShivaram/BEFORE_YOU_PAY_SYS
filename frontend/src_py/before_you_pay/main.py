"""FastAPI application entry point for Before You Pay."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from before_you_pay import __version__
from before_you_pay.api.routes import api_router
from before_you_pay.api.routes.health import router as health_router
from before_you_pay.config import get_settings
from before_you_pay.core.errors import BeforeYouPayException
from before_you_pay.models import StandardError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown hooks."""
    # Phase 0/1: Setup in-memory stubs and logging
    yield
    # Cleanup logic if any


def create_app() -> FastAPI:
    """Application factory for Before You Pay backend."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Phone-first AI decision-support application for financial documents. "
            "Phase 0/1: Domain contracts, interfaces, and architecture foundation."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(BeforeYouPayException)
    async def custom_exception_handler(
        request: Request,
        exc: BeforeYouPayException,
    ) -> JSONResponse:
        error_payload = StandardError(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            correlation_id=exc.correlation_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        error_payload = StandardError(
            code="SCHEMA_VALIDATION_ERROR",
            message="Request body or query parameter failed schema validation.",
            details={"validation_errors": exc.errors()},
        )
        return JSONResponse(
            status_code=422,
            content=error_payload.model_dump(mode="json"),
        )

    # Register Routers
    # Direct /health endpoint for container probes
    app.include_router(health_router)
    # Prefixed API routes (/api/v1/...)
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()


def run() -> None:
    """CLI entrypoint to run uvicorn server."""
    settings = get_settings()
    uvicorn.run(
        "before_you_pay.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
