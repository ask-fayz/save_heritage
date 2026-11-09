"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app import repo
from app.config import Settings, get_settings
from app.db import init_db, session
from app.routes import admin, contribute, public
from app.security import CSRF_COOKIE
from app.seed import seed_demo_data
from app.services.jobs import JobRunner
from app.web import render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None, *, synchronous_jobs: bool = False) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        init_db(settings.db_path)
        with session(settings.db_path) as conn:
            repo.fail_interrupted_jobs(conn)
            if settings.seed_demo:
                seed_demo_data(conn)
        yield
        app.state.jobs.shutdown()

    app = FastAPI(title="SAVE Heritage", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.jobs = JobRunner(settings, synchronous=synchronous_jobs)

    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    app.include_router(public.router)
    app.include_router(contribute.router)
    app.include_router(admin.router)

    @app.middleware("http")
    async def csrf_cookie_and_headers(request: Request, call_next):
        response = await call_next(request)
        selected_lang = request.query_params.get("lang")
        if selected_lang in ("en", "ru", "zh"):
            response.set_cookie("heritage_lang", selected_lang, samesite="lax", max_age=31536000)
        token = getattr(request.state, "csrf_token", None)
        if token and request.cookies.get(CSRF_COOKIE) != token:
            response.set_cookie(CSRF_COOKIE, token, httponly=True, samesite="lax",
                                secure=request.url.scheme == "https", max_age=60 * 60 * 24 * 7)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        wants_html = "text/html" in request.headers.get("accept", "") and not request.url.path.startswith("/api/")
        if not wants_html:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
        response = render(request, "error.html", {"status_code": exc.status_code, "message": exc.detail},
                          status_code=exc.status_code)
        for key, value in (exc.headers or {}).items():
            response.headers[key] = value
        return response

    return app
