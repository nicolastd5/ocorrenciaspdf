import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware
from starlette import status

from app.config import load_settings
from app.db import init_db
from app.routes_api import router as api_router, limiter as api_limiter
from app.routes_auth import router as auth_router
from app.routes_admin import router as admin_router
from app.routes_update import router as update_router
from app import jobs as jobs_module
from app.routes_app import router as app_router
from app.routes_codigos import router as codigos_router
from app.routes_jobs import router as jobs_router



logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("license-server")


def create_app(queue=None) -> FastAPI:
    settings = load_settings()
    init_db(settings.db_path)

    fastapi_app = FastAPI(title="License Server")
    fastapi_app.state.limiter = api_limiter
    fastapi_app.state.settings = settings
    fastapi_app.state.queue = queue

    if fastapi_app.state.queue is None:
        fastapi_app.state.queue = jobs_module.make_queue(settings.redis_url)

    fastapi_app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=False,
        same_site="lax",
        max_age=7 * 24 * 60 * 60,
    )

    fastapi_app.mount("/static", StaticFiles(directory="app/static"), name="static")
    fastapi_app.include_router(api_router)
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(admin_router)
    fastapi_app.include_router(update_router)
    fastapi_app.include_router(app_router)
    fastapi_app.include_router(codigos_router)
    fastapi_app.include_router(jobs_router)

    @fastapi_app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(status_code=429, content={"error": "rate_limit_exceeded"})

    @fastapi_app.get("/")
    async def root():
        return RedirectResponse("/app/ocorrencias", status_code=status.HTTP_303_SEE_OTHER)

    return fastapi_app


app = create_app()
