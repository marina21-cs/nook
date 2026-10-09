"""One current-code real NanoDet HTTP lifecycle under unchanged experiment guards."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/current-nanodet"
BASE = "http://127.0.0.1:18807"


def load_reviewed_sampler():
    # Reuse inspected internal guard code without running its archived main or writing there.
    source = ROOT / "benchmarks/smolvlm-reduced-smoke-2026-10-09/scripts/resources.py"
    namespace = {"__file__": str(source), "__name__": "reviewed_resource_sampler"}
    exec(compile(source.read_text(), str(source), "exec"), namespace)
    return namespace


def descendants(root_pid):
    parents = {}
    for folder in Path("/proc").glob("[0-9]*"):
        try:
            fields = (folder / "stat").read_text().rsplit(")", 1)[1].split()
            parents[int(folder.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
    selected = {root_pid}
    while True:
        more = {pid for pid, parent in parents.items() if parent in selected}
        if more <= selected:
            return sorted(selected)
        selected |= more


def run():
    OUT.mkdir(exist_ok=True)
    resources = load_reviewed_sampler()
    sample, violations = resources["sample"], resources["violations"]
    result = {
        "actual_inference_attempted": False,
        "actual_inference_completed": False,
        "calls": 0,
        "passed": False,
        "limits": resources["LIMITS"],
        "guard_provenance": "retained SmolVLM experiment policy; not manufacturer specification",
        "model_source_unchanged": True,
        "downloads": 0,
        "samples": [],
        "checks": [],
    }
    if (OUT / "result.json").exists():
        raise RuntimeError("Refusing to overwrite a completed attempt")
    previous = None
    for _ in range(3):
        previous = sample(previous)
        previous["stage"] = "preflight"
        previous["violations"] = violations(previous)
        result["samples"].append(previous)
        if previous["violations"]:
            result["blocked_before_start"] = previous["violations"]
            (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps({"blocked": previous["violations"], "reading": previous}, indent=2))
            return result
        time.sleep(1)
    fixture = ROOT / "tests/fixtures/vision/coffee.png"
    manifest = json.loads((fixture.parent / "manifest.json").read_text())[fixture.name]
    image = fixture.read_bytes()
    assert (
        len(image) == manifest["bytes"] and hashlib.sha256(image).hexdigest() == manifest["sha256"]
    )
    result["fixture"] = {
        "name": "coffee.png",
        "sha256": manifest["sha256"],
        "license": "CC0; Rachel Michetti courtesy of Pikolo Espresso Bar, scikit-image",
        "supported_target": "cup",
        "target_fixture_not_held_out": True,
    }
    done, stopped = threading.Event(), threading.Event()
    owned = set()
    monitor_error = []
    with tempfile.TemporaryDirectory(prefix="appbuilderss-real-nanodet-") as folder:
        scratch = Path(folder)
        audit = scratch / "audit.jsonl"
        env = dict(
            os.environ,
            APP_DATA_DIR=str(scratch / "data"),
            APP_PORT="18807",
            APP_VISION_DISABLED="0",
            APP_OFFLINE_AUDIT_LOG=str(audit),
        )
        for name in ("APP_TEXT_MODEL", "APP_VISION_MODEL", "APP_VISION_SHA256"):
            env.pop(name, None)
        log = (OUT / "server.log").open("wb")
        process = subprocess.Popen(
            [sys.executable, "-m", "scripts.offline_server"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        owned.add(process.pid)

        def stop_owned():
            stopped.set()
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

        def monitor():
            nonlocal previous
            counters = {}
            started = time.monotonic()
            try:
                while not done.is_set():
                    owned.update(descendants(process.pid))
                    previous = sample(previous, sorted(owned))
                    previous["stage"] = "server_and_one_call"
                    reasons = violations(previous)
                    previous["violations"] = reasons
                    result["samples"].append(previous)
                    with (OUT / "resources.jsonl").open("a") as file:
                        file.write(json.dumps(previous) + "\n")
                    for reason in set(counters) | set(reasons):
                        counters[reason] = counters.get(reason, 0) + 1 if reason in reasons else 0
                    immediate = set(reasons) & {
                        "cpu_temperature",
                        "low_available_memory",
                        "tree_memory_limit",
                    }
                    sustained = [reason for reason, count in counters.items() if count >= 3]
                    if immediate or sustained or time.monotonic() - started > 35:
                        result["monitor_stop"] = sorted(immediate | set(sustained)) or [
                            "whole_run_timeout"
                        ]
                        stop_owned()
                        return
                    done.wait(1)
            except Exception as error:
                monitor_error.append(type(error).__name__)
                result["monitor_stop"] = ["monitor_unavailable"]
                stop_owned()

        watcher = threading.Thread(target=monitor, daemon=True)
        watcher.start()
        try:
            with httpx.Client(base_url=BASE, trust_env=False, timeout=17) as client:
                for _ in range(60):
                    if stopped.is_set() or process.poll() is not None:
                        raise RuntimeError("Server stopped before request")
                    try:
                        if client.get("/api/status").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Readiness timeout")
                client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
                assert client.get("/api/status").json()["vision"]["available"] is True
                draft = client.post(
                    "/api/captures?source=import",
                    content=image,
                    headers={"Content-Type": "image/png"},
                )
                assert draft.status_code == 201
                result["actual_inference_attempted"] = True
                result["calls"] = 1
                start = time.monotonic()
                response = client.post(
                    f"/api/captures/{draft.json()['id']}/suggest", json={"request_id": str(uuid4())}
                )
                result["http_latency_ms"] = round((time.monotonic() - start) * 1000, 2)
                result["inference_http_status"] = response.status_code
                result["observed_response"] = response.json()
                assert response.status_code == 200, response.text
                observed = response.json()
                result["actual_inference_completed"] = observed["inference_used"]
                assert client.get("/api/items").json()["total"] == 0
                assert (
                    observed["identity_verified"] is False
                    and observed["location_verified"] is False
                )
                candidate = next(c for c in observed["candidates"] if c["category"] == "cup")
                result["checks"].append(
                    "real CPU detections, unsaved and unconfirmed, target cup observed"
                )
                confirmed = {
                    "confirmed": True,
                    "idempotency_key": str(uuid4()),
                    "location": "Synthetic evaluation shelf",
                    "make_current": True,
                    "rows": [
                        {
                            "identity": "new",
                            "personal_name": "evaluation ceramic cup",
                            "category": "cup",
                            "candidate_id": candidate["id"],
                            "region": candidate["region"],
                        }
                    ],
                }
                saved = client.post(f"/api/captures/{draft.json()['id']}/commit", json=confirmed)
                assert saved.status_code == 200
                item = saved.json()["items"][0]
                photo = item["current_observation"]["photo"]
                answer = client.post(
                    "/api/recall",
                    json={"query": "evaluation ceramic cup", "request_id": str(uuid4())},
                ).json()
                assert answer["kind"] == "found" and answer["items"] == [item]
                assert client.get(photo["url"]).status_code == 200
                assert photo["captured_at"] is None and item["live_location_verified"] is False
                result["confirmed_record"] = item
                result["recall"] = answer
                result["checks"].append(
                    "explicit confirmation saves exact user identity/location and dated imported photo evidence"
                )
                edited = client.patch(
                    f"/api/items/{item['id']}",
                    json={
                        "confirmed": True,
                        "idempotency_key": str(uuid4()),
                        "expected_revision": item["revision"],
                        "personal_name": "renamed evaluation cup",
                    },
                )
                assert edited.status_code == 200
                current = edited.json()["items"][0]
                assert (
                    current["current_observation"]["confirmed_at"]
                    == item["current_observation"]["confirmed_at"]
                )
                moved = client.post(
                    f"/api/items/{item['id']}/observations",
                    json={
                        "confirmed": True,
                        "idempotency_key": str(uuid4()),
                        "expected_revision": current["revision"],
                        "location": None,
                    },
                )
                assert moved.status_code == 200
                current = moved.json()["items"][0]
                unknown = client.post(
                    "/api/recall",
                    json={"query": "renamed evaluation cup", "request_id": str(uuid4())},
                ).json()
                assert unknown["kind"] == "unknown" and unknown["reason"] == "location_unknown"
                deleted = client.request(
                    "DELETE",
                    f"/api/items/{item['id']}",
                    json={
                        "confirmed": True,
                        "idempotency_key": str(uuid4()),
                        "expected_revision": current["revision"],
                        "evidence_scope": "unreferenced",
                    },
                )
                assert deleted.status_code == 200 and client.get(photo["url"]).status_code == 404
                assert client.get("/api/items").json()["total"] == 0
                result["checks"].append(
                    "metadata edit preserves time, unknown move stays unknown, delete removes item/photo"
                )
                result["passed"] = not stopped.is_set()
        except Exception as error:
            result["error"] = type(error).__name__
        finally:
            done.set()
            watcher.join(timeout=3)
            stop_owned()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
            log.close()
            events = (
                [json.loads(line) for line in audit.read_text().splitlines()]
                if audit.exists()
                else []
            )
            result["runtime_python_network_attempts"] = [
                event for event in events if event["phase"] == "backend_runtime"
            ]
            result["server_stopped"] = process.poll() is not None
            result["monitor_errors"] = monitor_error
            result["observed_owned_pids"] = sorted(owned)
            for _ in range(5):
                time.sleep(1)
                previous = sample(previous)
                previous["stage"] = "recovery_after_stop"
                previous["violations"] = violations(previous)
                result["samples"].append(previous)
            result["owned_processes_remaining"] = [
                pid for pid in owned if Path(f"/proc/{pid}").exists()
            ]
            if (
                result["runtime_python_network_attempts"]
                or result["owned_processes_remaining"]
                or monitor_error
            ):
                result["passed"] = False
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"samples", "confirmed_record", "recall"}
            },
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    run()
