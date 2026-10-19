"""Router composition adapted from the official FastAPI full-stack template."""

from fastapi import APIRouter

from app.api.routes import executor, login, tasks

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(tasks.router)
api_router.include_router(executor.router)
