import json

import pytest
from test_api import wait_for_task

from app.services import runtime


def test_route_submission_snapshots_checkpoints_and_remains_simulation(api):
    client, service, headers, owner = api
    routes = client.get("/api/v1/capabilities", headers=headers).json()["simulation_routes"]
    assert len(routes[0]["waypoints"]) == 3
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "simulation_route_id": routes[0]["id"],
            "mode": "simulation",
        },
    )
    assert response.status_code == 202, response.text
    task = wait_for_task(client, headers, response.json()["task_id"])
    assert task["state"] == "SUCCEEDED"
    assert task["simulation_route"] == routes[0]
    assert task["point_id"] == routes[0]["id"]
    assert task["photo_available"] is False
    directory = service.store.directory(task["task_id"])
    assert json.loads((directory / "waypoints.json").read_text()) == routes[0]["waypoints"]
    assert task["simulation_summary"]["reached_indices"] == [0, 1, 2]


@pytest.mark.parametrize(
    "body",
    [
        {"simulation_route_id": "checkpoints-simple", "mode": "motion"},
        {"simulation_route_id": "checkpoints-simple", "point_id": "a", "mode": "simulation"},
        {"simulation_route_id": "missing", "mode": "simulation"},
        {"mode": "simulation"},
    ],
)
def test_invalid_route_requests_do_not_launch_workers(api, body):
    client, service, headers, owner = api
    assert client.post("/api/v1/tasks", headers=headers, json=body).status_code == 422
    assert service.store.identifiers() == []


def test_invalid_catalog_never_reaches_runner(api, tmp_path):
    client, service, headers, owner = api
    bad = tmp_path / "bad-routes.json"
    bad.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "routes": [
                    {
                        "id": "bad",
                        "description": "bad",
                        "scene": "flat_obstacle",
                        "waypoints": [{"x": 1, "y": 0, "radius": -1}],
                    }
                ],
            }
        )
    )
    service.settings = service.settings.model_copy(update={"SIM_ROUTES": bad})
    with pytest.raises(ValueError):
        runtime.simulation_routes(service.settings)
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "simulation_route_id": "bad",
            "mode": "simulation",
        },
    )
    assert response.status_code == 503


def test_route_cannot_succeed_with_missing_checkpoint_even_if_runner_claims_goal(api):
    client, service, headers, owner = api
    service.settings = service.settings.model_copy(update={"SIM_STEPS": 2})
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "simulation_route_id": "checkpoints-simple",
            "mode": "simulation",
        },
    )
    assert response.status_code == 202
    task = wait_for_task(client, headers, response.json()["task_id"])
    assert task["simulation_summary"]["goal_reached"] is True
    assert task["simulation_summary"]["waypoints_reached"] == 2
    assert task["state"] == "FAILED"


def test_wall_route_is_snapshotted_and_uses_server_control_parameters(api):
    client, service, headers, owner = api
    route = runtime.select_simulation_route(service.settings, "checkpoints-walls")
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"mode": "simulation", "simulation_route_id": route["id"]},
    )
    assert response.status_code == 202
    identifier = response.json()["task_id"]
    command = runtime.simulation_command(
        service.settings, response.json()["point"], service.store.directory(identifier), route
    )
    assert command[command.index("--scene") + 1] == "staggered_walls"
    for key, value in route.get("control", {}).items():
        assert command[command.index("--" + key.replace("_", "-")) + 1] == str(value)
    task = wait_for_task(client, headers, identifier)
    assert task["simulation_route"] == route and task["state"] == "SUCCEEDED"
