"""Outbound executor clients use a dedicated credential, never browser JWTs."""

import secrets
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from app.api.routes.tasks import Service
from app.remote_schemas import DeliveryRequest, PollRequest, TaskReport
from app.services.remote import RemoteTaskService
from app.services.store import ServiceError

router = APIRouter(prefix="/executor", tags=["executor"])


def executor_service(
    service: Service, authorization: Annotated[str | None, Header()] = None
) -> RemoteTaskService:
    if not isinstance(service, RemoteTaskService) or not service.settings.REMOTE_ENABLED:
        raise ServiceError(404, "REMOTE_DISABLED", "Remote channel is disabled")
    configured = service.settings.REMOTE_EXECUTOR_KEY
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if (
        not configured
        or not authorization
        or not authorization.startswith("Bearer ")
        or not secrets.compare_digest(configured.get_secret_value().encode(), supplied.encode())
    ):
        raise ServiceError(401, "INVALID_EXECUTOR_CREDENTIALS", "Executor authentication failed")
    return service


Executor = Annotated[RemoteTaskService, Depends(executor_service)]


@router.post("/poll", summary="执行端心跳与幂等领取；不创建运动任务")
def poll(body: PollRequest, service: Executor):
    return service.poll(body)


@router.post("/disconnect", summary="执行端主动关闭；关闭新任务准入")
def disconnect(body: PollRequest, service: Executor):
    return service.disconnect(body)


@router.post("/tasks/{task_id}/start", summary="确认短期启动许可；客户端只尝试启动一次")
def start(task_id: str, body: DeliveryRequest, service: Executor):
    return service.start(task_id, body)


@router.post("/tasks/{task_id}/report", summary="按序回报进度或已结束结果，终态发布前等待文件")
def report(task_id: str, body: TaskReport, service: Executor):
    return service.report(task_id, body)


@router.post("/tasks/{task_id}/complete", summary="幂等确认完整结果与录像已交付")
def complete(task_id: str, body: DeliveryRequest, service: Executor):
    return service.complete(task_id, body)


@router.post("/tasks/{task_id}/video", summary="流式接收已登记的MP4，校验大小和SHA256后归档")
async def video(
    task_id: str,
    request: Request,
    service: Executor,
    x_executor_session: Annotated[UUID, Header()],
    x_task_token: Annotated[str, Header(min_length=32, max_length=128)],
):
    body = DeliveryRequest(session_id=x_executor_session, lease_token=x_task_token)
    expected = service.expected_video(task_id, body)
    directory = service.store.directory(task_id)
    descriptor, filename = tempfile.mkstemp(prefix=".video-", suffix=".tmp", dir=directory)
    temporary = Path(filename)
    try:
        import os

        received = 0
        with os.fdopen(descriptor, "wb") as output:
            async for chunk in request.stream():
                received += len(chunk)
                if received > min(expected["size"], service.settings.REMOTE_MAX_VIDEO_BYTES):
                    raise ServiceError(
                        413, "VIDEO_TOO_LARGE", "Recording exceeds the declared upload size"
                    )
                output.write(chunk)
        return service.accept_video(task_id, body, temporary)
    finally:
        temporary.unlink(missing_ok=True)
