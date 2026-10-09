"""One explicitly authorized public-landmark request, then network-denied restart/query.

Run under the existing resource wrapper. Uses a temporary store, no personal area,
no model, no GPS. The receipt refuses a second attempt unless an operator chooses
a new evidence directory explicitly; do not retry a public source automatically.
"""

import asyncio
import json
import socket
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.evidence_store import EvidenceStore
from app.item_repository import ItemRepository
from app.poi import POICache
from app.poi_contracts import NearestRequest
from app.poi_download import ENDPOINT, AreaDownload, AreaDownloader
from app.requests import RequestRegistry

OUT = Path(__file__).resolve().parents[1] / "deliverables/nook-live-area"
OUT.mkdir(exist_ok=True)
receipt = OUT / "attempt.json"
# Public geographic landmark: Trafalgar Square, London. Not a user location.
center = {"lat": 51.5080, "lon": -0.1281}
result = {
    "source": ENDPOINT,
    "landmark": "Trafalgar Square, London",
    "center": center,
    "radius_m": 100,
    "utc": datetime.now(UTC).isoformat(),
    "network_attempts": 0,
    "passed": False,
}
with receipt.open("x") as f:
    json.dump(result, f, indent=2)
try:
    with tempfile.TemporaryDirectory(prefix="nook-live-area-") as folder:
        settings = Settings(data_dir=Path(folder) / "data")
        store = EvidenceStore(settings)
        try:
            repo = ItemRepository(settings, store)
            poi = POICache(repo.db)
            poi.initialize()
            request = SimpleNamespace(
                app=SimpleNamespace(state=SimpleNamespace(poi=poi, requests=RequestRegistry()))
            )
            body = AreaDownload.model_validate(
                {
                    "confirmed": True,
                    "consent_to_share_area": True,
                    "request_id": str(uuid4()),
                    "expected_generation": repo.generation(),
                    "label": "Public landmark smoke: Trafalgar Square",
                    "center": center,
                    "radius_m": 100,
                }
            )
            result["network_attempts"] = 1
            download = asyncio.run(AreaDownloader(True).run(body, request))
            result["download"] = download
            assert download["download_bytes"] <= 1024 * 1024
            assert 0 < download["cache"]["record_count"] <= 250
        finally:
            store.close()
        # Deny Python outbound connections for the persistence/query phase only.
        # This is not OS-wide isolation and does not alter firewall/security state.
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex

        def deny(*args, **kwargs):
            raise OSError("Offline verification: outbound socket denied")

        socket.socket.connect = deny
        socket.socket.connect_ex = deny
        try:
            store = EvidenceStore(settings)
            try:
                repo = ItemRepository(settings, store)
                poi = POICache(repo.db)
                poi.initialize()
                current = poi.status()
                assert current["download_provenance"] == download["cache"]["download_provenance"]
                with repo.db.connect() as conn:
                    category = conn.execute(
                        "SELECT category FROM poi_cache_entries LIMIT 1"
                    ).fetchone()[0]
                nearest = poi.nearest(
                    NearestRequest.model_validate(
                        {
                            "confirmed": True,
                            "location": {
                                **center,
                                "captured_at": datetime.now(UTC).isoformat(),
                                "accuracy_m": 1000,
                            },
                            "category": category,
                            "max_distance_m": 5000,
                            "limit": 20,
                        }
                    )
                )
                assert nearest["results"]
                result.update(
                    passed=True,
                    restart_provenance_preserved=True,
                    offline_lookup=nearest,
                    offline_scope="Python socket guard during restart and nearest lookup; not OS-wide isolation",
                )
            finally:
                store.close()
        finally:
            socket.socket.connect = original_connect
            socket.socket.connect_ex = original_connect_ex
except Exception as exc:
    result["error_type"] = type(exc).__name__
    result["error"] = str(exc)
finally:
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"download", "offline_lookup"}}))
if not result["passed"]:
    raise SystemExit(1)
