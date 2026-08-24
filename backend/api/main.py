from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.api.routes import router
from backend.config import get_settings
from backend.db.session import SessionLocal

settings = get_settings()


class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: dict[str, Any]


class ServiceHealth(BaseModel):
    status: str
    latency_ms: float | None = None
    details: dict[str, Any] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Reclaim API",
    version="0.1.0",
    description="AI revenue recovery for failed payments.",
    lifespan=lifespan,
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
    return response


# Rate limiting middleware (simple in-memory, use Redis for production)
from collections import defaultdict
import time

rate_limit_store: defaultdict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 100  # requests per minute
RATE_WINDOW = 60  # seconds

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/health"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Clean old entries
    rate_limit_store[client_ip] = [t for t in rate_limit_store[client_ip] if now - t < RATE_WINDOW]

    if len(rate_limit_store[client_ip]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": str(RATE_WINDOW)},
        )

    rate_limit_store[client_ip].append(now)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/detailed", response_model=HealthCheckResponse)
def health_detailed() -> HealthCheckResponse:
    timestamp = datetime.utcnow()
    services = {}

    # Database health
    db_start = datetime.utcnow()
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_latency = (datetime.utcnow() - db_start).total_seconds() * 1000
        services["database"] = ServiceHealth(
            status="healthy",
            latency_ms=db_latency,
            details={"connection": "ok"},
        ).model_dump()
    except SQLAlchemyError as e:
        db_latency = (datetime.utcnow() - db_start).total_seconds() * 1000
        services["database"] = ServiceHealth(
            status="unhealthy",
            latency_ms=db_latency,
            details={"error": str(e)},
        ).model_dump()
    except Exception as e:
        services["database"] = ServiceHealth(
            status="unhealthy",
            details={"error": f"Unexpected error: {str(e)}"},
        ).model_dump()

    # API health
    services["api"] = ServiceHealth(
        status="healthy",
        latency_ms=None,
        details={"version": "0.1.0"},
    ).model_dump()

    # Configuration check
    config_status = "healthy"
    config_details = {}
    if not settings.gemini_api_key:
        config_status = "degraded"
        config_details["gemini_api_key"] = "not configured (using template fallback)"
    else:
        config_details["gemini_api_key"] = "configured"

    if not settings.database_url:
        config_status = "unhealthy"
        config_details["database_url"] = "not configured"
    else:
        config_details["database_url"] = "configured"

    services["configuration"] = ServiceHealth(
        status=config_status,
        details=config_details,
    ).model_dump()

    # Overall status
    overall_status = "healthy"
    for svc in services.values():
        if svc["status"] == "unhealthy":
            overall_status = "unhealthy"
            break
        elif svc["status"] == "degraded":
            overall_status = "degraded"

    return HealthCheckResponse(
        status=overall_status,
        timestamp=timestamp,
        version="0.1.0",
        services=services,
    )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Reclaim API",
        "version": "0.1.0",
        "description": "AI revenue recovery for failed payments.",
        "health": "/health",
        "detailed_health": "/health/detailed",
        "docs": "/docs",
    }


app.include_router(router)
