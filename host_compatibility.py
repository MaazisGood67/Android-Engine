"""Best-effort host checks for the archived WSAOnWin10 requirements."""

from dataclasses import dataclass
import platform
import re


WSA_MINIMUM_BUILD = (10, 0, 19042, 2604)
WSA_MINIMUM_RAM_BYTES = 8 * 1024**3
WSA_RECOMMENDED_RAM_BYTES = 16 * 1024**3


@dataclass(frozen=True)
class CompatibilityCheck:
    name: str
    status: str
    detail: str


def _version_tuple(value):
    match = re.match(r"^(\d+(?:\.\d+){1,3})", value or "")
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def assess_host(os_name=None, os_version=None, architecture=None, total_ram_bytes=None):
    os_name = platform.system() if os_name is None else os_name
    os_version = platform.version() if os_version is None else os_version
    architecture = platform.machine() if architecture is None else architecture
    if total_ram_bytes is None:
        try:
            import psutil

            total_ram_bytes = psutil.virtual_memory().total
        except ImportError:
            total_ram_bytes = 0

    checks = []
    if os_name != "Windows":
        checks.append(
            CompatibilityCheck("Windows", "BLOCKED", "WSAOnWin10 requires Windows 10.")
        )
    else:
        version = _version_tuple(os_version)
        if version is None:
            checks.append(
                CompatibilityCheck("Windows build", "UNKNOWN", "Could not parse the Windows build number.")
            )
        elif version < WSA_MINIMUM_BUILD:
            checks.append(
                CompatibilityCheck(
                    "Windows build",
                    "BLOCKED",
                    "WSAOnWin10 documents Windows 10 build 19042.2604 as its minimum.",
                )
            )
        else:
            checks.append(
                CompatibilityCheck(
                    "Windows build",
                    "CHECK UPDATES",
                    "Build number meets the stated floor; verify KB5014032 and KB5022834 are installed.",
                )
            )

    normalized_architecture = (architecture or "").lower()
    if normalized_architecture in {"amd64", "x86_64"}:
        checks.append(
            CompatibilityCheck("Architecture", "OK", f"64-bit host detected ({architecture}).")
        )
    else:
        checks.append(
            CompatibilityCheck("Architecture", "BLOCKED", f"Unsupported host architecture: {architecture or 'unknown'}.")
        )

    ram_gib = total_ram_bytes / (1024**3)
    if total_ram_bytes < WSA_MINIMUM_RAM_BYTES:
        checks.append(
            CompatibilityCheck(
                "Memory",
                "BELOW MINIMUM",
                f"{ram_gib:.1f} GB detected; WSAOnWin10 documents 8 GB minimum and 16 GB recommended.",
            )
        )
    elif total_ram_bytes < WSA_RECOMMENDED_RAM_BYTES:
        checks.append(
            CompatibilityCheck(
                "Memory",
                "MINIMUM ONLY",
                f"{ram_gib:.1f} GB detected; WSAOnWin10 recommends 16 GB.",
            )
        )
    else:
        checks.append(
            CompatibilityCheck("Memory", "OK", f"{ram_gib:.1f} GB detected.")
        )

    checks.append(
        CompatibilityCheck(
            "Virtualization",
            "VERIFY IN BIOS",
            "Enable Intel VT-x and Windows Virtual Machine Platform; this app cannot reliably verify firmware state.",
        )
    )
    checks.append(
        CompatibilityCheck(
            "WSA maintenance",
            "ARCHIVED",
            "Microsoft ended WSA support; WSAOnWin10 is archived and its Android security patches are outdated.",
        )
    )
    return tuple(checks)