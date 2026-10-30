"""Read-only system telemetry for diagnosing runtime stutter."""

from dataclasses import dataclass
import time

import psutil


LOW_MEMORY_BYTES = 400 * 1024 * 1024
HIGH_DISK_BUSY_PERCENT = 70.0
HIGH_PAGEFILE_PERCENT = 50.0


@dataclass(frozen=True)
class TelemetrySample:
    timestamp: str
    cpu_percent: float
    core_cpu_percent: tuple
    memory_total_bytes: int
    memory_available_bytes: int
    memory_used_bytes: int
    memory_percent: float
    pagefile_total_bytes: int
    pagefile_used_bytes: int
    pagefile_percent: float
    disk_read_bytes_per_second: float
    disk_write_bytes_per_second: float
    disk_busy_percent: float
    warnings: tuple


class SystemTelemetry:
    def __init__(self):
        psutil.cpu_percent(percpu=True)
        self._previous_disk = psutil.disk_io_counters()
        self._previous_time = time.monotonic()

    def sample(self):
        sampled_at = time.monotonic()
        elapsed = max(sampled_at - self._previous_time, 0.001)
        core_cpu = tuple(psutil.cpu_percent(percpu=True))
        memory = psutil.virtual_memory()
        pagefile = psutil.swap_memory()
        disk = psutil.disk_io_counters()

        read_rate = self._rate(disk, self._previous_disk, "read_bytes", elapsed)
        write_rate = self._rate(disk, self._previous_disk, "write_bytes", elapsed)
        busy_percent = self._busy_percent(disk, self._previous_disk, elapsed)

        self._previous_disk = disk
        self._previous_time = sampled_at

        cpu_percent = sum(core_cpu) / len(core_cpu) if core_cpu else 0.0
        warnings = []
        if memory.available < LOW_MEMORY_BYTES:
            warnings.append("Low available memory: less than 400 MB")
        if (
            pagefile.percent >= HIGH_PAGEFILE_PERCENT
            and busy_percent >= HIGH_DISK_BUSY_PERCENT
        ):
            warnings.append(
                "High pagefile use and disk activity; possible paging pressure"
            )

        return TelemetrySample(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            cpu_percent=cpu_percent,
            core_cpu_percent=core_cpu,
            memory_total_bytes=memory.total,
            memory_available_bytes=memory.available,
            memory_used_bytes=memory.used,
            memory_percent=memory.percent,
            pagefile_total_bytes=pagefile.total,
            pagefile_used_bytes=pagefile.used,
            pagefile_percent=pagefile.percent,
            disk_read_bytes_per_second=read_rate,
            disk_write_bytes_per_second=write_rate,
            disk_busy_percent=busy_percent,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _rate(current, previous, counter, elapsed):
        if current is None or previous is None:
            return 0.0
        difference = max(getattr(current, counter, 0) - getattr(previous, counter, 0), 0)
        return difference / elapsed

    @staticmethod
    def _busy_percent(current, previous, elapsed):
        if current is None or previous is None:
            return 0.0
        current_busy = getattr(current, "busy_time", None)
        previous_busy = getattr(previous, "busy_time", None)
        if current_busy is None or previous_busy is None:
            return 0.0
        difference = max(current_busy - previous_busy, 0)
        return min(difference / (elapsed * 10), 100.0)