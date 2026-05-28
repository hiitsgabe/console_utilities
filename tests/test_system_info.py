"""Tests for system_info data gathering service."""

import importlib.util
import os

_mod_path = os.path.join(
    os.path.dirname(__file__), "..", "src", "services", "system_info.py"
)
_spec = importlib.util.spec_from_file_location("system_info", _mod_path)
system_info = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(system_info)

format_bytes = system_info.format_bytes
DiskInfo = system_info.DiskInfo


class TestFormatBytes:
    def test_gigabytes(self):
        assert format_bytes(12_300_000_000) == "11.5 GB"

    def test_megabytes(self):
        assert format_bytes(5 * 1024 * 1024) == "5.0 MB"

    def test_zero(self):
        assert format_bytes(0) == "0.0 B"

    def test_none(self):
        assert format_bytes(None) == "--"


class TestParseOsRelease:
    def test_parses_name_and_version(self):
        content = 'NAME="Batocera"\nVERSION="40 (Beta)"\nVERSION_ID=40\n'
        result = system_info._parse_os_release(content)
        assert result["name"] == "Batocera"
        assert result["version"] == "40 (Beta)"

    def test_falls_back_to_version_id(self):
        content = 'NAME="Knulli"\nVERSION_ID=20240601\n'
        result = system_info._parse_os_release(content)
        assert result["name"] == "Knulli"
        assert result["version"] == "20240601"

    def test_empty_returns_empty_dict(self):
        assert system_info._parse_os_release("") == {}


class TestParseCpuModel:
    def test_extracts_model_name(self):
        content = "processor\t: 0\nmodel name\t: ARM Cortex-A53\n"
        assert system_info._parse_cpu_model(content) == "ARM Cortex-A53"

    def test_missing_returns_none(self):
        assert system_info._parse_cpu_model("processor\t: 0\n") is None


class TestParseMeminfo:
    def test_computes_total_and_used(self):
        content = "MemTotal:       1000000 kB\nMemAvailable:    400000 kB\n"
        total, used = system_info._parse_meminfo(content)
        assert total == 1000000 * 1024
        assert used == (1000000 - 400000) * 1024

    def test_missing_available_returns_none_used(self):
        content = "MemTotal:       1000000 kB\n"
        total, used = system_info._parse_meminfo(content)
        assert total == 1000000 * 1024
        assert used is None

    def test_empty_returns_none(self):
        assert system_info._parse_meminfo("") == (None, None)


class TestGatherDynamicDisks:
    def test_dedupes_mounts(self, monkeypatch):
        # All paths resolve to the same device → one disk row.
        monkeypatch.setattr(system_info.os.path, "exists", lambda p: True)
        monkeypatch.setattr(
            system_info, "_mount_point", lambda p: "/"
        )

        class FakeUsage:
            total, used, free = 100, 60, 40

        monkeypatch.setattr(
            system_info.shutil, "disk_usage", lambda p: FakeUsage()
        )
        result = system_info.gather_dynamic(roms_dir="/roms", work_dir="/work")
        assert len(result["disks"]) == 1
        assert result["disks"][0].used == 60

    def test_disk_probe_failure_is_skipped(self, monkeypatch):
        monkeypatch.setattr(system_info.os.path, "exists", lambda p: True)
        monkeypatch.setattr(system_info, "_mount_point", lambda p: p)

        def boom(p):
            raise OSError("nope")

        monkeypatch.setattr(system_info.shutil, "disk_usage", boom)
        result = system_info.gather_dynamic(roms_dir="/roms", work_dir="/work")
        assert result["disks"] == []
