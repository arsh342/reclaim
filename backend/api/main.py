"""FastAPI application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.db.session import init_db, get_session
from backend.api.routes import router as api_router
from backend.api.sse import router as sse_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="Reclaim API",
    description="AI Revenue Recovery Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(sse_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Reclaim API", "version": "1.0.0"}


@app.get("/health")
async def health(db: AsyncSession = Depends(get_session)):
    """Health check with database connectivity."""
    try:
        # Check database connectivity
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "checks": {
            "database": db_status,
            "api": "healthy",
        },
        "version": "1.0.0",
    }


# Mount MCP server at /mcp
try:
    from backend.mcp_server.server import mcp
    app.mount("/mcp", mcp.streamable_http_app())
except Exception as e:
    # MCP server optional - log and continue
    print(f"MCP server not mounted: {e}")