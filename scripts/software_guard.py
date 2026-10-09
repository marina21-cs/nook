"""Low-resource software tests: no models; respects hardware alarms/configured limits.

User-authorized reassessment, 2026-10-09: do not apply the model experiment's
52/54 C cutoffs to all software tests. Configured sensor limits are stop signals,
not manufacturer operating specifications. Model worker guards remain unchanged.
"""

import argparse
import json
import os
import runpy
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = runpy.run_path(str(ROOT / "scripts/voice_guard.py"))


def violations(row, severe_swap_samples, high_samples):
    reasons = []
    dimms = 0
    for chip, features in row["raw_sensors"].items():
        for values in features.values():
            if not isinstance(values, dict):
                continue
            if any(k.endswith("_alarm") and v for k, v in values.items()):
                reasons.append("hardware_alarm")
            if chip.startswith("spd5118"):
                for k, v in values.items():
                    if k.endswith("_input"):
                        dimms += 1
                        prefix = k.removesuffix("_input")
                        high = values.get(prefix + "_max")
                        critical = values.get(prefix + "_crit")
                        if high is None or critical is None or prefix + "_max_alarm" not in values:
                            reasons.append("dimm_threshold_or_alarm_missing")
                        elif v >= critical:
                            reasons.append("dimm_at_configured_critical")
                        elif v >= high and high_samples >= 3:
                            reasons.append("sustained_dimm_at_configured_high")
    if dimms < 2:
        reasons.append("missing_dimm_sensor")
    for key, value in row["temperatures_c"].items():
        if key.startswith("k10temp") and value >= 75:
            reasons.append("cpu_75C_experiment_stop")
        if key.startswith("nvme") and key.endswith("/Composite") and value >= 70:
            reasons.append("nvme_70C_experiment_stop")
    if row["available_bytes"] < 2 * 1024**3:
        reasons.append("available_below_2GiB")
    if row["tree_rss_bytes"] > 1536 * 1024**2:
        reasons.append("software_tree_above_1point5GiB")
    if (row.get("process_cpu_percent") or 0) > 250:
        reasons.append("software_tree_above_250percent_cpu")
    if severe_swap_samples >= 3:
        reasons.append("sustained_swap_above_8MiBps")
    return sorted(set(reasons))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.stage.replace("-", "").isalnum():
        raise SystemExit("Invalid stage")
    out = ROOT / "deliverables/nook-ui-alignment"
    out.mkdir(exist_ok=True)
    report = out / (args.stage + "-guard.json")
    log = out / (args.stage + "-resources.jsonl")
    if report.exists() or log.exists():
        raise SystemExit("Use a new evidence stage name")
    rows = []
    previous = None
    streak = 0
    high_streak = 0
    process = None
    reason = []
    code = None

    def record(pids=()):
        nonlocal previous, streak, high_streak
        previous = G["sample"](previous, pids)
        severe = (
            previous.get("swap_in_bytes_s", 0) + previous.get("swap_out_bytes_s", 0) > 8 * 1024**2
        )
        streak = streak + 1 if severe else 0
        high = any(
            values.get("temp1_input", float("-inf")) >= values.get("temp1_max", float("inf"))
            for chip, features in previous["raw_sensors"].items()
            if chip.startswith("spd5118")
            for values in features.values()
            if isinstance(values, dict)
        )
        high_streak = high_streak + 1 if high else 0
        previous["violations"] = violations(previous, streak, high_streak)
        rows.append(previous)
        G["RESOURCE"]["append"](log, previous)
        return previous

    try:
        for _ in range(4):
            row = record()
            if row["violations"]:
                raise RuntimeError(",".join(row["violations"]))
            time.sleep(1)
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            raise RuntimeError("Missing command")
        with (out / (args.stage + ".log")).open("w") as output:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={
                    **os.environ,
                    "APP_VOICE_ENABLED": "0",
                    "APP_VISION_DISABLED": "1",
                    "OMP_NUM_THREADS": "1",
                    "OPENBLAS_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                },
            )
            start = time.monotonic()
            while process.poll() is None:
                row = record(G["tree"](process.pid))
                if row["violations"]:
                    raise RuntimeError(",".join(row["violations"]))
                if time.monotonic() - start > args.timeout:
                    raise RuntimeError("stage_deadline")
                time.sleep(1)
            code = process.returncode
    except Exception as exc:
        reason = [str(exc)]
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
        result = {
            "stage": args.stage,
            "utc": G["RESOURCE"]["utc"](),
            "policy": "software-only; no models; active alarms/critical stop; configured DIMM high for three samples stops; CPU<75C; NVMe<70C; available>=2GiB; tree<=1.5GiB; <=250% CPU; sustained combined swap<=8MiB/s",
            "command_started": process is not None,
            "command_exit_code": code,
            "blocked_or_aborted": bool(reason),
            "reasons": reason,
            "samples": len(rows),
            "max_dimm_c": max(
                v
                for row in rows
                for k, v in row["temperatures_c"].items()
                if k.startswith("spd5118")
            ),
            "max_tree_rss_bytes": max(row["tree_rss_bytes"] for row in rows),
            "min_available_bytes": min(row["available_bytes"] for row in rows),
            "first": rows[0],
            "last": rows[-1],
        }
        report.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k not in {"first", "last"}}))
    return int(bool(reason) or code != 0)


if __name__ == "__main__":
    sys.exit(main())
