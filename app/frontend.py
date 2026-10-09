"""Fixed same-origin browser assets; no user-controlled filesystem paths."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

ASSETS = {
    "/": "index.html",
    "/assets/styles.css": "styles.css",
    "/assets/app.js": "app.js",
    "/assets/experience.js": "experience.js",
    "/assets/places.js": "places.js",
    "/assets/memory-prompt.js": "memory-prompt.js",
    "/assets/media.js": "media.js",
    "/assets/recorder.js": "recorder.js",
}
router = APIRouter()


def asset_response(filename: str):
    def serve() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / filename)

    return serve


for route, filename in ASSETS.items():
    router.add_api_route(
        route, asset_response(filename), methods=["GET", "HEAD"], include_in_schema=False
    )
