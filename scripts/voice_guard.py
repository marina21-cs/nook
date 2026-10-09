"""One authorized bounded voice-test policy, using read-only unprivileged sensors.

This test-only policy allows DIMMs below 54 C (previous experiment guard: 52 C).
It never edits hardware/OS limits; exposed thresholds are not safety guarantees.
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
RESOURCE = runpy.run_path(str(ROOT / "scripts/resource_sampling.py"))


def sample(previous=None, pids=()):
    row = RESOURCE["sample"](previous, pids)
    row["raw_sensors"] = json.loads(
        subprocess.check_output(["sensors", "-j"], text=True, timeout=3)
    )
    return row


def violations(row, swap_streak):
    reasons = []
    dimms = []
    for chip, features in row["raw_sensors"].items():
        for _label, values in features.items():
            if not isinstance(values, dict):
                continue
            if any(key.endswith("_alarm") and value for key, value in values.items()):
                reasons.append("sensor_alarm")
            if chip.startswith("spd5118"):
                for key, value in values.items():
                    if key.endswith("_input"):
                        dimms.append(value)
                        prefix = key.removesuffix("_input")
                        if values.get(prefix + "_max", 0) < 55:
                            reasons.append("dimm_high_threshold_below_55")
                        if (
                            prefix + "_max_alarm" not in values
                            or prefix + "_crit_alarm" not in values
                        ):
                            reasons.append("dimm_alarm_status_missing")
                        if value >= 54:
                            reasons.append("dimm_54C_abort")
                    if key.endswith("_max") and value < 55:
                        reasons.append("dimm_high_threshold_below_55")
    if len(dimms) < 2:
        reasons.append("dimm_sensor_missing")
    # Retain the unrelated old guards, replacing only this test's DIMM threshold.
    for reason in RESOURCE["violations"](row):
        if reason not in {"dimm_temperature", "continuing_swap_out"}:
            reasons.append(reason)
    if swap_streak >= 3:
        reasons.append("sustained_swap_out")
    return sorted(set(reasons))


def tree(pid):
    found = [pid]
    for current in found:
        try:
            found.extend(
                int(x) for x in Path(f"/proc/{current}/task/{current}/children").read_text().split()
            )
        except FileNotFoundError:
            pass
    return found


def recovery_clear(baseline):
    """Require three measured zero-swap-out intervals after the initial sample."""
    return len(baseline) >= 4 and all(row.get("swap_out_bytes_s") == 0 for row in baseline[1:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.stage.replace("-", "").isalnum():
        raise SystemExit("Invalid stage")
    out = ROOT / "voice/evidence"
    out.mkdir(exist_ok=True)
    summary = out / f"{args.stage}-guard.json"
    if summary.exists():
        raise SystemExit("Refusing to replace prior stage evidence")
    logpath = out / f"{args.stage}-resources.jsonl"
    previous = None
    baseline = []
    streak = 0
    rows = []
    process = None
    reason = []
    exit_code = None

    def record(pids=()):
        nonlocal previous, streak
        previous = sample(previous, pids)
        streak = streak + 1 if previous.get("swap_out_bytes_s", 0) > 0 else 0
        previous["violations"] = violations(previous, streak)
        rows.append(previous)
        RESOURCE["append"](logpath, previous)
        return previous

    try:
        for _ in range(4):
            row = record()
            baseline.append(row)
            if row["violations"]:
                raise RuntimeError(",".join(row["violations"]))
            time.sleep(1)
        if not recovery_clear(baseline):
            raise RuntimeError("recovery_swap_out_not_consistently_zero")
        for sensor in baseline[-1]["temperatures_c"]:
            if (
                sensor.startswith("spd5118")
                and max(r["temperatures_c"][sensor] for r in baseline)
                - min(r["temperatures_c"][sensor] for r in baseline)
                > 1
            ):
                raise RuntimeError("unstable_dimm_baseline")
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            raise RuntimeError("No stage command")
        with (out / f"{args.stage}.log").open("w") as output:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={
                    **os.environ,
                    "OMP_NUM_THREADS": "2",
                    "MKL_NUM_THREADS": "2",
                    "OPENBLAS_NUM_THREADS": "2",
                },
            )
            start = time.monotonic()
            while process.poll() is None:
                row = record(tree(process.pid))
                if row["violations"]:
                    raise RuntimeError(",".join(row["violations"]))
                if time.monotonic() - start > args.timeout:
                    raise RuntimeError("stage_deadline")
                time.sleep(1)
            exit_code = process.returncode
    except Exception as exc:
        reason = [str(exc)]
    finally:
        if process is not None:
            # Kill only this stage's process group, including an orphaned test worker.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
        for _ in range(3):
            time.sleep(1)
            record()
        result = {
            "stage": args.stage,
            "utc": RESOURCE["utc"](),
            "policy": "one authorized smoke: DIMM <54 C; high threshold >=55; no alarms; CPU <75; available >=2 GiB; other previous guards retained",
            "command_exit_code": exit_code,
            "blocked_or_aborted": bool(reason),
            "reasons": reason,
            "samples": len(rows),
            "first": rows[0],
            "last": rows[-1],
            "max_dimm_c": max(
                t for r in rows for k, t in r["temperatures_c"].items() if k.startswith("spd5118")
            ),
            "max_cpu_c": max(
                t for r in rows for k, t in r["temperatures_c"].items() if k.startswith("k10temp")
            ),
            "max_tree_rss_bytes": max(r["tree_rss_bytes"] for r in rows),
            "min_available_bytes": min(r["available_bytes"] for r in rows),
            "max_swap_out_bytes_s": max(r.get("swap_out_bytes_s", 0) for r in rows),
        }
        summary.write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps({k: v for k, v in result.items() if k not in {"first", "last"}}), flush=True
        )
    return 1 if reason or exit_code != 0 else 0


if __name__ == "__main__":
    sys.exit(main())
