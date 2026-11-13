"""FastAPI application factory, static asset serving, and exception handling."""

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import alphalens
from alphalens.api.security import RequestIdMiddleware, SecurityHeadersMiddleware
from alphalens.config import get_settings
from alphalens.logging import configure_logging, get_logger

logger = get_logger("alphalens.api")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    CORS Architecture Note:
    Same-origin deployment per ADR-002: in production, FastAPI serves the built
    frontend (from frontend/dist) and the API on the exact same origin.
    In development, the Vite dev server proxies /api to FastAPI.
    Therefore, CORS middleware is intentionally omitted to prevent cross-origin abuse.
    """
    configure_logging()
    settings = get_settings()

    docs_url = None if settings.app_env == "prod" else "/docs"
    openapi_url = None if settings.app_env == "prod" else "/openapi.json"

    app = FastAPI(
        title="AlphaLens API",
        version=alphalens.__version__,
        docs_url=docs_url,
        openapi_url=openapi_url,
    )

    # Middleware execution: Security headers -> Request ID
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.error(
            "unhandled_server_exception",
            request_id=request_id,
            path=request.url.path,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal error",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
            headers={"X-Request-ID": request_id},
        )

    @app.get("/api/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "ok",
            "version": alphalens.__version__,
        }

    # Static assets and SPA fallback serving
    frontend_dist = Path("frontend/dist")
    assets_dir = frontend_dist / "assets"

    if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> Any:
            # All unmapped /api routes must 404 with JSON, never return index.html
            clean_path = full_path.lstrip("/")
            if clean_path == "api" or clean_path.startswith("api/"):
                raise StarletteHTTPException(
                    status_code=404,
                    detail=f"Route '/{clean_path}' not found",
                )

            target_file = frontend_dist / clean_path
            if clean_path and target_file.is_file():
                return FileResponse(target_file)

            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
