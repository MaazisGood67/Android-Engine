"""QEMU command construction and virtual-disk operations for MaazXdroid."""

from dataclasses import dataclass
from pathlib import Path
import subprocess


class VmConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class AndroidVmConfig:
    qemu_path: Path
    disk_path: Path
    memory_mb: int = 1536
    cpu_count: int = 2

    def validate(self):
        if not self.qemu_path.is_file():
            raise VmConfigurationError(f"QEMU executable not found: {self.qemu_path}")
        if self.memory_mb < 512 or self.memory_mb > 3072:
            raise VmConfigurationError("VM memory must be between 512 MB and 3072 MB")
        if self.cpu_count < 1 or self.cpu_count > 4:
            raise VmConfigurationError("VM CPU count must be between 1 and 4")
        if not self.disk_path.is_file():
            raise VmConfigurationError(
                f"User-data disk not found: {self.disk_path}. Create it from an Android image first."
            )

    def build_arguments(self):
        self.validate()
        return [
            str(self.qemu_path),
            "-name",
            "MaazXdroid Android",
            "-accel",
            "whpx",
            "-machine",
            "q35",
            "-cpu",
            "max",
            "-smp",
            str(self.cpu_count),
            "-m",
            str(self.memory_mb),
            "-vga",
            "std",
            "-drive",
            f"file={self.disk_path},format=qcow2,if=ide",
            "-netdev",
            "user,id=net0",
            "-device",
            "e1000,netdev=net0",
            "-device",
            "usb-tablet",
        ]


def create_data_overlay(qemu_img_path, base_image_path, overlay_path):
    qemu_img = Path(qemu_img_path)
    base_image = Path(base_image_path)
    overlay = Path(overlay_path)
    if not qemu_img.is_file():
        raise VmConfigurationError(f"QEMU disk tool not found: {qemu_img}")
    if not base_image.is_file():
        raise VmConfigurationError(f"MaazXdroid Android system image not found: {base_image}")
    if base_image.suffix.lower() != ".qcow2":
        raise VmConfigurationError("The Android system image must be a QCOW2 file")
    if overlay.exists():
        raise VmConfigurationError(f"Refusing to overwrite existing user-data disk: {overlay}")

    overlay.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(qemu_img),
            "create",
            "-f",
            "qcow2",
            "-F",
            "qcow2",
            "-b",
            str(base_image.resolve()),
            str(overlay),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise VmConfigurationError(detail or "qemu-img failed to create the user-data disk")
    return overlay