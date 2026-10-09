"""Synthetic resource-policy boundary checks; no model or real sensor calls."""

import copy

import pytest

from scripts.voice_guard import recovery_clear, violations


def reading():
    sensor = {"temp1_input": 53.9, "temp1_max": 55.0, "temp1_max_alarm": 0, "temp1_crit_alarm": 0}
    return {
        "raw_sensors": {
            "spd5118-a": {"temp1": copy.deepcopy(sensor)},
            "spd5118-b": {"temp1": copy.deepcopy(sensor)},
        },
        "temperatures_c": {
            "spd5118-a/temp1": 53.9,
            "spd5118-b/temp1": 53.9,
            "k10temp/Tctl": 74.9,
            "nvme/Composite": 69.9,
        },
        "available_bytes": 2 * 1024**3,
        "tree_rss_bytes": 0,
        "process_cpu_percent": 0,
        "swap_in_bytes_s": 0,
        "swap_out_bytes_s": 0,
    }


def test_narrow_54_policy_preserves_unrelated_guards():
    assert violations(reading(), 0) == []


@pytest.mark.parametrize(
    "value,key,reason",
    [
        (54, "temp1_input", "dimm_54C_abort"),
        (54.9, "temp1_max", "dimm_high_threshold_below_55"),
        (1, "temp1_max_alarm", "sensor_alarm"),
        (1, "temp1_crit_alarm", "sensor_alarm"),
    ],
)
def test_dimm_limits_and_alarms(value, key, reason):
    row = reading()
    row["raw_sensors"]["spd5118-a"]["temp1"][key] = value
    assert reason in violations(row, 0)


def test_missing_limits_or_alarm_status_fail_closed():
    row = reading()
    row["raw_sensors"]["spd5118-a"]["temp1"].pop("temp1_max")
    assert "dimm_high_threshold_below_55" in violations(row, 0)
    row = reading()
    row["raw_sensors"]["spd5118-a"]["temp1"].pop("temp1_max_alarm")
    assert "dimm_alarm_status_missing" in violations(row, 0)


def test_swap_out_sustained_three_samples():
    row = reading()
    row["swap_out_bytes_s"] = 1
    assert "sustained_swap_out" not in violations(row, 2)
    assert "sustained_swap_out" in violations(row, 3)
    row["swap_in_bytes_s"] = 9 * 1024**2
    assert "swap_thrash" in violations(row, 1)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("available_bytes", 2 * 1024**3 - 1, "low_available_memory"),
        ("tree_rss_bytes", 5 * 1024**3, "tree_memory_limit"),
        ("process_cpu_percent", 251, "cpu_thread_limit"),
    ],
)
def test_unrelated_memory_cpu_guards(field, value, reason):
    row = reading()
    row[field] = value
    assert reason in violations(row, 0)


def test_cpu_temperature_guard():
    row = reading()
    row["temperatures_c"]["k10temp/Tctl"] = 75
    assert "cpu_temperature" in violations(row, 0)


def test_recovery_requires_three_measured_zero_intervals():
    assert recovery_clear([{}, reading(), reading(), reading()])
    assert not recovery_clear([{}, reading(), reading()])
    assert not recovery_clear([{}, reading(), {}, reading()])
    swapped = reading()
    swapped["swap_out_bytes_s"] = 1
    assert not recovery_clear([{}, swapped, reading(), reading()])
