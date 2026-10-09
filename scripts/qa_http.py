"""Independent real-HTTP adversarial backend acceptance, temporary synthetic records only."""

import io
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PORT = 18791
BASE = f"http://127.0.0.1:{PORT}"


def run():
    checks = []
    server = None
    pids = []
    with tempfile.TemporaryDirectory(prefix="appbuilderhck-independent-qa-") as folder:
        scratch = Path(folder)
        audit = scratch / "audit.jsonl"
        env = dict(
            os.environ,
            APP_DATA_DIR=str(scratch / "data"),
            APP_PORT=str(PORT),
            APP_OFFLINE_AUDIT_LOG=str(audit),
            APP_VISION_DISABLED="0",
            PYTHONDONTWRITEBYTECODE="1",
        )
        for key in ("APP_TEXT_MODEL", "APP_VISION_MODEL", "APP_VISION_SHA256"):
            env.pop(key, None)
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

        def start():
            nonlocal server
            server = subprocess.Popen(
                [sys.executable, "-m", "scripts.offline_server"],
                env=env,
                cwd=ROOT,
                stdout=log,
                stderr=log,
            )
            pids.append(server.pid)
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("QA server exited")
                try:
                    with httpx.Client(base_url=BASE, trust_env=False, timeout=1) as probe:
                        if probe.get("/api/status").status_code == 200:
                            return
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            raise RuntimeError("QA server readiness timed out")

        def record(text):
            checks.append(text)

        def confirmed(**fields):
            return {"confirmed": True, "idempotency_key": str(uuid4()), **fields}

        def reqid(query):
            return {"query": query, "request_id": str(uuid4())}

        def auth(client):
            response = client.get("/api/session")
            assert response.status_code == 200
            client.headers["X-CSRF-Token"] = response.json()["csrf_token"]

        def raw_response(headers):
            with socket.create_connection(("127.0.0.1", PORT), timeout=3) as conn:
                conn.sendall(
                    b"POST /api/recall HTTP/1.1\r\n"
                    + headers
                    + b"Content-Length: 2\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{}"
                )
                response = bytearray()
                while data := conn.recv(65536):
                    response.extend(data)
                return bytes(response)

        try:
            start()
            with httpx.Client(base_url=BASE, trust_env=False, timeout=30) as client:
                assert client.get("/api/items").status_code == 401
                auth(client)
                cookie = client.cookies.get("app_session")
                assert (
                    client.post(
                        "/api/recall", json=reqid("QA"), headers={"X-CSRF-Token": "wrong"}
                    ).status_code
                    == 403
                )
                for origin in ("null", "http://127.0.0.1:18792", "https://example.invalid"):
                    assert client.get("/api/items", headers={"Origin": origin}).status_code == 403
                assert (
                    client.get(
                        "/api/items",
                        headers={
                            "Host": "example.invalid",
                            "X-Forwarded-Host": f"127.0.0.1:{PORT}",
                        },
                    ).status_code
                    == 403
                )
                assert (
                    client.get("/api/session", headers={"Sec-Fetch-Site": "same-site"}).status_code
                    == 403
                )
                header = f"Host: 127.0.0.1:{PORT}\r\nCookie: app_session={cookie}\r\n".encode()
                assert (
                    b" 403 "
                    in raw_response(header + b"X-CSRF-Token: \xff\r\n").split(b"\r\n", 1)[0]
                )
                assert (
                    b" 400 "
                    in raw_response(
                        header
                        + b"Origin: http://127.0.0.1:18791\r\nOrigin: https://example.invalid\r\n"
                    ).split(b"\r\n", 1)[0]
                )
                record(
                    "actual HTTP session/CSRF, origin/Host/forwarded boundaries; duplicate Origin and non-ASCII CSRF denied"
                )

                for path in (
                    "/api/photos/%2e%2e%2fitems.sqlite",
                    "/api/photos/%2Fetc%2Fpasswd",
                    "/api/captures/not-a-uuid/photo",
                ):
                    response = client.get(path)
                    assert response.status_code in (404, 422) and "root:" not in response.text
                for body, media, status in (
                    (b"<svg/>", "image/svg+xml", 415),
                    (b"broken", "image/png", 422),
                    (b"{}", "text/plain", 415),
                ):
                    path = "/api/captures" if media.startswith("image/") else "/api/recall"
                    assert (
                        client.post(path, content=body, headers={"Content-Type": media}).status_code
                        == status
                    )
                png = io.BytesIO()
                Image.new("RGB", (72, 54), "purple").save(png, "PNG")
                assert (
                    client.post(
                        "/api/captures",
                        content=png.getvalue(),
                        headers={"Content-Type": "image/jpeg"},
                    ).status_code
                    == 415
                )
                assert (
                    client.post(
                        "/api/captures",
                        content=iter([b"x" * (6 * 1024 * 1024), b"y" * (5 * 1024 * 1024)]),
                        headers={"Content-Type": "image/png"},
                    ).status_code
                    == 413
                )
                # Patch only the tiny PNG IHDR; do not allocate/decode an enormous image.
                patched = bytearray(png.getvalue())
                patched[16:24] = struct.pack(">II", 100_000, 100_000)
                patched[29:33] = struct.pack(">I", zlib.crc32(patched[12:29]))
                assert client.post(
                    "/api/captures", content=bytes(patched), headers={"Content-Type": "image/png"}
                ).status_code in (413, 422)
                assert (
                    client.post(
                        "/api/recall",
                        content="[" * 1100 + "]" * 1100,
                        headers={"Content-Type": "application/json"},
                    ).status_code
                    == 422
                )
                assert client.get("/api/items").json()["total"] == 0
                record(
                    "real chunked upload byte cap; tiny image decode-bomb header; malformed/types/JSON/traversal rejected without a record"
                )

                draft = client.post(
                    "/api/captures?source=import",
                    content=(ROOT / "tests/fixtures/vision/coffee.png").read_bytes(),
                    headers={"Content-Type": "image/png"},
                ).json()
                suggestion = client.post(
                    f"/api/captures/{draft['id']}/suggest", json={"request_id": str(uuid4())}
                )
                assert suggestion.status_code == 200
                candidate = next(
                    c for c in suggestion.json()["candidates"] if c["category"] == "cup"
                )
                assert client.post("/api/recall", json=reqid("cup")).json()["kind"] == "unknown"
                body = confirmed(
                    location="QA confirmed cabinet",
                    make_current=True,
                    rows=[
                        {
                            "identity": "new",
                            "personal_name": "QA purple keepsake",
                            "category": "reviewed keepsake",
                            "candidate_id": candidate["id"],
                            "region": candidate["region"],
                        }
                    ],
                )
                for confirmation in (False, 1, "true", None):
                    assert (
                        client.post(
                            f"/api/captures/{draft['id']}/commit",
                            json={**body, "confirmed": confirmation},
                        ).status_code
                        == 422
                    )
                item = client.post(f"/api/captures/{draft['id']}/commit", json=body).json()[
                    "items"
                ][0]
                assert item["personal_name"] == "QA purple keepsake"
                assert item["current_observation"]["candidate_provenance"]["category"] == "cup"
                assert (
                    item["category"] == "reviewed keepsake"
                    and item["freshness"] == "unknown_photo_time"
                )
                photo = item["current_observation"]["photo"]
                assert client.post(f"/api/captures/{draft['id']}/commit", json=body).json()[
                    "replayed"
                ]
                response = client.get(photo["url"])
                assert (
                    response.status_code == 200 and response.headers["cache-control"] == "no-store"
                )
                assert response.headers["x-content-type-options"] == "nosniff"
                assert (
                    client.post("/api/recall", json=reqid(item["personal_name"])).json()["items"][
                        0
                    ]["location"]
                    == body["location"]
                )
                record(
                    "fresh real CPU detection is unsaved; mandatory literal confirmation; reviewed identity/category separate from candidate; grounded photo/location recall"
                )

                dup = client.post(
                    "/api/items",
                    json=confirmed(personal_name=item["personal_name"], location="QA other drawer"),
                ).json()["items"][0]
                ambiguous = client.post("/api/recall", json=reqid(item["personal_name"])).json()
                assert ambiguous["kind"] == "clarify" and ambiguous["total"] == 2
                deletion = confirmed(
                    expected_revision=dup["revision"], evidence_scope="unreferenced"
                )
                assert (
                    client.request("DELETE", f"/api/items/{dup['id']}", json=deletion).status_code
                    == 200
                )
                new_draft = client.post(
                    "/api/captures", content=png.getvalue(), headers={"Content-Type": "image/png"}
                ).json()
                assert client.request("DELETE", f"/api/items/{dup['id']}", json=deletion).json()[
                    "replayed"
                ]
                assert client.get(new_draft["photo_url"]).status_code == 200
                stop_id = str(uuid4())
                assert client.post(f"/api/requests/{stop_id}/cancel").status_code == 200
                assert (
                    client.post(
                        f"/api/captures/{new_draft['id']}/suggest", json={"request_id": stop_id}
                    ).status_code
                    == 409
                )
                assert client.delete(f"/api/captures/{new_draft['id']}").status_code == 200
                assert client.get(new_draft["photo_url"]).status_code == 404
                record(
                    "duplicate identities clarify; deletion retry preserves a new draft; pre-cancelled inference rejected; discard removes bytes"
                )

                observation = confirmed(expected_revision=item["revision"], location=None)
                item = client.post(
                    f"/api/items/{item['id']}/observations", json=observation
                ).json()["items"][0]
                answer = client.post("/api/recall", json=reqid(item["personal_name"])).json()
                assert answer["kind"] == "unknown" and answer["items"][0]["location"] is None
                assert (
                    item["current_observation"]["photo"] is None
                    and item["observations"][1]["photo"]["id"] == photo["id"]
                )
                assert (
                    client.post(
                        f"/api/items/{item['id']}/observations",
                        json=confirmed(expected_revision=1, location="obsolete"),
                    ).status_code
                    == 409
                )
                assert client.get(photo["url"]).status_code == 200
                record(
                    "move to unknown never substitutes historical photo/location; stale editor rejected"
                )

                manual_body = confirmed(personal_name="QA retry race object", location="QA drawer")
                with ThreadPoolExecutor(max_workers=6) as pool:
                    responses = list(
                        pool.map(lambda _: client.post("/api/items", json=manual_body), range(12))
                    )
                assert (
                    all(r.status_code == 201 for r in responses)
                    and sum(not r.json()["replayed"] for r in responses) == 1
                )
                retry_item = responses[0].json()["items"][0]
                assert (
                    client.request(
                        "DELETE",
                        f"/api/items/{retry_item['id']}",
                        json=confirmed(expected_revision=1, evidence_scope="unreferenced"),
                    ).status_code
                    == 200
                )
                assert client.post("/api/items", json=manual_body).status_code == 409
                record(
                    "12 parallel actual HTTP creates save once; late create retry after deletion cannot resurrect"
                )
                old_cookie = client.cookies.get("app_session")
                stop()
                start()
                assert client.get("/api/items").status_code == 401
                client.cookies.clear()
                auth(client)
                assert old_cookie != client.cookies.get("app_session")
                assert client.get(f"/api/items/{item['id']}").json() == item
                assert client.get(photo["url"]).status_code == 200
                assert client.post("/api/items", json=manual_body).status_code == 409
                assert client.get(new_draft["photo_url"]).status_code == 404
                record(
                    "actual process restart persists confirmed history/photo and retry tombstones; old session and drafts invalid"
                )

                deletion = confirmed(
                    expected_revision=item["revision"], evidence_scope="all_affected"
                )
                assert (
                    client.request("DELETE", f"/api/items/{item['id']}", json=deletion).status_code
                    == 200
                )
                assert client.get(photo["url"]).status_code == 404
                assert (
                    client.post("/api/recall", json=reqid(item["personal_name"])).json()["items"]
                    == []
                )
                survivor_body = confirmed(personal_name="QA delete all probe", location=None)
                client.post("/api/items", json=survivor_body).raise_for_status()
                generation = client.get("/api/items").json()["generation"]
                assert (
                    client.request(
                        "DELETE",
                        "/api/data",
                        json=confirmed(
                            confirmation="DELETE ALL LOCAL DATA", expected_generation=generation
                        ),
                    ).status_code
                    == 200
                )
                assert client.post("/api/items", json=survivor_body).status_code == 409
                assert client.get("/api/items").json()["total"] == 0
                record(
                    "deleted photos/recall inaccessible; delete-all late create retry cannot resurrect"
                )
        finally:
            stop()
            log.close()
        events = [json.loads(line) for line in audit.read_text().splitlines()]
        runtime = [e for e in events if e["phase"] == "backend_runtime"]
        assert not runtime
        assert len(events) == 2
        log_text = (scratch / "server.log").read_text()
        assert "Traceback" not in log_text and "ERROR" not in log_text
        (ROOT / "docs/qa-independent-http.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "address": BASE,
                    "checks": checks,
                    "server_pids": pids,
                    "server_remains_running": False,
                    "data_removed_on_exit": True,
                    "offline_guard_self_tests": len(events),
                    "runtime_outbound_python_attempts": runtime,
                    "network_scope": "Process Python audit only; no native syscall trace or physical WAN/LAN isolation",
                    "model_threshold_changed": False,
                },
                indent=2,
            )
            + "\n"
        )
    print(
        f"Independent HTTP QA: {len(checks)} check groups passed; servers stopped; temporary data removed",
        flush=True,
    )


if __name__ == "__main__":
    run()
