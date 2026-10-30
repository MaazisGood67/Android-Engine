"""Summarize MaazXdroid system telemetry CSV captures."""

import argparse
import csv
import math
from pathlib import Path
import re
import sys


class CaptureFormatError(ValueError):
    pass


def analyze_capture(path):
    capture_path = Path(path)
    try:
        source = capture_path.open("r", newline="", encoding="utf-8-sig")
    except OSError as error:
        raise CaptureFormatError(f"Cannot read capture: {error}") from error

    with source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise CaptureFormatError("Capture has no CSV header")
        required = {"timestamp", "system_cpu_percent", "memory_available_mb"}
        missing = sorted(required.difference(reader.fieldnames))
        if missing:
            raise CaptureFormatError("Missing required columns: " + ", ".join(missing))

        core_fields = sorted(
            (field for field in reader.fieldnames if re.fullmatch(r"core_\d+_percent", field)),
            key=lambda field: int(field.split("_")[1]),
        )
        samples = []
        invalid_rows = 0
        for row in reader:
            try:
                sample = {
                    "cpu": _number(row, "system_cpu_percent"),
                    "memory_available_mb": _number(row, "memory_available_mb"),
                    "pagefile_percent": _optional_number(row, "pagefile_percent"),
                    "disk_busy_percent": _optional_number(row, "disk_busy_percent"),
                    "disk_read": _optional_number(row, "disk_read_mb_per_second"),
                    "disk_write": _optional_number(row, "disk_write_mb_per_second"),
                    "cores": [_number(row, field) for field in core_fields],
                }
            except (TypeError, ValueError):
                invalid_rows += 1
                continue
            samples.append(sample)

    if not samples:
        raise CaptureFormatError("Capture contains no valid data rows")

    count = len(samples)
    average_cpu = sum(sample["cpu"] for sample in samples) / count
    peak_cpu = max(sample["cpu"] for sample in samples)
    lowest_memory = min(sample["memory_available_mb"] for sample in samples)
    per_core_samples = [sample for sample in samples if sample["cores"]]
    peak_core = max(
        (max(sample["cores"]) for sample in per_core_samples),
        default=None,
    )
    hot_core_count = sum(
        1
        for sample in per_core_samples
        if max(sample["cores"]) >= 90.0
    )
    paging_count = sum(
        1
        for sample in samples
        if sample["pagefile_percent"] is not None
        and sample["disk_busy_percent"] is not None
        and sample["pagefile_percent"] >= 50.0
        and sample["disk_busy_percent"] >= 70.0
    )
    average_read = _average_optional(samples, "disk_read")
    average_write = _average_optional(samples, "disk_write")

    findings = []
    if lowest_memory < 400.0:
        findings.append("Available RAM fell below 400 MB; memory pressure is likely.")
    if average_cpu >= 85.0:
        findings.append("Average system CPU was at least 85%; CPU contention may contribute to stutter.")
    if per_core_samples and hot_core_count / len(per_core_samples) >= 0.25:
        findings.append("At least one logical CPU was 90%+ in a quarter or more of samples.")
    if paging_count:
        findings.append(
            f"High pagefile use coincided with high disk busy time in {paging_count} sample(s); "
            "possible paging pressure."
        )
    if not findings:
        findings.append("No tracked CPU, low-memory, or combined pagefile/disk threshold was crossed.")

    return {
        "path": capture_path,
        "samples": count,
        "invalid_rows": invalid_rows,
        "average_cpu": average_cpu,
        "peak_cpu": peak_cpu,
        "lowest_memory_mb": lowest_memory,
        "peak_core": peak_core,
        "average_read": average_read,
        "average_write": average_write,
        "findings": findings,
    }


def _number(row, name):
    value = float(row[name])
    if not math.isfinite(value):
        raise ValueError(f"{name} is not finite")
    return value


def _optional_number(row, name):
    value = row.get(name)
    if value in (None, ""):
        return None
    return _number(row, name)


def _average_optional(samples, field):
    values = [sample[field] for sample in samples if sample[field] is not None]
    return sum(values) / len(values) if values else None


def format_report(analysis):
    lines = [
        "MaazXdroid Capture Analysis",
        f"File: {analysis['path']}",
        f"Valid samples: {analysis['samples']}",
        f"Skipped malformed rows: {analysis['invalid_rows']}",
        f"System CPU average / peak: {analysis['average_cpu']:.1f}% / {analysis['peak_cpu']:.1f}%",
        f"Lowest available RAM: {analysis['lowest_memory_mb']:.0f} MB",
    ]
    if analysis["peak_core"] is not None:
        lines.append(f"Peak logical-core load: {analysis['peak_core']:.1f}%")
    if analysis["average_read"] is not None and analysis["average_write"] is not None:
        lines.append(
            "Average disk read / write: "
            f"{analysis['average_read']:.3f} / {analysis['average_write']:.3f} MB/s"
        )
    lines.append("Findings:")
    lines.extend(f"- {finding}" for finding in analysis["findings"])
    lines.append("This report indicates possible bottlenecks; it does not measure FPS or prove causation.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze a MaazXdroid telemetry CSV")
    parser.add_argument("capture", help="Path to a telemetry CSV capture")
    arguments = parser.parse_args()
    try:
        print(format_report(analyze_capture(arguments.capture)))
    except CaptureFormatError as error:
        print(f"Capture analysis failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())