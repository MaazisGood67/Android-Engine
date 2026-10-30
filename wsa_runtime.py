"""Safe ADB operations for a user-installed Windows Subsystem for Android."""

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess


class WsaError(RuntimeError):
    pass


@dataclass(frozen=True)
class WsaDeviceInfo:
    serial: str
    android_release: str
    cpu_abi: str
    has_google_play_services: bool
    has_play_store: bool


class WsaController:
    def __init__(self, adb_path=None, endpoint="127.0.0.1:58526"):
        self.adb_path = str(adb_path or shutil.which("adb") or "")
        self.endpoint = endpoint.strip()

    def _validate_adb(self):
        if not self.adb_path or not Path(self.adb_path).is_file():
            raise WsaError("ADB not found. Select adb.exe from Android Platform Tools.")

    def _run(self, *arguments, timeout=20):
        self._validate_adb()
        try:
            result = subprocess.run(
                [self.adb_path, *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise WsaError(f"ADB command failed: {error}") from error
        output = result.stdout.strip()
        if result.returncode != 0:
            detail = result.stderr.strip() or output
            raise WsaError(detail or f"ADB exited with code {result.returncode}")
        return output

    def connect(self):
        if not re.fullmatch(r"[A-Za-z0-9.-]+:[0-9]{1,5}", self.endpoint):
            raise WsaError("Enter an ADB endpoint in host:port format")
        host, port_text = self.endpoint.rsplit(":", 1)
        if not host or not 1 <= int(port_text) <= 65535:
            raise WsaError("ADB endpoint port must be between 1 and 65535")

        connection_message = self._run("connect", self.endpoint)
        devices = self._run("devices")
        for line in devices.splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 2 and fields[0] == self.endpoint and fields[1] == "device":
                return connection_message or f"Connected to {self.endpoint}"
        raise WsaError(
            f"WSA is not available at {self.endpoint}. Start WSA and enable developer mode first."
        )

    def inspect(self):
        self._require_connected()
        release = self._run("-s", self.endpoint, "shell", "getprop", "ro.build.version.release")
        cpu_abi = self._run("-s", self.endpoint, "shell", "getprop", "ro.product.cpu.abi")
        packages = self._run("-s", self.endpoint, "shell", "pm", "list", "packages")
        package_names = set()
        for line in packages.splitlines():
            if line.startswith("package:"):
                package_names.add(line.removeprefix("package:"))
        return WsaDeviceInfo(
            serial=self.endpoint,
            android_release=release or "unknown",
            cpu_abi=cpu_abi or "unknown",
            has_google_play_services="com.google.android.gms" in package_names,
            has_play_store="com.android.vending" in package_names,
        )

    def install_apk(self, apk_path):
        self._require_connected()
        path = Path(apk_path).expanduser().resolve()
        if path.suffix.lower() != ".apk":
            raise WsaError("Choose an .apk file")
        if not path.is_file():
            raise WsaError(f"APK file not found: {path}")
        return self._run("-s", self.endpoint, "install", "-r", str(path), timeout=180)

    def _require_connected(self):
        self._validate_adb()
        devices = self._run("devices")
        if not any(
            len(fields := line.split()) >= 2
            and fields[0] == self.endpoint
            and fields[1] == "device"
            for line in devices.splitlines()[1:]
        ):
            raise WsaError("Connect to WSA before running this action")