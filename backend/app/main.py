"""AI Email Automation Agent FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.app_auth import router as app_auth_router
from app.api.auth import current_session
from app.api.google_oauth import router as google_oauth_router
from app.api.pipeline import router as pipeline_router
from app.api.system import router as system_router
from app.core.config import get_settings
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

app.include_router(app_auth_router)
app.include_router(pipeline_router)
app.include_router(google_oauth_router)
app.include_router(system_router)


@app.middleware("http")
async def require_app_login(request: Request, call_next):
    settings = get_settings()
    if not settings.app_auth_enabled:
        return await call_next(request)

    path = request.url.path
    public_prefixes = ("/auth/app", "/health")
    public_paths = ("/login", "/favicon.ico", "/styles.css", "/app.js")
    if path in public_paths or path.startswith(public_prefixes):
        return await call_next(request)

    if current_session(request):
        return await call_next(request)

    if path.startswith("/api/") or request.method not in {"GET", "HEAD"}:
        return JSONResponse(
            {"detail": "Login required."},
            status_code=401,
            headers={"WWW-Authenticate": "Cookie"},
        )
    return RedirectResponse("/login")

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


@app.get("/login")
async def login_page():
    login_index = DASHBOARD_DIR / "login.html"
    if login_index.exists():
        return FileResponse(login_index)
    return {"message": "Login page missing."}


@app.get("/styles.css")
async def dashboard_styles():
    stylesheet = DASHBOARD_DIR / "styles.css"
    if stylesheet.exists():
        return FileResponse(stylesheet, media_type="text/css")
    return JSONResponse({"detail": "Dashboard stylesheet missing."}, status_code=404)


@app.get("/app.js")
async def dashboard_script():
    script = DASHBOARD_DIR / "app.js"
    if script.exists():
        return FileResponse(script, media_type="application/javascript")
    return JSONResponse({"detail": "Dashboard script missing."}, status_code=404)


