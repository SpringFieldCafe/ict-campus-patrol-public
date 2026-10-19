"""Executor-only protocol; independent of browser OAuth credentials."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PollRequest(StrictModel):
    session_id: UUID
    device_id: str = Field(min_length=1, max_length=80)
    configured: bool
    accepting: bool
    current_task_id: str | None = Field(default=None, pattern=r"^task-[a-f0-9]{32}$")


class DeliveryRequest(StrictModel):
    session_id: UUID
    lease_token: str = Field(min_length=32, max_length=128)


class VideoDescriptor(StrictModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(gt=0, le=256 * 1024 * 1024)


class ExecutionError(StrictModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)


class TaskReport(DeliveryRequest):
    sequence: int = Field(ge=1)
    state: Literal[
        "PREPARING",
        "NAVIGATING",
        "STOPPING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
        "REJECTED",
    ]
    execution_finished: bool
    requires_operator_review: bool = False
    simulation_progress: dict | None = None
    simulation_summary: dict | None = None
    error: ExecutionError | None = None
    video: VideoDescriptor | None = None
