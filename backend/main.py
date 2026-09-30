"""
Garak Backend - FastAPI wrapper for garak CLI
Main entry point for the API server
"""
from contextlib import asynccontextmanager
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from api.routes import scan, plugins, config, system, custom_probes, workflow, models, targets, campaigns, hooks, schedules, webhooks, admin
from config import settings
from middleware.tenant import TenantMiddleware
from logging_config import setup_logging
from services.model_discovery import initialize_model_discovery
import logging

# Configure structured logging (M16) with optional rotation (M17)
setup_logging(
    level=settings.log_level,
    log_format=settings.log_format,
    log_file=settings.log_file,
    max_bytes=settings.log_max_bytes,
    backup_count=settings.log_backup_count,
)

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log requests with timing information."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log request details (skip health checks to reduce noise)
        if request.url.path not in ["/health", "/"]:
            logger.info(
                "%s %s %d %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra={
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )

        # Add timing header to response
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info(f"Starting Garak Backend on {settings.host}:{settings.port}")

    # Initialize database (PostgreSQL in prod, SQLite fallback in dev/tests)
    from database.session import init_db
    from database.migrations import run_backfill_if_needed
    init_db()
    run_backfill_if_needed()

    # Initialize object store (Minio in prod, local filesystem fallback)
    from services.object_store import init_object_store
    init_object_store()

    # Initialize model discovery (fetches Ollama models)
    logger.info("Initializing model discovery...")
    await initialize_model_discovery()

    yield

    # Shutdown
    logger.info("Shutting down Garak Backend...")

# Create FastAPI app
app = FastAPI(
    title="Garak Backend API",
    description="REST API wrapper for the garak LLM vulnerability scanner",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure GZip compression for responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)

# Add request logging middleware with timing
app.add_middleware(RequestLoggingMiddleware)

# Add tenant isolation middleware (extracts TenantContext from JWT)
app.add_middleware(TenantMiddleware, tenant_mode=settings.tenant_mode)

# Include routers
app.include_router(scan.router, prefix="/api/v1/scan", tags=["Scan"])
app.include_router(plugins.router, prefix="/api/v1/plugins", tags=["Plugins"])
app.include_router(config.router, prefix="/api/v1/config", tags=["Configuration"])
app.include_router(system.router, prefix="/api/v1/system", tags=["System"])
app.include_router(custom_probes.router, prefix="/api/v1/probes/custom", tags=["Custom Probes"])
app.include_router(workflow.router, tags=["Workflow"])
app.include_router(models.router, prefix="/api/v1/generators", tags=["Models"])
app.include_router(targets.router, prefix="/api/v1/targets", tags=["Targets"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["Campaigns"])
app.include_router(hooks.router, prefix="/api/v1/hooks", tags=["Hooks"])
app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["Schedules"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "name": "Hydra Backend API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with component status."""
    components = {}

    # Prism connectivity (if enabled)
    from services.prism_client import prism_available
    if prism_available():
        try:
            from services.prism_client import get_prism_client
            prism = get_prism_client()
            prism_ok = await prism.health()
            components["prism"] = "connected" if prism_ok else "degraded"
        except Exception:
            components["prism"] = "degraded"

    # Overall status: degraded if any component is degraded
    overall = "healthy"
    if any(v == "degraded" for v in components.values()):
        overall = "degraded"

    return {"status": overall, **components}


@app.get("/version")
async def version_info():
    """Version information endpoint"""
    import sys
    from services.garak_wrapper import garak_wrapper

    garak_version = garak_wrapper.get_garak_version()

    return {
        "backend_version": "1.0.0",
        "api_version": "v1",
        "python_version": sys.version.split()[0],
        "garak_version": garak_version,
    }


if __name__ == "__main__":
    import uvicorn
    logger.info(
        "Server configuration",
        extra={
            "host": settings.host,
            "port": settings.port,
            "cors_origins": settings.cors_origins_list,
            "log_level": settings.log_level,
            "log_format": settings.log_format,
            "log_file": settings.log_file,
        },
    )

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )
