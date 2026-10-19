from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    point_id: str | None = Field(
        default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$"
    )
    simulation_route_id: str | None = Field(
        default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$"
    )
    mode: Literal["simulation", "motion"]
    question: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_target(self):
        if (self.point_id is None) == (self.simulation_route_id is None):
            raise ValueError("Choose exactly one observation point or simulation route")
        if self.simulation_route_id is not None and self.mode != "simulation":
            raise ValueError("Checkpoint routes are simulation-only")
        return self


class AnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)


class TaskView(BaseModel):
    task_id: str
    point_id: str
    point: dict
    point_reference: Literal["initial_pose"]
    mode: Literal["simulation", "motion"]
    question: str
    state: Literal[
        "PREPARING",
        "NAVIGATING",
        "PARKED",
        "CAPTURING",
        "STOPPING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
        "REJECTED",
    ]
    created_at_utc: str
    updated_at_utc: str
    timeout_seconds: float
    error: dict | None
    stop_acknowledged: bool | None
    cleanup_forced: bool
    requires_operator_review: bool
    worker_alive: bool
    cancel_requested: bool
    photo_available: bool
    video_available: bool
    photo_url: str | None
    video_url: str | None
    photo: dict | None = None
    simulation_progress: dict | None = None
    simulation_summary: dict | None = None
    simulation_route: dict | None = None
    execution_backend: Literal["local", "remote"] = "local"
    executor_online: bool | None = None
    remote_pending: bool = False
    remote_phase: Literal["WAITING", "RUNNING", "UPLOADING", "DELIVERED"] | None = None
    analysis_state: str
    analysis_error: dict | None = None
    answer: dict | None


class TasksPage(BaseModel):
    data: list[TaskView]
    count: int
