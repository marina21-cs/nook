"""Unprivileged resource sampling; stops only a worker created by this sweep."""

import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024**3
PAGE = os.sysconf("SC_PAGE_SIZE")
HZ = os.sysconf("SC_CLK_TCK")
LIMITS = dict(
    cpu_c=75,
    dimm_c=52,
    nvme_composite_c=70,
    rss_bytes=5 * GIB,
    available_bytes=2 * GIB,
    emergency_available_bytes=GIB,
    process_cpu_percent=250,
    swap_total_bytes_s=8 * 1024**2,
    sustained_samples=3,
    interval_s=1,
)


def utc():
    return dt.datetime.now(dt.UTC).isoformat()


def append(path, row):
    with Path(path).open("a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()


def sample(prev=None, pids=()):
    now = time.monotonic()
    mem = {
        line.split(":")[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
    }
    cpu = list(map(int, Path("/proc/stat").read_text().splitlines()[0].split()[1:9]))
    vm = dict(
        (k, int(v))
        for k, v in (line.split() for line in Path("/proc/vmstat").read_text().splitlines())
    )
    sensors = json.loads(subprocess.check_output(["sensors", "-j"], text=True, timeout=2))
    temps, fans = {}, {}
    for chip, features in sensors.items():
        for label, vals in features.items():
            if isinstance(vals, dict):
                for key, value in vals.items():
                    if key.startswith("temp") and key.endswith("_input"):
                        temps[chip + "/" + label] = value
                    if key.startswith("fan") and key.endswith("_input"):
                        fans[chip + "/" + label] = value
    if not any(k.startswith("k10temp") for k in temps):
        raise RuntimeError("k10temp CPU sensor unavailable")
    if not any(k.startswith("spd5118") for k in temps):
        raise RuntimeError("Previously monitored RAM sensors unavailable")
    if not any(k.startswith("nvme") and k.endswith("/Composite") for k in temps):
        raise RuntimeError("Previously monitored NVMe sensor unavailable")
    ticks, rss, hwm, sockets, processes = 0, 0, 0, [], []
    socket_observation_errors = []
    for pid in pids:
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            st = dict(
                line.split(":", 1)
                for line in Path(f"/proc/{pid}/status").read_text().splitlines()
                if ":" in line
            )
            r = int(st.get("VmRSS", "0").split()[0]) * 1024
            h = int(st.get("VmHWM", "0").split()[0]) * 1024
            ticks += int(fields[11]) + int(fields[12])
            rss += r
            hwm += h
            # Socket enumeration is supplementary evidence, not a resource gate.
            # /proc can deny fd access during process exit even while stat/status
            # remain readable. Preserve this gap explicitly; never report it as
            # zero sockets or as OS-wide network isolation.
            try:
                for fd in Path(f"/proc/{pid}/fd").iterdir():
                    try:
                        target = os.readlink(fd)
                        if target.startswith("socket:"):
                            sockets.append(dict(pid=pid, fd=fd.name, target=target))
                    except FileNotFoundError:
                        pass
            except PermissionError:
                socket_observation_errors.append(dict(pid=pid, reason="fd_access_denied"))
            processes.append(dict(pid=pid, rss_bytes=r, hwm_bytes=h, threads=int(st["Threads"])))
        except (FileNotFoundError, ProcessLookupError):
            pass
    r = dict(
        utc=utc(),
        monotonic=now,
        temperatures_c=temps,
        raw_sensors=sensors,
        fans_rpm=fans,
        available_bytes=mem["MemAvailable"],
        total_bytes=mem["MemTotal"],
        swap_used_bytes=mem["SwapTotal"] - mem["SwapFree"],
        tree_rss_bytes=rss,
        tree_hwm_bytes=hwm,
        processes=processes,
        socket_fds=sockets,
        socket_observation_errors=socket_observation_errors,
        _cpu=cpu,
        _swap=[vm["pswpin"], vm["pswpout"]],
        _ticks=ticks,
        _pids=list(pids),
    )
    if prev:
        elapsed = now - prev["monotonic"]
        delta = [a - b for a, b in zip(cpu, prev["_cpu"], strict=True)]
        r.update(
            host_cpu_percent=100 * (sum(delta) - delta[3] - delta[4]) / max(sum(delta), 1),
            swap_in_bytes_s=(r["_swap"][0] - prev["_swap"][0]) * PAGE / elapsed,
            swap_out_bytes_s=(r["_swap"][1] - prev["_swap"][1]) * PAGE / elapsed,
            process_cpu_percent=100 * max(0, ticks - prev["_ticks"]) / HZ / elapsed
            if list(pids) == prev["_pids"]
            else None,
        )
    return r


def violations(r):
    reasons = []
    for k, t in r["temperatures_c"].items():
        if k.startswith("k10temp") and t >= LIMITS["cpu_c"]:
            reasons.append("cpu_temperature")
        if k.startswith("spd5118") and t >= LIMITS["dimm_c"]:
            reasons.append("dimm_temperature")
        if k.startswith("nvme") and k.endswith("/Composite") and t >= LIMITS["nvme_composite_c"]:
            reasons.append("nvme_temperature")
    if r["available_bytes"] < LIMITS["available_bytes"]:
        reasons.append("low_available_memory")
    if r["tree_rss_bytes"] >= LIMITS["rss_bytes"]:
        reasons.append("tree_memory_limit")
    if (r.get("process_cpu_percent") or 0) > LIMITS["process_cpu_percent"]:
        reasons.append("cpu_thread_limit")
    if r.get("swap_out_bytes_s", 0) > 0:
        reasons.append("continuing_swap_out")
    if r.get("swap_in_bytes_s", 0) + r.get("swap_out_bytes_s", 0) > LIMITS["swap_total_bytes_s"]:
        reasons.append("swap_thrash")
    return sorted(set(reasons))
