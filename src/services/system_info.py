"""
System information gathering service.

Collects OS, device, RAM, and disk-usage info using only the Python
standard library so no new dependency (and no python-for-android recipe)
is required. Every probe is individually guarded: a failure yields None
for that field (or omits that disk) rather than raising.
"""

import os
import platform
import shutil
import socket
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class DiskInfo:
    mount: str
    label: str
    total: int
    used: int
    free: int


def format_bytes(n: Optional[int]) -> str:
    """Human-readable size. None -> '--'."""
    if n is None:
        return "--"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _parse_os_release(content: str) -> dict:
    """Parse /etc/os-release content into {'name', 'version'}."""
    if not content.strip():
        return {}
    values = {}
    for line in content.splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"')
    result = {}
    if values.get("NAME"):
        result["name"] = values["NAME"]
    version = values.get("VERSION") or values.get("VERSION_ID")
    if version:
        result["version"] = version
    return result


def _parse_cpu_model(content: str) -> Optional[str]:
    """First 'model name' (x86) or 'Model'/'Hardware' (ARM) from /proc/cpuinfo."""
    for line in content.splitlines():
        lower = line.lower()
        if lower.startswith("model name") or lower.startswith("hardware"):
            _, _, val = line.partition(":")
            if val.strip():
                return val.strip()
    return None


def _parse_meminfo(content: str) -> Tuple[Optional[int], Optional[int]]:
    """Return (total_bytes, used_bytes) from /proc/meminfo. used = total - available."""
    total_kb = avail_kb = None
    for line in content.splitlines():
        if line.startswith("MemTotal:"):
            total_kb = _first_int(line)
        elif line.startswith("MemAvailable:"):
            avail_kb = _first_int(line)
    total = total_kb * 1024 if total_kb is not None else None
    used = (
        (total_kb - avail_kb) * 1024
        if total_kb is not None and avail_kb is not None
        else None
    )
    return total, used


def _first_int(line: str) -> Optional[int]:
    for token in line.split():
        if token.isdigit():
            return int(token)
    return None


def _mount_point(path: str) -> str:
    """Walk up until the parent is on a different device (the mount root)."""
    path = os.path.abspath(path)
    try:
        dev = os.stat(path).st_dev
    except OSError:
        return path
    while path != os.path.dirname(path):
        parent = os.path.dirname(path)
        try:
            if os.stat(parent).st_dev != dev:
                break
        except OSError:
            break
        path = parent
    return path


def gather_static() -> dict:
    """Static fields: OS name/version, hostname, CPU model. Gathered once."""
    os_data = _parse_os_release(_read_file("/etc/os-release"))
    return {
        "os_name": os_data.get("name") or _safe(platform.system),
        "os_version": os_data.get("version") or _safe(platform.release),
        "hostname": _safe(socket.gethostname),
        "cpu_model": _parse_cpu_model(_read_file("/proc/cpuinfo"))
        or _safe(platform.processor),
    }


def gather_dynamic(roms_dir: str = "", work_dir: str = "") -> dict:
    """Dynamic fields: RAM usage and relevant disk usage. Re-callable."""
    ram_total, ram_used = _parse_meminfo(_read_file("/proc/meminfo"))

    candidates = [("Root", "/")]
    if roms_dir:
        candidates.append(("ROMs", roms_dir))
    if work_dir:
        candidates.append(("Work", work_dir))

    disks: List[DiskInfo] = []
    seen_mounts = set()
    for label, path in candidates:
        if not path or not os.path.exists(path):
            continue
        mount = _mount_point(path)
        if mount in seen_mounts:
            continue
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            continue
        seen_mounts.add(mount)
        disks.append(
            DiskInfo(
                mount=mount,
                label=label,
                total=usage.total,
                used=usage.used,
                free=usage.free,
            )
        )

    return {"ram_total": ram_total, "ram_used": ram_used, "disks": disks}


def _safe(fn):
    try:
        result = fn()
        return result if result else None
    except Exception:
        return None
