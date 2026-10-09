"""Synthetic artifact tests; no network requests or model inference."""

import hashlib

import pytest

from scripts import voice_download_single as download


def test_preserved_partial_ranges_only_request_gaps(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "VOICE", tmp_path)
    target = tmp_path / "artifacts/model.bin"
    target.parent.mkdir()
    target.with_suffix(".bin.part").write_bytes(b"ab")
    ranges = tmp_path / "artifacts/ranges/model.bin"
    ranges.mkdir(parents=True)
    (ranges / "4-7.part").write_bytes(b"ef")
    entry = {"path": "artifacts/model.bin", "bytes": 8}
    assert download.missing(entry) == [(2, 4), (6, 8)]
    assert target.with_suffix(".bin.part").read_bytes() == b"ab"
    assert (ranges / "4-7.part").read_bytes() == b"ef"


def test_overlap_fails_without_changing_retained_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "VOICE", tmp_path)
    ranges = tmp_path / "artifacts/ranges/model.bin"
    ranges.mkdir(parents=True)
    (ranges / "0-3.bin").write_bytes(b"abcd")
    (ranges / "2-5.bin").write_bytes(b"cdef")
    with pytest.raises(ValueError, match="Overlapping"):
        download.missing({"path": "artifacts/model.bin", "bytes": 6})
    assert (ranges / "0-3.bin").read_bytes() == b"abcd"


def test_existing_git_blob_is_reverified(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "VOICE", tmp_path)
    target = tmp_path / "config.json"
    target.write_bytes(b"good")
    entry = {
        "path": "config.json",
        "bytes": 4,
        "git_blob_sha1": hashlib.sha1(b"blob 4\0good").hexdigest(),
    }
    download.assemble(entry)
    target.write_bytes(b"evil")
    with pytest.raises(ValueError, match="Git blob"):
        download.assemble(entry)


def test_assembly_checks_full_hash_and_preserves_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "VOICE", tmp_path)
    ranges = tmp_path / "artifacts/ranges/model.bin"
    ranges.mkdir(parents=True)
    (ranges / "0-3.bin").write_bytes(b"abcd")
    entry = {"path": "artifacts/model.bin", "bytes": 4, "sha256": "bad"}
    with pytest.raises(ValueError, match="SHA256"):
        download.assemble(entry)
    assert not (tmp_path / entry["path"]).exists()
    entry["sha256"] = hashlib.sha256(b"abcd").hexdigest()
    download.assemble(entry)
    assert (tmp_path / entry["path"]).read_bytes() == b"abcd"
    assert (ranges / "0-3.bin").read_bytes() == b"abcd"
