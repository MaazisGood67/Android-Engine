"""Read-only host and Android device diagnostics for MaazXdroid."""

import argparse
import platform
import shutil
import subprocess
import sys


class MaazXdroidEmulatorCore:
    def __init__(self, adb_path=None, serial=None):
        self.adb_path = adb_path or shutil.which("adb")
        self.serial = serial

    def print_host_report(self):
        print("MaazXdroid diagnostics")
        print(f"Host OS: {platform.system()} {platform.release()}")
        print(f"Host architecture: {platform.machine() or 'unknown'}")
        print(f"Processor: {platform.processor() or 'unknown'}")
        print("Android emulation: not provided by this diagnostic tool")

    def _adb(self, *arguments):
        result = subprocess.run(
            [self.adb_path, *arguments],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(detail or f"adb exited with code {result.returncode}")
        return result.stdout.strip()

    def inspect_android_device(self):
        if not self.adb_path:
            print("ADB: not found; install Android Platform Tools to inspect a device")
            return False

        print(f"ADB: {self.adb_path}")
        output = self._adb("devices", "-l")
        devices = []
        for line in output.splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 2:
                devices.append((fields[0], fields[1]))

        if self.serial:
            matches = [device for device in devices if device[0] == self.serial]
            if not matches or matches[0][1] != "device":
                print(f"Device {self.serial!r} is not connected and authorized")
                return False
            serial = self.serial
        else:
            online = [serial for serial, state in devices if state == "device"]
            if len(online) != 1:
                if online:
                    print("More than one device is connected; select one with --serial")
                else:
                    print("No authorized Android device found")
                return False
            serial = online[0]

        def getprop(name):
            return self._adb("-s", serial, "shell", "getprop", name) or "unknown"

        print(f"Device: {serial}")
        print(f"Android release: {getprop('ro.build.version.release')}")
        print(f"Supported ABIs: {getprop('ro.product.cpu.abilist')}")
        print("Note: ABI presence alone does not guarantee app or game compatibility.")
        return True

    def run(self):
        self.print_host_report()
        print()
        try:
            return self.inspect_android_device()
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
            print(f"ADB inspection failed: {error}", file=sys.stderr)
            return False


def main():
    parser = argparse.ArgumentParser(description="Read-only MaazXdroid diagnostics")
    parser.add_argument("--adb", help="Path to adb executable; defaults to PATH lookup")
    parser.add_argument("--serial", help="ADB serial when selecting among devices")
    arguments = parser.parse_args()

    diagnostics = MaazXdroidEmulatorCore(arguments.adb, arguments.serial)
    return 0 if diagnostics.run() else 1


if __name__ == "__main__":
    raise SystemExit(main())