"""Real HTTP smoke test, temporary synthetic data, test server stopped on exit."""

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from PIL import Image

BASE = "http://127.0.0.1:18765"


def run(output: Path, vision: bool = False) -> None:
    results: dict[str, Any] = {
        "address": BASE,
        "server_remains_running": False,
        "synthetic_records": True,
        "photo": "CC0 public coffee photograph" if vision else "synthetic purple image",
        "checks": [],
        "vision": "real NanoDet CPU" if vision else "explicitly disabled; manual fallback",
    }
    with tempfile.TemporaryDirectory(prefix="appbuilderhck-http-smoke-") as folder:
        environment = dict(os.environ, APP_DATA_DIR=str(Path(folder) / "data"), APP_PORT="18765")
        for variable in ("APP_TEXT_MODEL", "APP_VISION_MODEL", "APP_VISION_SHA256"):
            environment.pop(variable, None)
        environment["APP_VISION_DISABLED"] = "0" if vision else "1"
        audit = Path(folder) / "offline-audit.jsonl"
        environment["APP_OFFLINE_AUDIT_LOG"] = str(audit)
        log = open(Path(folder) / "server.log", "wb")
        process = None

        def start():
            child = subprocess.Popen(
                [sys.executable, "-m", "scripts.offline_server"],
                env=environment,
                stdout=log,
                stderr=log,
            )
            for _ in range(60):
                if child.poll() is not None:
                    raise RuntimeError("Test server exited before readiness")
                try:
                    with httpx.Client(trust_env=False, timeout=2) as probe:
                        if probe.get(BASE + "/api/status").status_code == 200:
                            return child
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            child.terminate()
            child.wait(timeout=5)
            raise RuntimeError("Test server did not become ready")

        def stop(child):
            if child and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)

        try:
            process = start()
            with httpx.Client(base_url=BASE, trust_env=False, timeout=30) as client:
                client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
                status = client.get("/api/status").json()
                assert not status["cloud_dependency"] and not status["vision"]["inference_verified"]
                assert status["vision"]["available"] is vision
                results["checks"].append("localhost startup and honest model status")
                invalid = client.post(
                    "/api/captures", content=b"malformed", headers={"Content-Type": "image/png"}
                )
                assert invalid.status_code == 422
                out = io.BytesIO()
                Image.new("RGB", (180, 120), "purple").save(out, "PNG")
                image = (
                    (
                        Path(__file__).resolve().parents[1] / "tests/fixtures/vision/coffee.png"
                    ).read_bytes()
                    if vision
                    else out.getvalue()
                )
                draft = client.post(
                    "/api/captures?source=camera",
                    content=image,
                    headers={"Content-Type": "image/png"},
                ).json()
                assert client.get("/api/items").json()["total"] == 0
                row: dict[str, Any] = {"identity": "new", "personal_name": "purple utility tool"}
                if vision:
                    suggestion = client.post(
                        f"/api/captures/{draft['id']}/suggest", json={"request_id": str(uuid4())}
                    )
                    assert suggestion.status_code == 200, suggestion.text
                    suggested = suggestion.json()
                    candidate = next(c for c in suggested["candidates"] if c["category"] == "cup")
                    assert suggested["inference_used"] and suggested["draft_saved_items"] == 0
                    assert (
                        not suggested["identity_verified"]
                        and not suggested["location_verified"]
                        and not suggested["inventory_complete"]
                    )
                    assert client.get("/api/items").json()["total"] == 0
                    row = {
                        "identity": "new",
                        "personal_name": "ceramic evaluation cup",
                        "category": "cup",
                        "candidate_id": candidate["id"],
                        "region": candidate["region"],
                    }
                    results["vision_elapsed_ms"] = suggested["elapsed_ms"]
                    results["checks"].append(
                        "real CPU candidates remain unsaved; explicit identity/location/region review required"
                    )
                else:
                    assert (
                        client.post(
                            f"/api/captures/{draft['id']}/suggest",
                            json={"request_id": str(uuid4())},
                        ).status_code
                        == 503
                    )
                body = {
                    "confirmed": True,
                    "idempotency_key": str(uuid4()),
                    "location": "Synthetic purple cabinet",
                    "make_current": True,
                    "rows": [row],
                }
                rejected = client.post(
                    f"/api/captures/{draft['id']}/commit", json={**body, "confirmed": False}
                )
                assert rejected.status_code == 422 and client.get("/api/items").json()["total"] == 0
                saved = client.post(f"/api/captures/{draft['id']}/commit", json=body)
                assert saved.status_code == 200
                assert client.post(f"/api/captures/{draft['id']}/commit", json=body).json()[
                    "replayed"
                ]
                item = saved.json()["items"][0]
                if vision:
                    provenance = item["current_observation"]["candidate_provenance"]
                    assert (
                        provenance["category"] == "cup"
                        and item["personal_name"] == row["personal_name"]
                    )
                photo = item["current_observation"]["photo"]
                assert client.get(photo["url"]).headers["content-type"] == "image/jpeg"
                answer = client.post(
                    "/api/recall",
                    json={
                        "query": "Where did I put my " + row["personal_name"] + "?",
                        "request_id": str(uuid4()),
                    },
                ).json()
                assert (
                    answer["kind"] == "found" and answer["items"][0]["location"] == body["location"]
                )
                results["checks"].append(
                    "invalid upload; draft boundary; upload-confirm-save-recall with photo; idempotent retry"
                )
                renamed = "renamed evaluation cup" if vision else "renamed purple utility tool"
                edited = client.patch(
                    f"/api/items/{item['id']}",
                    json={
                        "confirmed": True,
                        "idempotency_key": str(uuid4()),
                        "expected_revision": 1,
                        "personal_name": renamed,
                    },
                )
                assert edited.status_code == 200
                item = edited.json()["items"][0]
                assert (
                    item["revision"] == 2
                    and item["current_observation"]["confirmed_at"]
                    == saved.json()["items"][0]["current_observation"]["confirmed_at"]
                )
                duplicate = client.post(
                    "/api/items",
                    json={
                        "confirmed": True,
                        "idempotency_key": str(uuid4()),
                        "personal_name": renamed,
                        "location": "Second synthetic location",
                    },
                ).json()["items"][0]
                ambiguous = client.post(
                    "/api/recall", json={"query": renamed, "request_id": str(uuid4())}
                ).json()
                assert ambiguous["kind"] == "clarify" and ambiguous["total"] == 2
                assert (
                    client.request(
                        "DELETE",
                        f"/api/items/{duplicate['id']}",
                        json={
                            "confirmed": True,
                            "idempotency_key": str(uuid4()),
                            "expected_revision": 1,
                            "evidence_scope": "unreferenced",
                        },
                    ).status_code
                    == 200
                )
                results["checks"].append(
                    "metadata edit preserves observation time; duplicate names require clarification and separate IDs"
                )
                assert (
                    client.get("/api/items", headers={"Origin": "https://example.com"}).status_code
                    == 403
                )
                results["checks"].append("cross-origin request denied")
            stop(process)
            process = start()
            with httpx.Client(base_url=BASE, trust_env=False, timeout=30) as client:
                client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
                persisted = client.get(f"/api/items/{item['id']}").json()
                assert persisted == item and client.get(photo["url"]).status_code == 200
                results["checks"].append(
                    "real process restart preserves confirmed record and photo"
                )
                if vision:
                    fresh = client.post(
                        "/api/captures", content=image, headers={"Content-Type": "image/png"}
                    ).json()
                    repeated = client.post(
                        f"/api/captures/{fresh['id']}/suggest", json={"request_id": str(uuid4())}
                    )
                    assert repeated.status_code == 200 and any(
                        c["category"] == "cup" for c in repeated.json()["candidates"]
                    )
                    assert client.delete(f"/api/captures/{fresh['id']}").status_code == 200
                    results["checks"].append(
                        "fresh real local inference succeeds after process restart with outbound sockets blocked"
                    )
                mutation = {
                    "confirmed": True,
                    "idempotency_key": str(uuid4()),
                    "expected_revision": 2,
                    "location": None,
                }
                moved = client.post(f"/api/items/{item['id']}/observations", json=mutation)
                assert moved.status_code == 200 and moved.json()["items"][0]["location"] is None
                moved_recall = client.post(
                    "/api/recall", json={"query": renamed, "request_id": str(uuid4())}
                ).json()
                assert (
                    moved_recall["kind"] == "unknown"
                    and moved_recall["items"][0]["location"] is None
                )
                assert (
                    client.post(
                        f"/api/items/{item['id']}/observations",
                        json={**mutation, "idempotency_key": str(uuid4())},
                    ).status_code
                    == 409
                )
                deletion = {
                    "confirmed": True,
                    "idempotency_key": str(uuid4()),
                    "expected_revision": 3,
                    "evidence_scope": "unreferenced",
                }
                assert (
                    client.request("DELETE", f"/api/items/{item['id']}", json=deletion).status_code
                    == 200
                )
                assert client.get(photo["url"]).status_code == 404
                unknown = client.post(
                    "/api/recall", json={"query": renamed, "request_id": str(uuid4())}
                ).json()
                assert unknown["kind"] == "unknown" and unknown["items"] == []
                results["checks"].append(
                    "move/unknown; stale revision rejection; delete removes evidence and recall"
                )
        finally:
            stop(process)
            log.close()
        audit_events = [json.loads(line) for line in audit.read_text().splitlines()]
        runtime_events = [e for e in audit_events if e["phase"] == "backend_runtime"]
        assert not runtime_events, runtime_events
        assert len([e for e in audit_events if e["phase"] == "guard_self_test"]) == 2
        results["offline"] = {
            "guard_self_tests_passed": 2,
            "runtime_outbound_python_attempts": runtime_events,
            "scope": "All outbound Python socket/DNS calls denied inside both server processes; workers also deny outbound calls. No native syscall trace or physical WAN/LAN manipulation.",
        }
    results["passed"] = True
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vision", action="store_true")
    args = parser.parse_args()
    run(args.output, args.vision)
