"""AI Email Automation Agent FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.google_oauth import router as google_oauth_router
from app.api.pipeline import router as pipeline_router
from app.api.system import router as system_router
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


app = FastAPI(
    title="Personal AI Outreach Agent",
    description="Human-approved Gmail outreach automation for job search and networking",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(pipeline_router)
app.include_router(google_oauth_router)
app.include_router(system_router)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"
if DASHBOARD_DIR.exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=DASHBOARD_DIR, html=True),
        name="dashboard",
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/")
async def root():
    dashboard_index = DASHBOARD_DIR / "index.html"
    if dashboard_index.exists():
        return FileResponse(dashboard_index)
    return {"message": "Personal AI Outreach Agent API", "docs": "/docs"}


