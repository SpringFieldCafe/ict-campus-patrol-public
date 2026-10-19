import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser
from app.schemas import AnalysisCreate, TaskCreate, TasksPage, TaskView
from app.services import runtime
from app.services.store import ServiceError
from app.services.tasks import TaskService

router = APIRouter(tags=["observation"])


def get_service(request: Request) -> TaskService:
    return request.app.state.tasks


Service = Annotated[TaskService, Depends(get_service)]


@router.get("/capabilities", summary="查看实际配置状态，不连接机器人或模型")
def capabilities(current_user: CurrentUser, service: Service):
    return service.capabilities()


@router.get("/points", summary="列出观察点；坐标以每次启动位姿为参考")
def observation_points(current_user: CurrentUser, service: Service):
    if service.settings.REMOTE_ENABLED:
        return {"reference": "initial_pose", "example_configuration": True, "points": []}
    try:
        return runtime.points(service.settings)
    except OSError, ValueError, TypeError:
        raise ServiceError(
            503, "POINTS_NOT_CONFIGURED", "Observation point configuration is invalid"
        ) from None


@router.post(
    "/tasks", status_code=202, response_model=TaskView, summary="提交单个任务；忙时返回409"
)
def create_task(body: TaskCreate, current_user: CurrentUser, service: Service):
    return service.create(
        body.point_id, body.mode, body.question, str(current_user.id), body.simulation_route_id
    )


@router.get("/tasks", response_model=TasksPage, summary="查看持久保存的任务历史")
def list_tasks(
    current_user: CurrentUser,
    service: Service,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return service.list(str(current_user.id), current_user.is_superuser, offset, limit)


@router.get("/tasks/{task_id}", response_model=TaskView, summary="查询阶段、结果和问答状态")
def task_status(task_id: str, current_user: CurrentUser, service: Service):
    service.owned(task_id, str(current_user.id), current_user.is_superuser)
    return service.view(task_id)


@router.post("/tasks/{task_id}/cancel", summary="请求取消；返回成功不代表机器狗已停")
def cancel_task(task_id: str, current_user: CurrentUser, service: Service):
    service.owned(task_id, str(current_user.id), current_user.is_superuser)
    return service.cancel(task_id)


@router.get("/tasks/{task_id}/events", summary="读取阶段事件；不返回私有执行日志")
def task_events(
    task_id: str,
    current_user: CurrentUser,
    service: Service,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    service.owned(task_id, str(current_user.id), current_user.is_superuser)
    path = service.store.directory(task_id) / "events.jsonl"
    values = [json.loads(line) for line in path.read_text().splitlines() if line]
    return {"data": values[after : after + limit], "next_offset": min(len(values), after + limit)}


@router.get("/tasks/{task_id}/photo", summary="读取经过任务号与SHA256校验的真实相机照片")
def task_photo(task_id: str, current_user: CurrentUser, service: Service):
    metadata = service.owned(task_id, str(current_user.id), current_user.is_superuser)
    state = service.store.reconcile(task_id)
    if metadata["mode"] != "motion" or state["state"] != "SUCCEEDED":
        raise ServiceError(409, "PHOTO_NOT_READY", "No verified camera photo is available")
    image, evidence, mime = runtime.photo_evidence(service.settings, task_id)
    return FileResponse(
        image,
        media_type=mime,
        headers={
            "Cache-Control": "private, no-store",
            "ETag": '"' + evidence["image_sha256"] + '"',
        },
    )


@router.get("/tasks/{task_id}/video", summary="读取已完成的仿真录像（场景自由相机视角）")
def task_video(task_id: str, current_user: CurrentUser, service: Service):
    metadata = service.owned(task_id, str(current_user.id), current_user.is_superuser)
    if metadata["mode"] != "simulation" or not service.store.reconcile(task_id).get(
        "video_available"
    ):
        raise ServiceError(409, "VIDEO_NOT_READY", "No finalized simulation video is available")
    directory = service.store.directory(task_id)
    video = runtime.inside(directory / "simulation.mp4", directory)
    return FileResponse(
        video, media_type="video/mp4", headers={"Cache-Control": "private, no-store"}
    )


@router.get("/tasks/{task_id}/result", summary="返回照片证据／仿真摘要与模型回答")
def task_result(task_id: str, current_user: CurrentUser, service: Service):
    service.owned(task_id, str(current_user.id), current_user.is_superuser)
    value = service.view(task_id)
    return {
        key: value.get(key)
        for key in (
            "task_id",
            "mode",
            "state",
            "error",
            "photo",
            "photo_url",
            "video_url",
            "simulation_summary",
            "analysis_state",
            "analysis_error",
            "answer",
        )
    }


@router.post(
    "/tasks/{task_id}/analysis",
    status_code=202,
    response_model=TaskView,
    summary="显式请求对成功采集的照片问答；不会重新移动或拍照",
)
def analyze_photo(task_id: str, body: AnalysisCreate, current_user: CurrentUser, service: Service):
    service.owned(task_id, str(current_user.id), current_user.is_superuser)
    return service.analyze(task_id, body.question)
