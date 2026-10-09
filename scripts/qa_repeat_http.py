"""Repeated real HTTP races and model-failure recovery; owns all temporary servers/data."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx

from app.inference.nanodet import MODEL_FILENAME, MODEL_SHA256

ROOT = Path(__file__).resolve().parents[1]
PORT = 18793
BASE = f"http://127.0.0.1:{PORT}"


def confirmed(**fields):
    return {"confirmed": True, "idempotency_key": str(uuid4()), **fields}


def run(output: Path) -> None:
    cases = []
    pids = []
    all_runtime: list[dict] = []
    self_tests = 0
    for profile in ("valid", "missing", "corrupt", "changed_after_start"):
        with tempfile.TemporaryDirectory(prefix="appbuilderhck-http-repeat-") as folder:
            scratch = Path(folder)
            model = scratch / MODEL_FILENAME
            if profile in ("valid", "changed_after_start"):
                model.write_bytes((ROOT / "models" / MODEL_FILENAME).read_bytes())
            elif profile == "corrupt":
                altered = bytearray((ROOT / "models" / MODEL_FILENAME).read_bytes())
                altered[0] ^= 1
                model.write_bytes(altered)
            audit = scratch / "audit.jsonl"
            env = dict(os.environ)
            env.update(
                APP_PORT=str(PORT),
                APP_DATA_DIR=str(scratch / "data"),
                APP_VISION_MODEL=str(model),
                APP_VISION_SHA256=MODEL_SHA256,
                APP_VISION_DISABLED="0",
                APP_OFFLINE_AUDIT_LOG=str(audit),
                PYTHONDONTWRITEBYTECODE="1",
            )
            env.pop("APP_TEXT_MODEL", None)
            server = None
            log = (scratch / "server.log").open("wb")

            def stop():
                nonlocal server
                if server is not None:
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)
                    server = None

            def start(env=env, log=log):
                nonlocal server
                server = subprocess.Popen(
                    [sys.executable, "-m", "scripts.offline_server"],
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=log,
                )
                pids.append(server.pid)
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("Test server exited")
                    try:
                        with httpx.Client(base_url=BASE, timeout=1, trust_env=False) as probe:
                            if probe.get("/api/status").status_code == 200:
                                return
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.05)
                raise RuntimeError("Readiness timeout")

            def auth(client):
                client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]

            def upload(client, filename="museum-wallet.jpg"):
                response = client.post(
                    "/api/captures?source=import",
                    content=(
                        ROOT / "tests/fixtures/vision/heldout-20261009" / filename
                    ).read_bytes(),
                    headers={"Content-Type": "image/jpeg"},
                )
                assert response.status_code == 201, response.text
                return response.json()

            try:
                start()
                with httpx.Client(base_url=BASE, trust_env=False, timeout=30) as client:
                    auth(client)
                    status = client.get("/api/status").json()["vision"]
                    assert status["available"] == (profile in ("valid", "changed_after_start"))
                    if profile == "changed_after_start":
                        altered = bytearray(model.read_bytes())
                        altered[-1] ^= 1
                        model.write_bytes(altered)
                    draft = upload(client)
                    suggestion = client.post(
                        f"/api/captures/{draft['id']}/suggest", json={"request_id": str(uuid4())}
                    )
                    expected_status = 200 if profile == "valid" else 503
                    assert suggestion.status_code == expected_status, suggestion.text
                    if profile != "valid":
                        assert suggestion.json()["error"]["code"] == (
                            "vision_failed"
                            if profile == "changed_after_start"
                            else "vision_unavailable"
                        )
                    assert client.get(draft["photo_url"]).status_code == 200
                    assert client.get("/api/items").json()["total"] == 0
                    for category in ("wallet", "tv", "suitcase"):
                        unknown = client.post(
                            "/api/recall", json={"query": category, "request_id": str(uuid4())}
                        ).json()
                        assert unknown["kind"] == "unknown" and unknown["items"] == []
                    manual = confirmed(
                        location="QA manual cabinet",
                        make_current=True,
                        rows=[
                            {
                                "identity": "new",
                                "personal_name": "QA reviewed museum wallet",
                                "category": "wallet",
                            }
                        ],
                    )
                    assert (
                        client.post(
                            f"/api/captures/{draft['id']}/commit",
                            json={**manual, "confirmed": False},
                        ).status_code
                        == 422
                    )
                    item = client.post(f"/api/captures/{draft['id']}/commit", json=manual).json()[
                        "items"
                    ][0]
                    assert item["current_observation"]["candidate_provenance"] is None
                    answer = client.post(
                        "/api/recall",
                        json={"query": "QA reviewed museum wallet", "request_id": str(uuid4())},
                    ).json()
                    assert (
                        answer["kind"] == "found"
                        and answer["items"][0]["location"] == manual["location"]
                    )
                    for category in ("tv", "suitcase"):
                        assert (
                            client.post(
                                "/api/recall", json={"query": category, "request_id": str(uuid4())}
                            ).json()["items"]
                            == []
                        )
                    if profile == "valid":
                        # Actual worker underway: reuse/cancel/commit/discard races on ten new drafts.
                        with ThreadPoolExecutor(max_workers=4) as pool:
                            for n in range(10):
                                race = upload(client, "plastic-cup.jpg")
                                request_id = str(uuid4())
                                path = f"/api/captures/{race['id']}/suggest"
                                future = pool.submit(
                                    client.post, path, json={"request_id": request_id}
                                )
                                time.sleep(0.07)
                                assert not future.done(), (
                                    "Worker completed before the intended in-flight race"
                                )
                                duplicate = client.post(path, json={"request_id": request_id})
                                assert duplicate.status_code == 409
                                if n % 2 == 0:
                                    cancel = client.post(f"/api/requests/{request_id}/cancel")
                                    assert (
                                        cancel.status_code == 200 and "active" not in cancel.json()
                                    )
                                    response = future.result(timeout=10)
                                    assert (
                                        response.status_code == 409
                                        and response.json()["error"]["code"] == "request_cancelled"
                                    )
                                    assert (
                                        client.get(f"/api/captures/{race['id']}").json()[
                                            "candidates"
                                        ]
                                        == []
                                    )
                                    retry = client.post(path, json={"request_id": str(uuid4())})
                                    assert retry.status_code == 200
                                else:
                                    assert (
                                        client.delete(f"/api/captures/{race['id']}").status_code
                                        == 200
                                    )
                                    assert future.result(timeout=10).status_code in (409, 404)
                                    assert client.get(race["photo_url"]).status_code == 404
                                if n % 2 == 0:
                                    assert (
                                        client.delete(f"/api/captures/{race['id']}").status_code
                                        == 200
                                    )
                            # Confirmed duplicate operations race on three separate synthetic records.
                            for n in range(3):
                                create = confirmed(
                                    personal_name=f"QA HTTP duplicate {n}", location="QA drawer"
                                )
                                responses = list(
                                    pool.map(
                                        lambda _, create=create: client.post(
                                            "/api/items", json=create
                                        ),
                                        range(16),
                                    )
                                )
                                assert all(r.status_code == 201 for r in responses)
                                assert sum(not r.json()["replayed"] for r in responses) == 1
                                victim = responses[0].json()["items"][0]
                                observe = confirmed(expected_revision=1, location=None)
                                move = client.post(
                                    f"/api/items/{victim['id']}/observations", json=observe
                                ).json()["items"][0]
                                deletion = confirmed(
                                    expected_revision=2, evidence_scope="unreferenced"
                                )
                                responses = list(
                                    pool.map(
                                        lambda _, victim=victim, deletion=deletion: client.request(
                                            "DELETE", f"/api/items/{victim['id']}", json=deletion
                                        ),
                                        range(16),
                                    )
                                )
                                assert all(r.status_code == 200 for r in responses)
                                assert sum(not r.json()["replayed"] for r in responses) == 1
                                assert move["location"] is None
                                assert client.post("/api/items", json=create).status_code == 409
                                assert (
                                    client.post(
                                        f"/api/items/{victim['id']}/observations", json=observe
                                    ).status_code
                                    == 409
                                )
                    # Malformed requests remain structured, data unchanged and server healthy.
                    for raw in (
                        b'{"query":"a","query":"b"}',
                        b'{"query":NaN}',
                        b"\xff",
                        b"[]",
                        b"[" * 1100 + b"]" * 1100,
                    ):
                        response = client.post(
                            "/api/recall", content=raw, headers={"Content-Type": "application/json"}
                        )
                        assert response.status_code == 422 and "error" in response.json()
                    assert client.get("/api/items").json()["total"] == 1
                    photo = item["current_observation"]["photo"]
                    stop()
                    start()
                    assert client.get("/api/items").status_code == 401
                    client.cookies.clear()
                    auth(client)
                    assert client.get(f"/api/items/{item['id']}").json() == item
                    assert client.get(photo["url"]).status_code == 200
                    assert client.get(draft["photo_url"]).status_code == 404
                    deletion = confirmed(expected_revision=1, evidence_scope="all_affected")
                    assert (
                        client.request(
                            "DELETE", f"/api/items/{item['id']}", json=deletion
                        ).status_code
                        == 200
                    )
                    assert client.get(photo["url"]).status_code == 404
                    assert (
                        client.post(f"/api/captures/{draft['id']}/commit", json=manual).status_code
                        == 409
                    )
                    assert client.get("/api/items").json()["total"] == 0
                    cases.append(
                        {
                            "profile": profile,
                            "startup_vision": status["state"],
                            "suggest_status": suggestion.status_code,
                            "manual_confirm_recall_restart_delete": "passed",
                            "active_worker_cancel_retry_races": 5 if profile == "valid" else 0,
                            "active_worker_discard_races": 5 if profile == "valid" else 0,
                            "parallel_create_delete_groups": 3 if profile == "valid" else 0,
                            "malformed_json_cases": 5,
                        }
                    )
            finally:
                stop()
                log.close()
            events = [json.loads(line) for line in audit.read_text().splitlines()]
            all_runtime.extend(e for e in events if e["phase"] == "backend_runtime")
            self_tests += sum(e["phase"] == "guard_self_test" for e in events)
            assert "Traceback" not in (scratch / "server.log").read_text()
        print(json.dumps(cases[-1]), flush=True)
    assert not all_runtime and self_tests == 8
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", PORT)) != 0
    report = {
        "passed": True,
        "profiles": cases,
        "server_pids": pids,
        "servers_stopped": True,
        "temporary_data_removed": True,
        "guard_self_tests": self_tests,
        "runtime_outbound_python_attempts": all_runtime,
        "network_scope": "Python-process socket audit only; native/UDP/OS-wide isolation unproven",
    }
    output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
