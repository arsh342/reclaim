"""FastAPI application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.db.session import init_db
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
async def health():
    return {"status": "healthy"}


# Mount MCP server at /mcp
try:
    from backend.mcp_server.server import mcp
    app.mount("/mcp", mcp.streamable_http_app())
except Exception as e:
    # MCP server optional - log and continue
    print(f"MCP server not mounted: {e}")