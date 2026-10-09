"""Synthetic monitor-policy regression tests; no claim of hardware safety."""

from copy import deepcopy

import pytest

from scripts import software_guard, voice_guard


def row():
    sensor = {
        "temp1_input": 54.5,
        "temp1_max": 55.0,
        "temp1_crit": 85.0,
        "temp1_max_alarm": 0,
        "temp1_crit_alarm": 0,
    }
    return {
        "raw_sensors": {
            "spd5118-test-1": {"temp1": deepcopy(sensor)},
            "spd5118-test-2": {"temp1": deepcopy(sensor)},
        },
        "temperatures_c": {"k10temp/Tctl": 58.0, "nvme/Composite": 45.0},
        "available_bytes": 4 * 1024**3,
        "tree_rss_bytes": 100 * 1024**2,
        "process_cpu_percent": 100,
    }


def test_software_policy_is_separate_from_model_cutoffs():
    assert software_guard.violations(row(), 0, 0) == []


def test_active_alarm_always_stops():
    sample = row()
    sample["raw_sensors"]["spd5118-test-1"]["temp1"]["temp1_max_alarm"] = 1
    assert "hardware_alarm" in software_guard.violations(sample, 0, 0)


def test_high_must_be_sustained_but_critical_stops_immediately():
    sample = row()
    sensor = sample["raw_sensors"]["spd5118-test-1"]["temp1"]
    sensor["temp1_input"] = 55
    assert software_guard.violations(sample, 0, 1) == []
    assert "sustained_dimm_at_configured_high" in software_guard.violations(sample, 0, 3)
    sensor["temp1_input"] = 85
    assert "dimm_at_configured_critical" in software_guard.violations(sample, 0, 1)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("available_bytes", 1, "available_below_2GiB"),
        ("tree_rss_bytes", 2 * 1024**3, "software_tree_above_1point5GiB"),
        ("process_cpu_percent", 251, "software_tree_above_250percent_cpu"),
    ],
)
def test_software_resource_limits(field, value, reason):
    sample = row()
    sample[field] = value
    assert reason in software_guard.violations(sample, 0, 0)


def test_sustained_severe_swap_stops():
    assert "sustained_swap_above_8MiBps" in software_guard.violations(row(), 3, 0)


def test_alarm_evidence_is_not_consumed_by_a_second_sensor_read(monkeypatch):
    sample = row()
    sample["raw_sensors"]["spd5118-test-1"]["temp1"]["temp1_max_alarm"] = 1
    monkeypatch.setitem(voice_guard.RESOURCE, "sample", lambda previous, pids: sample)

    def fail(*args, **kwargs):
        raise AssertionError("Second read could consume a sticky alarm")

    monkeypatch.setattr(voice_guard.subprocess, "check_output", fail)
    result = voice_guard.sample()
    assert (
        result is sample
        and result["raw_sensors"]["spd5118-test-1"]["temp1"]["temp1_max_alarm"] == 1
    )


def test_fd_permission_gap_does_not_erase_resource_metrics(monkeypatch):
    import json
    import os
    from pathlib import Path

    from scripts import resource_sampling

    sensors = {
        "k10temp-test": {"Tctl": {"temp1_input": 50}},
        "spd5118-test": {"temp1": {"temp1_input": 50}},
        "nvme-test": {"Composite": {"temp1_input": 40}},
    }
    monkeypatch.setattr(
        resource_sampling.subprocess, "check_output", lambda *a, **kw: json.dumps(sensors)
    )
    original = Path.iterdir

    def denied(path):
        if str(path) == f"/proc/{os.getpid()}/fd":
            raise PermissionError("synthetic fd denial")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", denied)
    sampled = resource_sampling.sample(pids=[os.getpid()])
    assert sampled["tree_rss_bytes"] > 0
    assert sampled["processes"][0]["pid"] == os.getpid()
    assert sampled["socket_observation_errors"] == [
        {"pid": os.getpid(), "reason": "fd_access_denied"}
    ]
    assert sampled["temperatures_c"]["spd5118-test/temp1"] == 50
