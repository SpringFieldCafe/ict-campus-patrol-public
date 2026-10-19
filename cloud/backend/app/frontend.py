"""Serve a built console without turning unknown API or filesystem paths into SPA routes."""

from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

SPA_PATHS = ("/", "/login", "/console", "/history", "/project")
PUBLIC_FILES = (
    "favicon.svg",
    "favicon.ico",
    "app-loading.css",
    "detect-ie.js",
    "template-LICENSE.txt",
)
ASSET_SUFFIXES = {
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".avif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".wasm",
}


def published_file(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    return resolved.is_relative_to(root) and resolved.is_file()


class ConsoleAssets(StaticFiles):
    async def get_response(self, path: str, scope):
        parts = Path(path).parts
        if (
            any(
                part.startswith(".")
                or part.casefold().split(".")[0] in {"private", "secrets", "credentials"}
                for part in parts
            )
            or Path(path).suffix.lower() not in ASSET_SUFFIXES
        ):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)


def attach_frontend(app: FastAPI, path: Path) -> bool:
    """Register only published console paths, returning false when no build exists.

    Call after API routes have been registered. Build presence is checked once;
    restart the API after creating the first build.
    """
    root = path.resolve()
    index = root / "index.html"
    if not published_file(index, root):
        return False

    async def console_index():
        if not published_file(index, root):
            raise HTTPException(status_code=404)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    for route in SPA_PATHS:
        app.add_api_route(
            route,
            console_index,
            methods=["GET", "HEAD"],
            tags=["console"],
            include_in_schema=False,
        )

    def public_response(filename: str):
        async def serve():
            target = root / filename
            if not published_file(target, root):
                raise HTTPException(status_code=404)
            return FileResponse(target)

        return serve

    for filename in PUBLIC_FILES:
        if published_file(root / filename, root):
            app.add_api_route(
                "/" + filename,
                public_response(filename),
                methods=["GET", "HEAD"],
                tags=["console"],
                include_in_schema=False,
            )

    assets = root / "assets"
    if assets.is_dir() and assets.resolve().is_relative_to(root):
        app.mount("/assets", ConsoleAssets(directory=assets), name="console-assets")
    return True
