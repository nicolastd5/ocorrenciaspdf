import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.config import load_settings
from app.db import init_db
from app.routes_api import router as api_router, limiter as api_limiter
from app.routes_admin import router as admin_router
from app.routes_update import router as update_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("license-server")


def create_app() -> FastAPI:
    settings = load_settings()
    init_db(settings.db_path)

    fastapi_app = FastAPI(title="License Server")
    fastapi_app.state.limiter = api_limiter
    fastapi_app.state.settings = settings

    fastapi_app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=False,
        same_site="lax",
        max_age=7 * 24 * 60 * 60,
    )

    fastapi_app.include_router(api_router)
    fastapi_app.include_router(admin_router)
    fastapi_app.include_router(update_router)

    @fastapi_app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(status_code=429, content={"error": "rate_limit_exceeded"})

    @fastapi_app.get("/")
    async def root():
        return {"service": "license-server", "status": "ok"}

    return fastapi_app


app = create_app()
