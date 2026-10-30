import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vm_runtime import AndroidVmConfig, VmConfigurationError, create_data_overlay


class AndroidVmConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.qemu = self.root / "qemu-system-x86_64.exe"
        self.image = self.root / "maazxdroid-android.qcow2"
        self.disk = self.root / "android-user-data.qcow2"
        self.qemu.touch()
        self.image.touch()
        self.disk.touch()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_boot_uses_user_overlay_without_iso_installer(self):
        config = AndroidVmConfig(self.qemu, self.disk)

        arguments = config.build_arguments()

        self.assertIn("whpx", arguments)
        self.assertNotIn("-cdrom", arguments)
        self.assertTrue(any(str(self.disk) in argument for argument in arguments))
        self.assertEqual(arguments[arguments.index("-m") + 1], "1536")

    def test_invalid_disk_and_memory_are_rejected(self):
        config = AndroidVmConfig(self.qemu, self.root / "missing.qcow2", memory_mb=4096)

        with self.assertRaisesRegex(VmConfigurationError, "memory"):
            config.validate()

    def test_overlay_uses_base_image_and_never_overwrites(self):
        qemu_img = self.root / "qemu-img.exe"
        qemu_img.touch()
        new_overlay = self.root / "new-overlay.qcow2"

        with patch("vm_runtime.subprocess.run") as run:
            run.return_value.returncode = 0
            create_data_overlay(qemu_img, self.image, new_overlay)

        arguments = run.call_args.args[0]
        self.assertIn("-b", arguments)
        self.assertIn(str(self.image.resolve()), arguments)
        self.assertEqual(arguments[-1], str(new_overlay))
        with self.assertRaisesRegex(VmConfigurationError, "overwrite"):
            create_data_overlay(qemu_img, self.image, self.disk)

    def test_overlay_requires_qcow2_base_image(self):
        qemu_img = self.root / "qemu-img.exe"
        qemu_img.touch()
        raw_image = self.root / "android.iso"
        raw_image.touch()

        with self.assertRaisesRegex(VmConfigurationError, "QCOW2"):
            create_data_overlay(qemu_img, raw_image, self.root / "overlay.qcow2")


if __name__ == "__main__":
    unittest.main()