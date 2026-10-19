"""Huawei MaaS image-chat adapter. No SDK, retries or public image upload required."""

import base64
from typing import TYPE_CHECKING

import httpx

from app.services.store import ServiceError, TaskStore, atomic_json, now, read_object

if TYPE_CHECKING:
    from app.core.config import Settings


def ask_image(
    settings: Settings,
    photo: bytes,
    mime: str,
    question: str,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    if not settings.huawei_configured:
        raise ServiceError(503, "HUAWEI_NOT_CONFIGURED", "Configure a Huawei vision model locally")
    content = base64.b64encode(photo).decode("ascii")
    try:
        with httpx.Client(
            timeout=settings.HUAWEI_TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as client:
            response = client.post(
                settings.HUAWEI_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": "Bearer " + settings.HUAWEI_API_KEY.get_secret_value(),
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.HUAWEI_MODEL,
                    "stream": False,
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": question},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{content}"},
                                },
                            ],
                        }
                    ],
                },
            )
            if response.status_code != 200:
                raise ServiceError(
                    502,
                    "MODEL_REQUEST_FAILED",
                    f"Model service returned HTTP {response.status_code}",
                )
            value = response.json()
            answer = value["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Empty model answer")
            return {
                "answer": answer,
                "provider": "huawei_maas",
                "model": settings.HUAWEI_MODEL,
                "request_id": value.get("id"),
                "answered_at_utc": now(),
            }
    except httpx.TimeoutException:
        raise ServiceError(
            504, "MODEL_TIMEOUT", "Model service timed out; no automatic retry"
        ) from None
    except httpx.HTTPError:
        raise ServiceError(
            502, "MODEL_CONNECTION_FAILED", "Could not connect to model service"
        ) from None
    except ValueError, KeyError, IndexError, TypeError:
        raise ServiceError(
            502, "INVALID_MODEL_RESPONSE", "Model service returned an invalid answer"
        ) from None


def analyze(settings: Settings, store: TaskStore, task_id: str, question: str) -> None:
    # Offline evaluation reuses ask_image without loading account/robot configuration.
    from app.services import runtime

    metadata = store.metadata(task_id)
    state = store.state(task_id)
    if metadata["mode"] != "motion":
        store.update(task_id, analysis_state="NO_CAMERA_PHOTO")
        return
    if not question:
        store.update(task_id, analysis_state="NOT_REQUESTED")
        return
    if not settings.huawei_configured:
        store.update(task_id, analysis_state="NOT_CONFIGURED")
        return
    if state["state"] != "SUCCEEDED":
        return
    store.update(task_id, analysis_state="RUNNING", analysis_error=None)
    try:
        image, evidence, mime = runtime.photo_evidence(settings, task_id)
        answer = ask_image(settings, image.read_bytes(), mime, question)
        answer.update(task_id=task_id, question=question, image_sha256=evidence["image_sha256"])
        atomic_json(store.directory(task_id) / "answer.json", answer)
        store.update(task_id, analysis_state="SUCCEEDED")
    except ServiceError as error:
        store.update(
            task_id,
            analysis_state="FAILED",
            analysis_error={
                "code": error.code,
                "message": error.message,
            },
        )
    except Exception:
        # Cloud/persistence failures never rewrite the successful robot task state.
        store.update(
            task_id,
            analysis_state="FAILED",
            analysis_error={
                "code": "ANALYSIS_FAILED",
                "message": "Could not complete or save the model answer",
            },
        )


def read_answer(store: TaskStore, task_id: str) -> dict | None:
    state = store.state(task_id)
    if state.get("analysis_state") != "SUCCEEDED":
        return None
    return read_object(store.directory(task_id) / "answer.json")
