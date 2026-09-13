import os
import time

import telemetry
from telemetry import ProcessTelemetrySampler, cpu_capacity_cores, gpu_snapshot


def test_cpu_capacity_respects_cgroup_v2_quota(monkeypatch):
    monkeypatch.setattr(telemetry, "psutil", None)
    monkeypatch.setattr(telemetry.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(
        telemetry,
        "_read_text",
        lambda path: "400000 100000" if path.endswith("cpu.max") else "",
    )

    assert cpu_capacity_cores() == 4.0


def test_gpu_snapshot_reports_unavailable_without_inventing_values(monkeypatch):
    monkeypatch.setattr(telemetry.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        telemetry,
        "_query_linux_drm",
        lambda: {
            "available": False,
            "provider": None,
            "reason": "Tidak ada perangkat GPU yang terlihat dari container",
            "devices": [],
            "process_memory": {},
        },
    )
    monkeypatch.setattr(telemetry, "_gpu_cache", None)
    monkeypatch.setattr(telemetry, "_gpu_cache_at", 0.0)

    result = gpu_snapshot({os.getpid()})

    assert result["available"] is False
    assert result["device_count"] == 0
    assert result["job_memory_mb"] == 0
    assert "Runtime NVIDIA" in result["reason"]


def test_gpu_snapshot_attributes_vram_to_job_pid(monkeypatch):
    class Result:
        def __init__(self, stdout):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    responses = iter(
        [
            Result("GPU-1, 0, NVIDIA Test, 73, 18, 2048, 8192, 67, 121.5, 555.1\n"),
            Result("GPU-1, 4242, 768\nGPU-1, 9999, 256\n"),
        ]
    )
    monkeypatch.setattr(telemetry.shutil, "which", lambda _name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(telemetry.subprocess, "run", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(telemetry, "_gpu_cache", None)
    monkeypatch.setattr(telemetry, "_gpu_cache_at", 0.0)

    result = gpu_snapshot({4242})

    assert result["available"] is True
    assert result["utilization_percent"] == 73
    assert result["memory_percent"] == 25
    assert result["job_memory_mb"] == 768
    assert result["job_process_count"] == 1
    assert result["job_attributed"] is True


def test_process_sampler_emits_real_bounded_history():
    sampler = ProcessTelemetrySampler(os.getpid(), history_size=2)
    sampler.sample()
    time.sleep(0.02)
    sampler.sample()
    snapshot = sampler.sample()

    assert snapshot["available"] is True
    assert snapshot["root_pid"] == os.getpid()
    assert snapshot["process_count"] >= 1
    assert snapshot["cpu_capacity_cores"] > 0
    assert snapshot["job_memory_mb"] > 0
    assert len(snapshot["history"]) == 2
    assert snapshot["source"] == "psutil+cgroup+nvidia-smi"
    assert set(snapshot["peaks"]) == {
        "job_cpu_percent",
        "server_cpu_percent",
        "job_memory_mb",
        "gpu_utilization_percent",
        "io_mb_s",
        "network_mb_s",
    }
    assert isinstance(snapshot["alerts"], list)
    assert "available" in snapshot["battery"]
