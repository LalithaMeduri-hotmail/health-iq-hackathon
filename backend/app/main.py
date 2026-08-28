"""FastAPI application factory: `/health`, CORS, request-id middleware, routers (M0 exit criteria)."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import mealplan, medicines, pdf, prescriptions, profile, reports, share
from app.config import get_settings
from app.errors import DomainError
from app.models.common import ProblemDetails


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # TODO(D1): initialize the Azure Monitor OpenTelemetry exporter here (Section 7.2).
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Health IQ API", version="v1", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        """Centralized domain exception -> RFC 7807 mapping (backend.instructions.md)."""
        problem = ProblemDetails(
            type=f"https://healthiq/errors/{exc.type_slug}",
            title=exc.title,
            status=exc.status,
            detail=exc.detail,
            instance=getattr(request.state, "request_id", "unknown"),
            errors=exc.errors,
        )
        return JSONResponse(
            status_code=exc.status,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        problem = ProblemDetails(
            type="https://healthiq/errors/internal-error",
            title="Internal server error",
            status=500,
            detail=str(exc),
            instance=getattr(request.state, "request_id", "unknown"),
        )
        return JSONResponse(
            status_code=500,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(prescriptions.router)
    app.include_router(medicines.router)
    app.include_router(reports.router)
    app.include_router(mealplan.router)
    app.include_router(pdf.router)
    app.include_router(share.router)
    app.include_router(profile.router)

    return app


app = create_app()
