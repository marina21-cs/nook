"""Real loopback lifecycle acceptance; synthetic data, no model calls or downloads."""

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PORT = 18806
BASE = f"http://127.0.0.1:{PORT}"


def run(*, receipt_stress: bool = False) -> dict:
    checks: list[str] = []
    demo_responses = {}
    with tempfile.TemporaryDirectory(prefix="appbuilderss-phase-") as temporary:
        scratch = Path(temporary)
        env = dict(
            os.environ,
            APP_DATA_DIR=str(scratch / "data"),
            APP_PORT=str(PORT),
            APP_VISION_DISABLED="1",
            APP_OFFLINE_AUDIT_LOG=str(scratch / "audit.jsonl"),
        )
        env.pop("APP_TEXT_MODEL", None)
        process = None
        log = (scratch / "server.log").open("wb")

        def stop() -> None:
            nonlocal process
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                process = None

        def start() -> httpx.Client:
            nonlocal process
            process = subprocess.Popen(
                [sys.executable, "-m", "scripts.offline_server"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            client = httpx.Client(base_url=BASE, trust_env=False, timeout=5)
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("Temporary test server exited")
                try:
                    if client.get("/api/status").status_code == 200:
                        token = client.get("/api/session").json()["csrf_token"]
                        client.headers["X-CSRF-Token"] = token
                        return client
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            client.close()
            raise RuntimeError("Temporary test server not ready")

        def turn(client: httpx.Client, **fields) -> httpx.Response:
            return client.post(
                "/api/turns",
                json={
                    "request_id": str(uuid4()),
                    "utterance": "Nasaan yung blue keys ko?",
                    **fields,
                },
            )

        try:
            client = start()
            image = io.BytesIO()
            Image.new("RGB", (64, 48), "blue").save(image, "PNG")
            draft = client.post(
                "/api/captures", content=image.getvalue(), headers={"Content-Type": "image/png"}
            )
            assert draft.status_code == 201
            saved = client.post(
                f"/api/captures/{draft.json()['id']}/commit",
                json={
                    "confirmed": True,
                    "idempotency_key": str(uuid4()),
                    "location": "Desk drawer",
                    "make_current": True,
                    "rows": [{"identity": "new", "personal_name": "blue keys"}],
                },
            )
            assert saved.status_code == 200
            item = saved.json()["items"][0]
            before_files = sorted(str(path.relative_to(scratch)) for path in scratch.rglob("*"))
            generation = client.get("/api/status").json()["generation"]
            answer = turn(
                client,
                language="fil",
                render_speech=True,
                frame={
                    "data_base64": base64.b64encode(image.getvalue()).decode(),
                    "content_type": "image/png",
                },
            )
            assert answer.status_code == 200, answer.text
            result = answer.json()
            assert result["kind"] == "memory" and result["recall"]["items"][0] == item
            demo_responses["supported"] = {
                "kind": result["kind"],
                "reply_text": result["reply_text"],
                "stored_location": item["location"],
                "live_location_verified": False,
                "persisted_turn_input": False,
                "speech_status": result["speech"]["status"],
            }
            assert result["persisted"] is False and result["speech"]["status"] == "not_provisioned"
            assert client.get("/api/status").json()["generation"] == generation
            assert (
                sorted(str(path.relative_to(scratch)) for path in scratch.rglob("*"))
                == before_files
            )
            checks.append(
                "real typed/frame turn retains exact saved evidence; no input files or DB writes"
            )
            assert turn(client, confirmed=True).status_code == 422
            unsupported = turn(client, intent="visual_question").json()
            assert unsupported["kind"] == "unsupported"
            unknown = turn(client, utterance="red passport").json()
            assert unknown["kind"] == "unknown"
            demo_responses["unknown"] = {
                "kind": unknown["kind"],
                "reason": unknown["recall"]["reason"],
            }
            demo_responses["unsupported_visual_question"] = {"kind": unsupported["kind"]}
            request_id = str(uuid4())
            assert client.post(f"/api/requests/{request_id}/cancel").status_code == 200
            assert (
                client.post(
                    "/api/turns", json={"request_id": request_id, "utterance": "blue keys"}
                ).status_code
                == 409
            )
            checks.append(
                "confirmation bypass/unsupported visual question/pre-start cancellation rejected"
            )
            with ThreadPoolExecutor(max_workers=3) as pool:
                responses = list(pool.map(lambda _: turn(client), range(3)))
            assert all(response.status_code == 200 for response in responses)
            checks.append("three concurrent typed turns preserve memory")
            payload = {
                "confirmed": True,
                "expected_generation": generation,
                "dataset_label": "synthetic QA",
                "snapshot_complete": True,
                "element_count": 3,
                "coverage_bounds": {"south": -1, "north": 1, "west": -1, "east": 1},
                "elements": [
                    {"type": "node", "id": 1, "lat": 0, "lon": 0, "tags": {"amenity": "pharmacy"}},
                    {
                        "type": "way",
                        "id": 1,
                        "center": {"lat": 0, "lon": 0.01},
                        "tags": {"amenity": "pharmacy"},
                    },
                    {
                        "type": "relation",
                        "id": 1,
                        "center": {"lat": 0, "lon": 0.02},
                        "tags": {"amenity": "pharmacy"},
                    },
                ],
            }
            imported = client.put("/api/poi/cache", json=payload)
            assert imported.status_code == 200, imported.text
            assert imported.json()["record_count"] == 3
            bad = dict(payload, expected_generation=imported.json()["generation"], element_count=2)
            assert client.put("/api/poi/cache", json=bad).status_code == 422
            assert client.get("/api/poi/cache").json()["record_count"] == 3
            checks.append(
                "bounded POI import namespaces retained; malformed update preserves prior cache"
            )
            client.close()
            stop()
            client = start()
            assert client.get(f"/api/items/{item['id']}").json() == item
            assert client.get(item["current_observation"]["photo"]["url"]).status_code == 200
            assert client.get("/api/poi/cache").json()["record_count"] == 3
            query = {
                "confirmed": True,
                "location": {
                    "lat": 0,
                    "lon": 0,
                    "captured_at": datetime.now(UTC).isoformat(),
                    "accuracy_m": 20,
                },
                "category": "pharmacy",
            }
            places = client.post("/api/poi/nearest", json=query)
            assert places.status_code == 200, places.text
            assert [row["key"] for row in places.json()["results"]] == [
                "node/1",
                "way/1",
                "relation/1",
            ]
            assert (
                places.json()["coverage_complete"] is False
                and places.json()["stock_verified"] is False
            )
            checks.append(
                "restart preserves confirmed item/photo and cache; nearest cached straight-line ordering"
            )
            if receipt_stress:
                started = time.monotonic()
                epoch = client.get("/api/status").json()["write_epoch"]
                for index in range(10001):
                    edited = client.patch(
                        f"/api/items/{item['id']}",
                        json={
                            "confirmed": True,
                            "idempotency_key": str(uuid4()),
                            "write_epoch": epoch,
                            "expected_revision": item["revision"],
                            "distinguishing_note": f"bounded retention check {index}",
                        },
                    )
                    assert edited.status_code == 200, edited.text
                    item = edited.json()["items"][0]
                    epoch = edited.json()["write_epoch"]
                assert epoch >= 1
                deleted = client.request(
                    "DELETE",
                    f"/api/items/{item['id']}",
                    json={
                        "confirmed": True,
                        "idempotency_key": str(uuid4()),
                        "expected_revision": item["revision"],
                        "evidence_scope": "all_affected",
                    },
                )
                assert deleted.status_code == 200, deleted.text
                checks.append(
                    f"10001 real HTTP edits cross receipt limit; epoch rotates; item deletion succeeds ({time.monotonic() - started:.2f}s)"
                )
            generation = client.get("/api/status").json()["generation"]
            reset_body = {
                "confirmed": True,
                "idempotency_key": str(uuid4()),
                "confirmation": "DELETE ALL LOCAL DATA",
                "expected_generation": generation,
            }
            erased = client.request(
                "DELETE",
                "/api/data",
                json=reset_body,
            )
            assert erased.status_code == 200, erased.text
            assert client.get("/api/poi/cache").json()["record_count"] == 0
            assert client.get("/api/items").json()["total"] == 0
            assert client.get(item["current_observation"]["photo"]["url"]).status_code == 404
            assert list((scratch / "data" / "photos").iterdir()) == []
            assert b"synthetic QA" not in (scratch / "data" / "items.sqlite").read_bytes()
            checks.append(
                "delete-all removes POI and personal evidence; no dataset label residue in active DB"
            )
            new_body = {
                "confirmed": True,
                "idempotency_key": str(uuid4()),
                "write_epoch": erased.json()["write_epoch"],
                "personal_name": "post-reset record",
                "location": "new drawer",
            }
            fresh = client.post("/api/items", json=new_body)
            assert fresh.status_code == 201, fresh.text
            client.close()
            stop()
            client = start()
            retry = client.request("DELETE", "/api/data", json=reset_body)
            assert retry.status_code == 200 and retry.json()["replayed"]
            assert client.get("/api/items").json()["total"] == 1
            stale = dict(new_body, write_epoch=0, idempotency_key=str(uuid4()))
            assert client.post("/api/items", json=stale).status_code == 409
            assert client.post("/api/items", json=new_body).json()["replayed"]
            checks.append(
                "post-reset epoch permits new work; restart preserves epoch; old reset retry does not erase new data"
            )
            client.close()
        finally:
            stop()
            log.close()
        audit = scratch / "audit.jsonl"
        events = (
            [json.loads(line) for line in audit.read_text().splitlines()] if audit.exists() else []
        )
        runtime_events = [event for event in events if event["phase"] == "backend_runtime"]
        assert not runtime_events, "Unexpected Python backend network attempt"
        return {
            "passed": True,
            "demo_responses": demo_responses,
            "checks": checks,
            "inference_calls": 0,
            "python_backend_network_attempts": len(runtime_events),
            "servers_stopped": True,
            "scope": "loopback HTTP; Python audit guard, not OS-wide isolation",
        }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="Explicit evidence destination; default is stdout only"
    )
    parser.add_argument(
        "--receipt-stress",
        action="store_true",
        help="Run 10001 real HTTP edits across receipt rollover",
    )
    args = parser.parse_args(argv)
    result = run(receipt_stress=True) if args.receipt_stress else run()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
