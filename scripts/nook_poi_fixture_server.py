"""Test-only server: synthetic Overpass boundary; never real retrieval acceptance."""

import asyncio
import json
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn

from app.config import Settings
from app.main import create_app


def deny(*args, **kwargs):
    raise OSError("Fixture server denies outbound network")


socket.socket.connect = deny
socket.socket.connect_ex = deny
settings = Settings.from_env()
app = create_app(settings)
original = app.router.lifespan_context


@asynccontextmanager
async def lifespan(api):
    async with original(api):

        async def synthetic(query):
            print("SYNTHETIC_SOURCE_BOUNDARY", flush=True)
            await asyncio.sleep(0.1)
            return json.dumps(
                {
                    "osm3s": {"timestamp_osm_base": "2026-10-09T00:00:00Z"},
                    "elements": [
                        {
                            "type": "node",
                            "id": 1,
                            "lat": 0.0,
                            "lon": 0.0,
                            "tags": {"amenity": "cafe", "name": "Synthetic offline cafe"},
                        }
                    ],
                }
            ).encode()

        api.state.area_downloader.fetch = synthetic
        yield


app.router.lifespan_context = lifespan
uvicorn.run(app, host="127.0.0.1", port=settings.port)
