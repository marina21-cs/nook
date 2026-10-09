"""Synthetic provisioning fixtures only: no download, pip install or model inference."""

import hashlib
import http.client
import io
import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts import voice_setup as setup


def manifest(payload=b"fixture"):
    return {
        "schema": 1,
        "target": "synthetic",
        "total_payload_bytes": len(payload),
        "files": [
            {
                "name": "setuptools",
                "kind": "package",
                "path": "packages/fixture.whl",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "url": "https://files.pythonhosted.org/fixture.whl",
            }
        ],
    }


class Response(io.BytesIO):
    status = 200
    headers = {}


def test_shipped_manifest_complete_and_pinned():
    data = setup.load_manifest()
    assert len(setup.selected(data, "package")) == 89
    assert len(setup.selected(data, "model")) == 15
    assert data["total_payload_bytes"] == 820069956
    torch = next(e for e in data["files"] if e.get("name") == "torch")
    assert torch["bytes"] == 184053363
    assert torch["sha256"] == "cb06175284673a581dd91fb1965662ae4ecaba6e5c357aa0ea7bb8b84b6b7eeb"


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "../outside.whl"),
        ("path", "/packages/a.whl"),
        ("path", None),
        ("path", "packages/../a.whl"),
        ("path", "packages\\a.whl"),
        ("bytes", True),
        ("sha256", None),
        ("sha256", "x"),
        ("url", "http://files.pythonhosted.org/a"),
        ("url", "https://files.pythonhosted.org.evil/a"),
        ("url", "https://user:secret@files.pythonhosted.org/a"),
        ("url", "https://files.pythonhosted.org/a?token=secret"),
    ],
)
def test_manifest_rejects_unsafe_values(tmp_path, field, value):
    data = manifest()
    data["files"][0][field] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        setup.load_manifest(path)


def test_redirect_does_not_allow_local_network():
    for url in ("http://127.0.0.1/a", "https://localhost/a", "https://evil.example/a"):
        with pytest.raises(ValueError):
            setup.validate_url(url, redirect=True)
    setup.validate_url("https://cdn-lfs.hf.co/file?signature=x", redirect=True)


def test_redirect_never_drains_unbounded_response_body():
    class NoBodyRead(io.BytesIO):
        def read(self, size=-1):
            raise AssertionError("Redirect body must not be consumed")

    stream = NoBodyRead(b"HTTP/1.1 302 Found\r\nContent-Length: 10\r\n\r\nnot needed")
    response = http.client.HTTPResponse(SimpleNamespace(makefile=lambda *args: stream))
    response.begin()
    request = setup.urllib.request.Request("https://files.pythonhosted.org/fixture.whl")
    request.timeout = 1
    handler = setup.SourceRedirects()
    expected = object()
    handler.parent = SimpleNamespace(open=lambda *args, **kwargs: expected)
    assert handler.http_error_302(
        request, response, 302, "Found", {"location": "https://files.pythonhosted.org/other.whl"}
    ) is expected
    assert stream.closed


def test_download_requires_explicit_budget_before_network(tmp_path):
    def forbidden(*args):
        raise AssertionError("network must not be attempted")

    for options in ({}, {"allow_network": True, "budget": 1}):
        with pytest.raises(ValueError):
            setup.download(tmp_path, manifest(), "all", opener=forbidden, **options)
    assert setup.inventory(tmp_path, manifest())["network_used"] is False
    assert not (tmp_path / "packages").exists()


def test_download_hashes_and_reuses_cache(tmp_path):
    calls = []

    def fake(url):
        calls.append(url)
        return Response(b"fixture")

    first = setup.download(tmp_path, manifest(), "all", allow_network=True, budget=7, opener=fake)
    second = setup.download(tmp_path, manifest(), "all", allow_network=True, budget=0, opener=fake)
    assert first["downloaded_bytes"] == 7 and second["verified_cached_files"] == 1
    assert len(calls) == 1
    assert setup.verify(tmp_path, manifest())["verified_files"] == 1


@pytest.mark.parametrize("payload", [b"wrong!!", b"short", b""])
def test_bad_download_removes_only_owned_partial(tmp_path, payload):
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("keep")
    with pytest.raises(ValueError):
        setup.download(
            tmp_path,
            manifest(),
            "all",
            allow_network=True,
            budget=7,
            opener=lambda url: Response(payload),
        )
    assert not list((tmp_path / "packages").iterdir())
    assert unrelated.read_text() == "keep"


def test_invalid_existing_file_and_symlink_preserved(tmp_path):
    path = tmp_path / "packages/fixture.whl"
    path.parent.mkdir()
    path.write_bytes(b"bad")
    with pytest.raises(ValueError, match="preserved"):
        setup.download(tmp_path, manifest(), "all", allow_network=True, budget=7)
    assert path.read_bytes() == b"bad"
    path.unlink()
    path.symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        setup.inventory(tmp_path, manifest())


def test_preexisting_partial_preserved(tmp_path):
    path = tmp_path / "packages/fixture.whl.part"
    path.parent.mkdir()
    path.write_bytes(b"inspect me")
    with pytest.raises(ValueError, match="Partial"):
        setup.download(tmp_path, manifest(), "all", allow_network=True, budget=7)
    assert path.read_bytes() == b"inspect me"


def test_mock_install_offline_pinned_and_final_path(tmp_path, monkeypatch):
    path = tmp_path / "packages/fixture.whl"
    path.parent.mkdir()
    path.write_bytes(b"fixture")
    commands, locks = [], []
    monkeypatch.setenv("PIP_INDEX_URL", "https://untrusted.example")
    monkeypatch.setenv("PYTHONPATH", "/untrusted")

    def fake_run(command, **kwargs):
        commands.append(command)
        assert kwargs["check"] and kwargs["timeout"] <= 300
        assert "PIP_INDEX_URL" not in kwargs["env"] and "PYTHONPATH" not in kwargs["env"]
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        if "-r" in command:
            from pathlib import Path

            locks.append(Path(command[-1]).read_text())
            for flag in ("--no-index", "--no-deps", "--no-build-isolation", "--require-hashes"):
                assert flag in command

    result = setup.install(tmp_path, manifest(), run=fake_run, platform_check=lambda: None)
    assert commands[0][-1] == str(tmp_path / "runtime")
    assert len(commands) == 4 and len(locks) == 2
    assert all("file://" in lock and "--hash=sha256:" in lock for lock in locks)
    assert not result["network_used"] and not result["models_loaded"]
    assert not (tmp_path / "runtime/.nook-setup-incomplete").exists()
    with pytest.raises(ValueError, match="already exists"):
        setup.install(tmp_path, manifest(), run=fake_run, platform_check=lambda: None)


def test_failed_mock_install_keeps_incomplete_marker(tmp_path):
    path = tmp_path / "packages/fixture.whl"
    path.parent.mkdir()
    path.write_bytes(b"fixture")

    def failure(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    with pytest.raises(subprocess.CalledProcessError):
        setup.install(tmp_path, manifest(), run=failure, platform_check=lambda: None)
    assert (tmp_path / "runtime/.nook-setup-incomplete").is_file()


@pytest.mark.parametrize(
    "status,headers",
    [
        (403, {}),
        (200, {"Content-Encoding": "gzip"}),
        (200, {"Content-Length": "8"}),
        (200, {"Content-Length": "invalid"}),
    ],
)
def test_response_errors_preserve_no_unverified_file(tmp_path, status, headers):
    response = Response(b"fixture")
    response.status, response.headers = status, headers
    with pytest.raises(ValueError):
        setup.download(
            tmp_path, manifest(), "all", allow_network=True, budget=7, opener=lambda url: response
        )
    assert not list((tmp_path / "packages").iterdir())


def test_network_failure_cleans_partial_and_releases_lock(tmp_path):
    def fail(url):
        raise TimeoutError("synthetic timeout")

    with pytest.raises(TimeoutError):
        setup.download(tmp_path, manifest(), "all", allow_network=True, budget=7, opener=fail)
    assert not list((tmp_path / "packages").iterdir())
    with setup.exclusive(tmp_path):
        with pytest.raises(BlockingIOError):
            with setup.exclusive(tmp_path):
                pytest.fail("second setup must not acquire lock")
