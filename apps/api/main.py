"""
CargoIQ API — Main Application Entry Point
FastAPI application with CORS, routers, health check, and global error handling.
"""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .core.config import settings
from .routers import auth, documents, shipments, analytics, compliance, inbox, internal, portals, audit, carrier_audit, public, onboarding

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"🚀 CargoIQ API starting — {settings.ENVIRONMENT}")
    logger.info(f"   Supabase: {settings.SUPABASE_URL[:40]}...")
    logger.info(f"   Claude API: {'✓ configured' if settings.ANTHROPIC_API_KEY else '✗ MISSING'}")
    yield
    logger.info("👋 CargoIQ API shutting down")


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="CargoIQ API",
    description=(
        "South Africa's AI compliance and cost containment layer for freight forwarders. "
        "CargoFlow AI + WiseLayer."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request timing middleware ─────────────────────────────────
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 1)
    response.headers["X-Process-Time-Ms"] = str(duration)
    return response


# ── Global error handlers ─────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " → ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": errors}
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred. Our team has been notified.",
            "error": str(exc)[:100] if settings.DEBUG else "Internal server error",
        }
    )


# ── Routers ───────────────────────────────────────────────────
API_V1 = "/api/v1"

app.include_router(auth.router,       prefix=API_V1)
app.include_router(documents.router,  prefix=API_V1)
app.include_router(shipments.router,  prefix=API_V1)
app.include_router(analytics.router,  prefix=API_V1)
app.include_router(compliance.router, prefix=API_V1)
app.include_router(inbox.router,    prefix=API_V1)
app.include_router(internal.router, prefix=API_V1)
app.include_router(portals.router,  prefix=API_V1)
app.include_router(audit.router,    prefix=API_V1)
app.include_router(carrier_audit.router, prefix=API_V1)
app.include_router(public.router, prefix=API_V1)
app.include_router(onboarding.router, prefix=API_V1)


# ── Health & Root ─────────────────────────────────────────────
@app.get("/", tags=["System"])
async def root():
    return {
        "service": "CargoIQ API",
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs" if not settings.is_production else "disabled",
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Health check for Railway/load balancer."""
    from .core.supabase_client import get_supabase_admin
    checks = {"api": "ok", "supabase": "unknown"}
    try:
        admin = get_supabase_admin()
        admin.table("organisations").select("id").limit(1).execute()
        checks["supabase"] = "ok"
    except Exception as e:
        checks["supabase"] = f"error: {str(e)[:50]}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )
