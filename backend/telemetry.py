from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - requirements.txt installs it in production.
    psutil = None  # type: ignore[assignment]


MIB = 1024 * 1024
_GPU_CACHE_TTL_SECONDS = 0.85
_gpu_cache_lock = threading.Lock()
_gpu_cache_at = 0.0
_gpu_cache: dict[str, Any] | None = None


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _finite_limit(value: str) -> int | None:
    if not value or value == "max":
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if 0 < parsed < (1 << 60) else None


def cpu_capacity_cores() -> float:
    """Return usable cores, respecting affinity and cgroup v1/v2 CPU quotas."""
    host_count = max(1, os.cpu_count() or 1)
    affinity_count = host_count
    if psutil is not None:
        try:
            affinity_count = max(1, len(psutil.Process().cpu_affinity()))
        except (AttributeError, OSError, psutil.Error):
            pass

    quota_cores: float | None = None
    cpu_max = _read_text("/sys/fs/cgroup/cpu.max").split()
    if len(cpu_max) == 2 and cpu_max[0] != "max":
        try:
            quota_cores = float(cpu_max[0]) / max(1.0, float(cpu_max[1]))
        except ValueError:
            pass
    if quota_cores is None:
        quota = _finite_limit(_read_text("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"))
        period = _finite_limit(_read_text("/sys/fs/cgroup/cpu/cpu.cfs_period_us"))
        if quota and period:
            quota_cores = quota / period

    capacity = float(min(host_count, affinity_count))
    if quota_cores is not None:
        capacity = min(capacity, quota_cores)
    return max(0.1, round(capacity, 2))


def memory_capacity_bytes() -> tuple[int, int]:
    """Return used/total memory for the active cgroup when it is constrained."""
    if psutil is None:
        return 0, 0
    virtual = psutil.virtual_memory()
    host_used = int(virtual.total - virtual.available)
    host_total = int(virtual.total)

    cgroup_max = _finite_limit(_read_text("/sys/fs/cgroup/memory.max"))
    cgroup_current = _finite_limit(_read_text("/sys/fs/cgroup/memory.current"))
    if cgroup_max is None:
        cgroup_max = _finite_limit(_read_text("/sys/fs/cgroup/memory/memory.limit_in_bytes"))
        cgroup_current = _finite_limit(_read_text("/sys/fs/cgroup/memory/memory.usage_in_bytes"))
    if cgroup_max and cgroup_current is not None and cgroup_max < host_total:
        return min(cgroup_current, cgroup_max), cgroup_max
    return host_used, host_total


def _csv_rows(output: str) -> list[list[str]]:
    return [
        [cell.strip() for cell in row]
        for row in csv.reader(io.StringIO(output))
        if row
    ]


def _number(value: str) -> float | None:
    cleaned = value.strip().casefold()
    if not cleaned or cleaned in {"n/a", "[not supported]", "not supported"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _query_nvidia() -> dict[str, Any]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {
            "available": False,
            "provider": None,
            "reason": (
                "Runtime NVIDIA belum diteruskan ke container; "
                "jalankan scripts/setup-nvidia-container-runtime.sh di host"
            ),
            "devices": [],
            "process_memory": {},
        }

    fields = (
        "uuid,index,name,utilization.gpu,utilization.memory,memory.used,memory.total,"
        "temperature.gpu,power.draw,driver_version"
    )
    try:
        device_result = subprocess.run(
            [binary, f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "provider": "nvidia-smi",
            "reason": f"query GPU gagal: {exc}",
            "devices": [],
            "process_memory": {},
        }
    if device_result.returncode != 0:
        reason = (device_result.stderr or device_result.stdout).strip().splitlines()
        return {
            "available": False,
            "provider": "nvidia-smi",
            "reason": (reason[-1] if reason else "GPU NVIDIA tidak terlihat")[:160],
            "devices": [],
            "process_memory": {},
        }

    devices: list[dict[str, Any]] = []
    for row in _csv_rows(device_result.stdout):
        if len(row) < 10:
            continue
        memory_used = _number(row[5])
        memory_total = _number(row[6])
        devices.append(
            {
                "uuid": row[0],
                "index": int(_number(row[1]) or 0),
                "name": row[2],
                "utilization_percent": _number(row[3]),
                "memory_utilization_percent": _number(row[4]),
                "memory_used_mb": memory_used,
                "memory_total_mb": memory_total,
                "memory_percent": round((memory_used or 0) / memory_total * 100, 1) if memory_total else None,
                "temperature_c": _number(row[7]),
                "power_w": _number(row[8]),
                "driver_version": row[9],
            }
        )

    process_memory: dict[int, dict[str, Any]] = {}
    try:
        process_result = subprocess.run(
            [
                binary,
                "--query-compute-apps=gpu_uuid,pid,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=1.2,
            check=False,
        )
        if process_result.returncode == 0:
            for row in _csv_rows(process_result.stdout):
                if len(row) < 3:
                    continue
                pid_value = _number(row[1])
                if pid_value is None:
                    continue
                process_memory[int(pid_value)] = {
                    "uuid": row[0],
                    "memory_mb": _number(row[2]) or 0.0,
                }
    except (OSError, subprocess.TimeoutExpired):
        pass

    return {
        "available": bool(devices),
        "provider": "nvidia-smi",
        "reason": None if devices else "Tidak ada GPU NVIDIA yang terdeteksi",
        "devices": devices,
        "process_memory": process_memory,
    }


def _query_linux_drm() -> dict[str, Any]:
    vendor_names = {"0x8086": "Intel", "0x1002": "AMD", "0x10de": "NVIDIA"}
    roots = (Path("/host/drm"), Path("/sys/class/drm"))
    cards: list[Path] = []
    for root in roots:
        try:
            cards = sorted(path for path in root.glob("card*") if re.fullmatch(r"card\d+", path.name))
        except OSError:
            cards = []
        if cards:
            break

    devices: list[dict[str, Any]] = []
    for card in cards:
        device = card / "device"
        vendor_id = _read_text(str(device / "vendor")).casefold()
        device_id = _read_text(str(device / "device")).casefold()
        if not vendor_id:
            continue
        utilization = _number(_read_text(str(device / "gpu_busy_percent")))
        memory_used_bytes = _number(_read_text(str(device / "mem_info_vram_used")))
        memory_total_bytes = _number(_read_text(str(device / "mem_info_vram_total")))
        temperature_c: float | None = None
        power_w: float | None = None
        try:
            hwmon_dirs = list((device / "hwmon").glob("hwmon*"))
        except OSError:
            hwmon_dirs = []
        for hwmon in hwmon_dirs:
            temperature_raw = _number(_read_text(str(hwmon / "temp1_input")))
            power_raw = _number(_read_text(str(hwmon / "power1_average")))
            if temperature_raw is not None:
                temperature_c = round(temperature_raw / 1000, 1) if temperature_raw > 500 else temperature_raw
            if power_raw is not None:
                power_w = round(power_raw / 1_000_000, 1) if power_raw > 10_000 else power_raw
        memory_used = memory_used_bytes / MIB if memory_used_bytes is not None else None
        memory_total = memory_total_bytes / MIB if memory_total_bytes is not None else None
        devices.append(
            {
                "uuid": card.name,
                "index": int(card.name.removeprefix("card")),
                "name": f"{vendor_names.get(vendor_id, 'DRM')} GPU {device_id or card.name}",
                "utilization_percent": utilization,
                "memory_utilization_percent": None,
                "memory_used_mb": round(memory_used, 1) if memory_used is not None else None,
                "memory_total_mb": round(memory_total, 1) if memory_total is not None else None,
                "memory_percent": round(memory_used / memory_total * 100, 1) if memory_used is not None and memory_total else None,
                "temperature_c": temperature_c,
                "power_w": power_w,
                "driver_version": None,
            }
        )
    return {
        "available": bool(devices),
        "provider": "linux-drm-sysfs" if devices else None,
        "reason": (
            "GPU terdeteksi; counter utilitas/VRAM bergantung pada dukungan driver sysfs"
            if devices else "Tidak ada perangkat GPU yang terlihat dari container"
        ),
        "devices": devices,
        "process_memory": {},
    }


def _query_gpu_devices() -> dict[str, Any]:
    nvidia = _query_nvidia()
    if nvidia.get("available"):
        return nvidia
    drm = _query_linux_drm()
    if drm.get("available"):
        return drm
    reasons = [str(item.get("reason") or "").strip() for item in (nvidia, drm)]
    nvidia["reason"] = " · ".join(reason for reason in reasons if reason)[:240]
    return nvidia


def gpu_snapshot(job_pids: set[int]) -> dict[str, Any]:
    global _gpu_cache, _gpu_cache_at
    now = time.monotonic()
    with _gpu_cache_lock:
        if _gpu_cache is None or now - _gpu_cache_at >= _GPU_CACHE_TTL_SECONDS:
            _gpu_cache = _query_gpu_devices()
            _gpu_cache_at = now
        raw = _gpu_cache

    devices = raw.get("devices", [])
    if not raw.get("available") or not devices:
        return {
            "available": False,
            "provider": raw.get("provider"),
            "reason": raw.get("reason"),
            "device_count": 0,
            "job_memory_mb": 0.0,
        }

    process_memory = raw.get("process_memory", {})
    job_processes = [process_memory[pid] for pid in job_pids if pid in process_memory]
    job_memory_mb = sum(float(item.get("memory_mb") or 0) for item in job_processes)
    job_uuids = {str(item.get("uuid")) for item in job_processes}
    relevant = [item for item in devices if item.get("uuid") in job_uuids] or devices
    primary = max(relevant, key=lambda item: float(item.get("utilization_percent") or 0))
    return {
        "available": True,
        "provider": raw.get("provider"),
        "reason": None,
        "device_count": len(devices),
        "index": primary.get("index"),
        "name": primary.get("name"),
        "utilization_percent": primary.get("utilization_percent"),
        "memory_utilization_percent": primary.get("memory_utilization_percent"),
        "memory_used_mb": primary.get("memory_used_mb"),
        "memory_total_mb": primary.get("memory_total_mb"),
        "memory_percent": primary.get("memory_percent"),
        "temperature_c": primary.get("temperature_c"),
        "power_w": primary.get("power_w"),
        "driver_version": primary.get("driver_version"),
        "job_memory_mb": round(job_memory_mb, 1),
        "job_process_count": len(job_processes),
        "job_attributed": bool(job_processes),
    }


def battery_snapshot() -> dict[str, Any]:
    """Read a laptop battery when visible, with a host-sysfs container fallback."""
    if psutil is not None:
        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                return {
                    "available": True,
                    "percent": round(float(battery.percent), 1),
                    "plugged": bool(battery.power_plugged),
                    "seconds_left": (
                        int(battery.secsleft)
                        if isinstance(battery.secsleft, (int, float)) and battery.secsleft >= 0
                        else None
                    ),
                    "source": "psutil",
                }
        except (AttributeError, OSError, psutil.Error):
            pass

    for root in (Path("/host/power_supply"), Path("/sys/class/power_supply")):
        try:
            batteries = sorted(path for path in root.glob("BAT*") if path.is_dir())
        except OSError:
            continue
        for battery_dir in batteries:
            capacity = _number(_read_text(str(battery_dir / "capacity")))
            status = _read_text(str(battery_dir / "status")).casefold()
            if capacity is not None:
                return {
                    "available": True,
                    "percent": round(capacity, 1),
                    "plugged": status in {"charging", "full", "not charging"},
                    "seconds_left": None,
                    "source": "sysfs",
                }
    return {"available": False, "percent": None, "plugged": None, "seconds_left": None, "source": None}


def cpu_sensor_snapshot() -> tuple[float | None, float | None]:
    frequency_mhz: float | None = None
    temperature_c: float | None = None
    if psutil is None:
        return frequency_mhz, temperature_c
    try:
        frequency = psutil.cpu_freq()
        if frequency is not None:
            frequency_mhz = round(float(frequency.current), 0)
    except (AttributeError, NotImplementedError, OSError, psutil.Error):
        pass
    try:
        temperatures = psutil.sensors_temperatures(fahrenheit=False)
        preferred = [
            entry.current
            for name, entries in temperatures.items()
            if any(token in name.casefold() for token in ("coretemp", "k10temp", "cpu", "soc"))
            for entry in entries
            if entry.current is not None
        ]
        if preferred:
            temperature_c = round(max(float(value) for value in preferred), 1)
    except (AttributeError, NotImplementedError, OSError, psutil.Error):
        pass
    return frequency_mhz, temperature_c


class ProcessTelemetrySampler:
    """Measure a worker and all current descendants from monotonic counter deltas."""

    def __init__(self, root_pid: int, *, history_size: int = 48):
        self.root_pid = root_pid
        self.cpu_capacity = cpu_capacity_cores()
        self.previous_at: float | None = None
        self.previous_process_cpu: dict[int, float] = {}
        self.previous_process_io: dict[int, tuple[int, int]] = {}
        self.previous_net: tuple[int, int] | None = None
        self.previous_server_cpu: tuple[float, float] | None = None
        self.sequence = 0
        self.history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self.alerts: deque[dict[str, Any]] = deque(maxlen=24)
        self.alert_active: dict[str, bool] = {}
        self.peaks = {
            "job_cpu_percent": 0.0,
            "server_cpu_percent": 0.0,
            "job_memory_mb": 0.0,
            "gpu_utilization_percent": 0.0,
            "io_mb_s": 0.0,
            "network_mb_s": 0.0,
        }

    def _threshold_alert(
        self,
        *,
        code: str,
        active: bool,
        severity: str,
        message: str,
        value: float,
        unit: str,
        sampled_at: str,
    ) -> None:
        was_active = self.alert_active.get(code, False)
        if active and not was_active:
            self.alerts.append(
                {
                    "sequence": self.sequence,
                    "sampled_at": sampled_at,
                    "code": code,
                    "severity": severity,
                    "message": message,
                    "value": round(value, 2),
                    "unit": unit,
                }
            )
        self.alert_active[code] = active

    def _processes(self) -> list[Any]:
        if psutil is None:
            return []
        try:
            root = psutil.Process(self.root_pid)
            return [root, *root.children(recursive=True)]
        except (psutil.Error, OSError):
            return []

    @staticmethod
    def _server_cpu_times() -> tuple[float, float]:
        if psutil is None:
            return 0.0, 0.0
        times = psutil.cpu_times()
        values = [float(value) for value in times]
        total = sum(values)
        idle = float(getattr(times, "idle", 0)) + float(getattr(times, "iowait", 0))
        return total, idle

    def sample(
        self,
        *,
        active: bool = True,
        stage: str | None = None,
        clip_index: int | None = None,
        clip_total: int | None = None,
    ) -> dict[str, Any]:
        now = time.monotonic()
        interval = max(0.001, now - self.previous_at) if self.previous_at is not None else 0.0
        processes = self._processes()
        pids: set[int] = set()
        current_cpu: dict[int, float] = {}
        current_io: dict[int, tuple[int, int]] = {}
        rss_bytes = 0
        thread_count = 0
        cpu_delta = 0.0
        read_delta = 0
        write_delta = 0

        if psutil is not None:
            for process in processes:
                try:
                    pid = int(process.pid)
                    pids.add(pid)
                    cpu_times = process.cpu_times()
                    cpu_value = float(cpu_times.user + cpu_times.system)
                    current_cpu[pid] = cpu_value
                    previous_cpu = self.previous_process_cpu.get(pid)
                    if previous_cpu is not None:
                        cpu_delta += max(0.0, cpu_value - previous_cpu)
                    rss_bytes += int(process.memory_info().rss)
                    thread_count += int(process.num_threads())
                    try:
                        counters = process.io_counters()
                        io_value = (int(counters.read_bytes), int(counters.write_bytes))
                        current_io[pid] = io_value
                        previous_io = self.previous_process_io.get(pid)
                        if previous_io is not None:
                            read_delta += max(0, io_value[0] - previous_io[0])
                            write_delta += max(0, io_value[1] - previous_io[1])
                    except (AttributeError, psutil.Error, OSError):
                        pass
                except (psutil.Error, OSError):
                    continue

        raw_cpu_percent = cpu_delta / interval * 100 if interval else 0.0
        normalized_cpu_percent = raw_cpu_percent / max(0.1, self.cpu_capacity)

        server_times = self._server_cpu_times()
        server_cpu_percent = 0.0
        if self.previous_server_cpu is not None:
            total_delta = max(0.0, server_times[0] - self.previous_server_cpu[0])
            idle_delta = max(0.0, server_times[1] - self.previous_server_cpu[1])
            if total_delta:
                server_cpu_percent = (1 - min(1.0, idle_delta / total_delta)) * 100

        memory_used, memory_total = memory_capacity_bytes()
        server_memory_percent = memory_used / memory_total * 100 if memory_total else 0.0
        job_memory_percent = rss_bytes / memory_total * 100 if memory_total else 0.0

        network_rx_mbps = 0.0
        network_tx_mbps = 0.0
        if psutil is not None:
            try:
                net = psutil.net_io_counters()
                net_value = (int(net.bytes_recv), int(net.bytes_sent))
                if self.previous_net is not None and interval:
                    network_rx_mbps = max(0, net_value[0] - self.previous_net[0]) / MIB / interval
                    network_tx_mbps = max(0, net_value[1] - self.previous_net[1]) / MIB / interval
                self.previous_net = net_value
            except (AttributeError, OSError):
                pass

        try:
            load_1m, load_5m, load_15m = os.getloadavg()
        except (AttributeError, OSError):
            load_1m = load_5m = load_15m = 0.0
        try:
            disk = shutil.disk_usage(Path.cwd())
            disk_free_gb = disk.free / (1024 ** 3)
            disk_used_percent = disk.used / disk.total * 100 if disk.total else 0.0
        except OSError:
            disk_free_gb = disk_used_percent = 0.0

        gpu = gpu_snapshot(pids)
        self.sequence += 1
        sampled_at = datetime.now(timezone.utc).isoformat()
        io_mb_s = (read_delta + write_delta) / MIB / interval if interval else 0.0
        network_mb_s = network_rx_mbps + network_tx_mbps
        gpu_utilization = float(gpu.get("utilization_percent") or 0)
        gpu_temperature = float(gpu.get("temperature_c") or 0)
        cpu_frequency_mhz, cpu_temperature_c = cpu_sensor_snapshot()
        battery = battery_snapshot()
        peak_values = {
            "job_cpu_percent": normalized_cpu_percent,
            "server_cpu_percent": server_cpu_percent,
            "job_memory_mb": rss_bytes / MIB,
            "gpu_utilization_percent": gpu_utilization,
            "io_mb_s": io_mb_s,
            "network_mb_s": network_mb_s,
        }
        for key, value in peak_values.items():
            self.peaks[key] = round(max(self.peaks[key], value), 2)

        self._threshold_alert(
            code="job_cpu_hot",
            active=normalized_cpu_percent >= 90,
            severity="warning",
            message="CPU job melewati 90% kapasitas yang dialokasikan",
            value=normalized_cpu_percent,
            unit="%",
            sampled_at=sampled_at,
        )
        self._threshold_alert(
            code="server_cpu_hot",
            active=server_cpu_percent >= 92,
            severity="critical",
            message="CPU server melewati 92%",
            value=server_cpu_percent,
            unit="%",
            sampled_at=sampled_at,
        )
        self._threshold_alert(
            code="memory_hot",
            active=server_memory_percent >= 90,
            severity="critical",
            message="RAM server/container melewati 90%",
            value=server_memory_percent,
            unit="%",
            sampled_at=sampled_at,
        )
        self._threshold_alert(
            code="gpu_hot",
            active=bool(gpu.get("available")) and gpu_temperature >= 83,
            severity="critical",
            message="Temperatur GPU melewati 83°C",
            value=gpu_temperature,
            unit="°C",
            sampled_at=sampled_at,
        )
        self._threshold_alert(
            code="disk_low",
            active=disk_free_gb <= 5,
            severity="critical",
            message="Sisa disk kurang dari 5 GB",
            value=disk_free_gb,
            unit="GB",
            sampled_at=sampled_at,
        )
        self._threshold_alert(
            code="io_spike",
            active=io_mb_s >= 150,
            severity="warning",
            message="Lalu lintas disk process tree melewati 150 MB/s",
            value=io_mb_s,
            unit="MB/s",
            sampled_at=sampled_at,
        )
        self._threshold_alert(
            code="battery_low",
            active=bool(battery.get("available")) and not battery.get("plugged") and float(battery.get("percent") or 0) <= 20,
            severity="warning",
            message="Baterai server rendah; Eco HUD disarankan",
            value=float(battery.get("percent") or 0),
            unit="%",
            sampled_at=sampled_at,
        )
        point = {
            "sequence": self.sequence,
            "sampled_at": sampled_at,
            "stage": str(stage or "unknown").strip().casefold() or "unknown",
            "clip_index": clip_index,
            "clip_total": clip_total,
            "job_cpu_percent": round(normalized_cpu_percent, 1),
            "server_cpu_percent": round(server_cpu_percent, 1),
            "job_memory_mb": round(rss_bytes / MIB, 1),
            "gpu_utilization_percent": gpu.get("utilization_percent"),
            "gpu_job_memory_mb": gpu.get("job_memory_mb", 0.0),
            "read_mb_s": round(read_delta / MIB / interval, 2) if interval else 0.0,
            "write_mb_s": round(write_delta / MIB / interval, 2) if interval else 0.0,
            "network_mb_s": round(network_mb_s, 2),
        }
        self.history.append(point)

        snapshot = {
            "available": psutil is not None,
            "source": "psutil+cgroup+nvidia-smi",
            "sampled_at": sampled_at,
            "sequence": self.sequence,
            "interval_seconds": round(interval, 3),
            "active": active and bool(processes),
            "root_pid": self.root_pid,
            "process_count": len(processes),
            "thread_count": thread_count,
            "cpu_capacity_cores": self.cpu_capacity,
            "job_cpu_percent": round(normalized_cpu_percent, 1),
            "job_cpu_core_percent": round(raw_cpu_percent, 1),
            "server_cpu_percent": round(server_cpu_percent, 1),
            "load_1m": round(load_1m, 2),
            "load_5m": round(load_5m, 2),
            "load_15m": round(load_15m, 2),
            "job_memory_mb": round(rss_bytes / MIB, 1),
            "job_memory_percent": round(job_memory_percent, 1),
            "server_memory_used_mb": round(memory_used / MIB, 1),
            "server_memory_total_mb": round(memory_total / MIB, 1),
            "server_memory_percent": round(server_memory_percent, 1),
            "read_mb_s": round(read_delta / MIB / interval, 2) if interval else 0.0,
            "write_mb_s": round(write_delta / MIB / interval, 2) if interval else 0.0,
            "network_rx_mb_s": round(network_rx_mbps, 2),
            "network_tx_mb_s": round(network_tx_mbps, 2),
            "disk_free_gb": round(disk_free_gb, 1),
            "disk_used_percent": round(disk_used_percent, 1),
            "cpu_frequency_mhz": cpu_frequency_mhz,
            "cpu_temperature_c": cpu_temperature_c,
            "battery": battery,
            "gpu": gpu,
            "peaks": dict(self.peaks),
            "alerts": list(self.alerts),
            "history": list(self.history),
        }
        self.previous_at = now
        self.previous_process_cpu = current_cpu
        self.previous_process_io = current_io
        self.previous_server_cpu = server_times
        return snapshot
