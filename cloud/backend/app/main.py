"""FastAPI application adapted from the official full-stack template (MIT)."""

import fcntl
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlmodel import Session, text
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import REPO_ROOT, settings
from app.core.db import engine, init_db
from app.frontend import attach_frontend
from app.services.remote import RemoteTaskService
from app.services.store import ServiceError
from app.services.tasks import TaskService


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.APP_DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    # This initial local backend intentionally runs one HTTP worker per data directory.
    with (settings.APP_DATA_DIR / ".server.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Another API instance already owns this data directory; use one worker"
            ) from None
        init_db()
        app.state.tasks = (
            RemoteTaskService(settings) if settings.REMOTE_ENABLED else TaskService(settings)
        )
        try:
            yield
        finally:
            app.state.tasks.close()
            fcntl.flock(lock, fcntl.LOCK_UN)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Range"],
    expose_headers=["ETag", "Content-Range", "Accept-Ranges"],
)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.exception_handler(ServiceError)
async def handle_service_error(request: Request, error: ServiceError):
    return JSONResponse(
        status_code=error.status,
        content={
            "detail": {
                "code": error.code,
                "message": error.message,
            }
        },
    )


@app.get("/healthz", tags=["health"], summary="仅检查API与本地数据库，不连接机器人")
def health():
    with Session(engine) as session:
        session.exec(text("SELECT 1")).one()
    return {"status": "ok", "service": "campus-patrol-api"}


attach_frontend(app, REPO_ROOT / "apps/web/dist")
