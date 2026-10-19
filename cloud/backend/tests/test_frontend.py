"""Check SPA refreshes and static serving without touching the running API or robot."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.frontend import SPA_PATHS, attach_frontend


@pytest.fixture
def console(tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html>console fixture</html>")
    (dist / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (dist / "app-loading.css").write_text("body { color: black; }")
    (dist / "detect-ie.js").write_text("/* browser compatibility fixture */")
    (assets / "app-123.js").write_text("console.log('fixture')")
    (dist / ".env").write_text("SYNTHETIC_SECRET=do-not-serve")
    (dist / "private").mkdir()
    (dist / "private/config.json").write_text('{"synthetic_secret": true}')
    (assets / ".env.js").write_text("synthetic secret")
    (assets / "private").mkdir()
    (assets / "private/config.js").write_text("synthetic secret")
    (assets / "source.js.map").write_text("synthetic source map")
    outside = tmp_path / "outside.js"
    outside.write_text("synthetic outside file")
    (assets / "outside.js").symlink_to(outside)
    app = FastAPI(generate_unique_id_function=lambda route: route.tags[0] + "-" + route.name)

    @app.get("/api/v1/example", tags=["api"])
    def example():
        return {"source": "api"}

    assert attach_frontend(app, dist)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("path", SPA_PATHS)
def test_known_spa_routes_support_refresh_and_head(console, path):
    response = console.get(path)
    assert response.status_code == 200
    assert response.text == "<html>console fixture</html>"
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"
    assert console.head(path).status_code == 200


@pytest.mark.parametrize(
    "path", ["/favicon.svg", "/app-loading.css", "/detect-ie.js", "/assets/app-123.js"]
)
def test_explicit_public_files_and_built_assets(console, path):
    assert console.get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/unknown",
        "/api/v1/missing",
        "/unknown",
        "/.env",
        "/.env.local",
        "/private/config.json",
        "/index.html",
        "/src/main.ts",
        "/assets/.env.js",
        "/assets/private/config.js",
        "/assets/source.js.map",
        "/assets/outside.js",
        "/assets/missing.js",
        "/assets/%2e%2e/.env",
    ],
)
def test_unpublished_paths_do_not_serve_files_or_spa(console, path):
    response = console.get(path)
    assert response.status_code == 404
    assert "console fixture" not in response.text
    assert "synthetic secret" not in response.text
    assert "SYNTHETIC_SECRET" not in response.text


def test_api_docs_and_methods_are_unchanged(console):
    assert console.get("/api/v1/example").json() == {"source": "api"}
    assert console.get("/docs").status_code == 200
    assert set(console.get("/openapi.json").json()["paths"]) == {"/api/v1/example"}
    assert console.post("/console").status_code == 405


def test_missing_build_leaves_backend_available(tmp_path):
    app = FastAPI()
    assert not attach_frontend(app, tmp_path / "not-built")
    with TestClient(app) as client:
        assert client.get("/").status_code == 404
        assert client.get("/docs").status_code == 200


def test_build_index_and_public_symlinks_cannot_escape(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    outside = tmp_path / "outside.html"
    outside.write_text("synthetic private page")
    (dist / "index.html").symlink_to(outside)
    assert not attach_frontend(FastAPI(), dist)
    (dist / "index.html").unlink()
    (dist / "index.html").write_text("console fixture")
    (dist / "favicon.svg").symlink_to(outside)
    app = FastAPI()
    assert attach_frontend(app, dist)
    with TestClient(app) as client:
        assert client.get("/favicon.svg").status_code == 404
