import unittest
from types import SimpleNamespace
from unittest.mock import patch

from telemetry import SystemTelemetry


class SystemTelemetryTests(unittest.TestCase):
    def sample_with(self, available_bytes, pagefile_percent, busy_time):
        disk_samples = [
            SimpleNamespace(read_bytes=1000, write_bytes=1000, busy_time=0),
            SimpleNamespace(read_bytes=5000, write_bytes=3000, busy_time=busy_time),
        ]
        memory = SimpleNamespace(
            total=4 * 1024**3,
            available=available_bytes,
            used=4 * 1024**3 - available_bytes,
            percent=90.0,
        )
        pagefile = SimpleNamespace(
            total=4 * 1024**3,
            used=int(4 * 1024**3 * pagefile_percent / 100),
            percent=pagefile_percent,
        )
        with patch("telemetry.psutil.cpu_percent", side_effect=[[0, 0], [25, 75]]), \
             patch("telemetry.psutil.disk_io_counters", side_effect=disk_samples), \
             patch("telemetry.psutil.virtual_memory", return_value=memory), \
             patch("telemetry.psutil.swap_memory", return_value=pagefile), \
             patch("telemetry.time.monotonic", side_effect=[10.0, 11.0]):
            return SystemTelemetry().sample()

    def test_reports_rates_core_load_and_resource_warnings(self):
        sample = self.sample_with(
            available_bytes=350 * 1024**2,
            pagefile_percent=75.0,
            busy_time=800,
        )

        self.assertEqual(sample.cpu_percent, 50.0)
        self.assertEqual(sample.core_cpu_percent, (25, 75))
        self.assertEqual(sample.disk_read_bytes_per_second, 4000.0)
        self.assertEqual(sample.disk_write_bytes_per_second, 2000.0)
        self.assertEqual(sample.disk_busy_percent, 80.0)
        self.assertEqual(len(sample.warnings), 2)

    def test_does_not_flag_paging_without_high_disk_busy_time(self):
        sample = self.sample_with(
            available_bytes=1024**3,
            pagefile_percent=75.0,
            busy_time=100,
        )

        self.assertEqual(sample.warnings, ())


if __name__ == "__main__":
    unittest.main()