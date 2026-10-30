import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wsa_runtime import WsaController, WsaError


class WsaControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.adb = self.root / "adb.exe"
        self.adb.touch()
        self.controller = WsaController(self.adb, "127.0.0.1:58526")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_connect_requires_an_authorized_device(self):
        with patch("wsa_runtime.subprocess.run") as run:
            run.side_effect = [
                SimpleNamespace(returncode=0, stdout="connected to 127.0.0.1:58526", stderr=""),
                SimpleNamespace(returncode=0, stdout="List of devices attached\n127.0.0.1:58526\tdevice", stderr=""),
            ]
            message = self.controller.connect()

        self.assertIn("connected", message)

    def test_inspection_reports_google_services_without_assuming_play_store(self):
        with patch.object(
            self.controller,
            "_run",
            side_effect=[
                "List of devices attached\n127.0.0.1:58526\tdevice",
                "13",
                "x86_64",
                "package:com.google.android.gms\npackage:com.example.game",
            ],
        ):
            info = self.controller.inspect()

        self.assertEqual(info.android_release, "13")
        self.assertEqual(info.cpu_abi, "x86_64")
        self.assertTrue(info.has_google_play_services)
        self.assertFalse(info.has_play_store)

    def test_install_uses_adb_sideload_without_shell(self):
        apk = self.root / "sample.apk"
        apk.touch()
        with patch.object(self.controller, "_require_connected"), patch(
            "wsa_runtime.subprocess.run"
        ) as run:
            run.return_value = SimpleNamespace(returncode=0, stdout="Success", stderr="")
            output = self.controller.install_apk(apk)

        self.assertEqual(output, "Success")
        arguments = run.call_args.args[0]
        self.assertIn("install", arguments)
        self.assertIn("-r", arguments)
        self.assertEqual(run.call_args.kwargs["shell"], False)

    def test_install_rejects_non_apk_file(self):
        file_path = self.root / "installer.exe"
        file_path.touch()
        with patch.object(self.controller, "_require_connected"):
            with self.assertRaisesRegex(WsaError, r"\.apk"):
                self.controller.install_apk(file_path)

    def test_lists_only_user_installed_packages(self):
        with patch.object(
            self.controller,
            "_run",
            side_effect=[
                "List of devices attached\n127.0.0.1:58526\tdevice",
                "package:com.example.game\npackage:com.example.store",
            ],
        ):
            packages = self.controller.list_user_apps()

        self.assertEqual(packages, ["com.example.game", "com.example.store"])

    def test_rejects_invalid_endpoint(self):
        controller = WsaController(self.adb, "127.0.0.1:99999")

        with self.assertRaisesRegex(WsaError, "port"):
            controller.connect()


if __name__ == "__main__":
    unittest.main()