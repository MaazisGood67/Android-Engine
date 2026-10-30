import unittest

from host_compatibility import assess_host


class HostCompatibilityTests(unittest.TestCase):
    def test_target_windows_build_and_4gb_ram_are_reported_honestly(self):
        checks = assess_host(
            os_name="Windows",
            os_version="10.0.19044.0",
            architecture="AMD64",
            total_ram_bytes=4 * 1024**3,
        )
        by_name = {check.name: check for check in checks}

        self.assertEqual(by_name["Windows build"].status, "CHECK UPDATES")
        self.assertEqual(by_name["Architecture"].status, "OK")
        self.assertEqual(by_name["Memory"].status, "BELOW MINIMUM")
        self.assertEqual(by_name["Virtualization"].status, "VERIFY IN BIOS")
        self.assertEqual(by_name["WSA maintenance"].status, "ARCHIVED")

    def test_outdated_windows_build_and_architecture_are_blocked(self):
        checks = assess_host(
            os_name="Windows",
            os_version="10.0.19041.1000",
            architecture="x86",
            total_ram_bytes=16 * 1024**3,
        )
        by_name = {check.name: check for check in checks}

        self.assertEqual(by_name["Windows build"].status, "BLOCKED")
        self.assertEqual(by_name["Architecture"].status, "BLOCKED")
        self.assertEqual(by_name["Memory"].status, "OK")

    def test_non_windows_host_is_not_supported(self):
        checks = assess_host(
            os_name="Linux",
            os_version="6.8.0",
            architecture="x86_64",
            total_ram_bytes=16 * 1024**3,
        )

        self.assertEqual(checks[0].status, "BLOCKED")


if __name__ == "__main__":
    unittest.main()