"""MaazXdroid launcher and system resource capture UI."""

import csv
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import psutil
from telemetry import SystemTelemetry
from vm_runtime import AndroidVmConfig, VmConfigurationError, create_data_overlay


class MaazXdroidApp:
    BACKGROUND = "#100b1b"
    PANEL = "#1b1229"
    PANEL_ALT = "#26183a"
    TEXT = "#f5edff"
    MUTED = "#b6a4ca"
    ACCENT = "#d46bff"
    WARNING = "#ffc857"

    def __init__(self, root):
        self.root = root
        self.root.title("MaazXdroid | Android Gaming VM")
        self.root.geometry("1000x760")
        self.root.minsize(880, 700)
        self.root.configure(bg=self.BACKGROUND)
        try:
            self.root.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        self._window_icon = tk.PhotoImage(width=32, height=32)
        self._window_icon.put(self.BACKGROUND, to=(0, 0, 32, 32))
        for offset in range(5, 27):
            self._window_icon.put(
                self.ACCENT, to=(offset, offset, offset + 3, offset + 3)
            )
            self._window_icon.put(
                self.ACCENT, to=(29 - offset, offset, 32 - offset, offset + 3)
            )
        self.root.iconphoto(True, self._window_icon)

        app_data = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))
        ) / "MaazXdroid"
        self.qemu_path = tk.StringVar()
        self.android_image_path = tk.StringVar(
            value=str(app_data / "images" / "maazxdroid-android.qcow2")
        )
        self.user_data_path = tk.StringVar(
            value=str(app_data / "userdata" / "android-data.qcow2")
        )
        self.vm_memory_mb = tk.StringVar(value="1280")
        self.cpu_text = tk.StringVar(value="-- %")
        self.core_text = tk.StringVar(value="-- %")
        self.memory_text = tk.StringVar(value="-- GB available")
        self.pagefile_text = tk.StringVar(value="-- / -- GB")
        self.disk_text = tk.StringVar(value="R -- / W -- MB/s")
        self.capture_text = tk.StringVar(value="Not recording")
        self.status_text = tk.StringVar(value="Ready")

        self.sample_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.capture_thread = None
        self.capture_file = None
        self.capture_writer = None
        self.capture_path = None
        self.samples = []
        self.telemetry = None
        self.last_warnings = set()

        self._configure_styles()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _configure_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Resource.Horizontal.TProgressbar",
            troughcolor=self.PANEL_ALT,
            background=self.ACCENT,
            bordercolor=self.PANEL_ALT,
            lightcolor=self.ACCENT,
            darkcolor=self.ACCENT,
        )

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=self.BACKGROUND, padx=30, pady=24)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=self.BACKGROUND)
        header.pack(fill="x", pady=(0, 22))
        tk.Label(
            header,
            text="MAAZXDROID",
            bg=self.BACKGROUND,
            fg=self.ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="MAAZXDROID ANDROID",
            bg=self.BACKGROUND,
            fg=self.TEXT,
            font=("Segoe UI", 25, "bold"),
        ).pack(anchor="w", pady=(3, 0))
        tk.Label(
            header,
            text="A low-resource Android VM launcher. 60 FPS is a test target, not a guarantee.",
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        launch_panel = self._panel(outer)
        launch_panel.pack(fill="x", pady=(0, 14))
        tk.Label(
            launch_panel,
            text="ANDROID RUNTIME",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")

        self._path_row(
            launch_panel,
            "01  QEMU engine",
            self.qemu_path,
            "Browse",
            self._browse_qemu,
        )
        self._path_row(
            launch_panel,
            "02  Android image",
            self.android_image_path,
            "Browse",
            self._browse_android_image,
        )
        self._path_row(
            launch_panel,
            "03  User data",
            self.user_data_path,
            "Choose",
            self._choose_user_data,
        )

        vm_actions = tk.Frame(launch_panel, bg=self.PANEL)
        vm_actions.pack(fill="x", pady=(12, 0))
        tk.Label(
            vm_actions,
            text="04  LOW-END RAM PROFILE",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        self.memory_selector = ttk.Combobox(
            vm_actions,
            textvariable=self.vm_memory_mb,
            values=("1024", "1280", "1536", "2048"),
            state="readonly",
            width=8,
        )
        self.memory_selector.pack(side="left", padx=(0, 16))
        self._button(
            vm_actions, "Prepare Step 5", self._create_user_data, secondary=True
        ).pack(side="left", padx=(0, 8))
        self._button(
            vm_actions, "06  Start Android", self._start_android
        ).pack(side="left")
        tk.Label(
            launch_panel,
            text="Target: 60 FPS. Actual frame rate depends on the Android image, QEMU graphics, driver, and game.",
            bg=self.PANEL,
            fg=self.WARNING,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(10, 0))

        metrics_row = tk.Frame(outer, bg=self.BACKGROUND)
        metrics_row.pack(fill="x", pady=(0, 14))
        for column in range(3):
            metrics_row.columnconfigure(column, weight=1, uniform="metric")

        self.cpu_bar = self._metric_card(metrics_row, 0, 0, "SYSTEM CPU", self.cpu_text)
        self.core_bar = self._metric_card(metrics_row, 0, 1, "BUSIEST CPU CORE", self.core_text)
        self.memory_bar = self._metric_card(metrics_row, 0, 2, "AVAILABLE MEMORY", self.memory_text)
        self.pagefile_bar = self._metric_card(metrics_row, 1, 0, "PAGEFILE / SWAP USE", self.pagefile_text)
        self.disk_bar = self._metric_card(metrics_row, 1, 1, "DISK ACTIVITY", self.disk_text)
        capture_card = tk.Frame(metrics_row, bg=self.PANEL, padx=16, pady=15)
        capture_card.grid(row=1, column=2, sticky="nsew", padx=(7, 0), pady=(8, 0))
        tk.Label(
            capture_card,
            text="07  PERFORMANCE CAPTURE",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            capture_card,
            textvariable=self.capture_text,
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(10, 13))
        self.start_button = self._button(capture_card, "Start CSV capture", self._start_capture)
        self.start_button.pack(fill="x")
        self.stop_button = self._button(
            capture_card, "Stop capture", self._stop_capture, secondary=True
        )
        self.stop_button.pack(fill="x", pady=(7, 0))
        self.stop_button.configure(state="disabled")

        report_panel = self._panel(outer)
        report_panel.pack(fill="both", expand=True)
        report_header = tk.Frame(report_panel, bg=self.PANEL)
        report_header.pack(fill="x")
        tk.Label(
            report_header,
            text="SESSION NOTES",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        self.status_label = tk.Label(
            report_header,
            textvariable=self.status_text,
            bg=self.PANEL,
            fg=self.ACCENT,
            font=("Segoe UI", 9, "bold"),
        )
        self.status_label.pack(side="right")

        self.log = tk.Text(
            report_panel,
            height=8,
            bg=self.PANEL_ALT,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            wrap="word",
            font=("Consolas", 9),
            padx=12,
            pady=10,
            state="disabled",
        )
        self.log.pack(fill="both", expand=True, pady=(12, 0))
        self._log("Setup: select QEMU, Android image, and user-data path; then prepare the overlay.")
        if not Path(self.android_image_path.get()).is_file():
            self._log("Android system image is not installed yet; this alpha does not bundle one.")

        footer = tk.Label(
            outer,
            text="Android image and 3D acceleration are not included in this alpha; game compatibility is unverified.",
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        )
        footer.pack(anchor="w", pady=(12, 0))

    def _panel(self, parent):
        return tk.Frame(
            parent,
            bg=self.PANEL,
            padx=18,
            pady=16,
            highlightthickness=1,
            highlightbackground="#49325f",
        )

    def _path_row(self, parent, label, variable, button_text, command):
        row = tk.Frame(parent, bg=self.PANEL)
        row.pack(fill="x", pady=(8, 0))
        tk.Label(
            row,
            text=label,
            width=18,
            anchor="w",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 8))
        entry = tk.Entry(
            row,
            textvariable=variable,
            bg=self.PANEL_ALT,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            font=("Segoe UI", 9),
        )
        entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self._button(row, button_text, command, secondary=True).pack(side="left")
        return entry

    def _button(self, parent, text, command, secondary=False):
        background = self.PANEL_ALT if secondary else self.ACCENT
        foreground = self.TEXT if secondary else self.BACKGROUND
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=background,
            activeforeground=foreground,
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=9,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

    def _metric_card(self, parent, row, column, title, value):
        card = tk.Frame(parent, bg=self.PANEL, padx=16, pady=15)
        card.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 7, 7),
            pady=(0 if row == 0 else 8, 0),
        )
        tk.Label(
            card,
            text=title,
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            card,
            textvariable=value,
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(10, 11))
        bar = ttk.Progressbar(
            card,
            style="Resource.Horizontal.TProgressbar",
            maximum=100,
            mode="determinate",
        )
        bar.pack(fill="x")
        return bar

    def _browse_qemu(self):
        selected = filedialog.askopenfilename(
            title="Select QEMU system emulator",
            filetypes=(("QEMU emulator", "qemu-system-x86_64.exe"), ("Applications", "*.exe")),
        )
        if selected:
            self.qemu_path.set(selected)

    def _browse_android_image(self):
        selected = filedialog.askopenfilename(
            title="Select the MaazXdroid Android system image",
            filetypes=(("QEMU QCOW2 system images", "*.qcow2"),),
        )
        if selected:
            self.android_image_path.set(selected)

    def _choose_user_data(self):
        disk_path = Path(self.user_data_path.get()).expanduser()
        selected = filedialog.asksaveasfilename(
            title="Choose the Android user-data overlay location",
            defaultextension=".qcow2",
            initialdir=str(disk_path.parent),
            initialfile=disk_path.name,
            filetypes=(("QEMU virtual disks", "*.qcow2"),),
        )
        if selected:
            self.user_data_path.set(selected)

    def _create_user_data(self):
        qemu_path = Path(self.qemu_path.get().strip())
        qemu_img_name = "qemu-img.exe" if os.name == "nt" else "qemu-img"
        try:
            disk_path = create_data_overlay(
                qemu_path.with_name(qemu_img_name),
                Path(self.android_image_path.get().strip()),
                Path(self.user_data_path.get().strip()),
            )
        except (OSError, ValueError, VmConfigurationError) as error:
            messagebox.showerror("Could not prepare Android data", str(error))
            return
        self.status_text.set("Android data ready")
        self._log(f"Created writable user-data overlay: {disk_path}")

    def _start_android(self):
        try:
            qemu_path = Path(self.qemu_path.get().strip())
            disk_path = Path(self.user_data_path.get().strip())
            config = AndroidVmConfig(
                qemu_path=qemu_path,
                disk_path=disk_path,
                memory_mb=int(self.vm_memory_mb.get()),
                cpu_count=2,
            )
            arguments = config.build_arguments()
            subprocess.Popen(arguments, cwd=str(qemu_path.parent))
        except (OSError, ValueError, VmConfigurationError) as error:
            messagebox.showerror("Could not start Android VM", str(error))
            return
        self.status_text.set("MaazXdroid Android started")
        self._log(f"Started Android guest using writable data: {disk_path}")

    def _start_capture(self):
        selected = filedialog.asksaveasfilename(
            title="Save lobby performance capture",
            defaultextension=".csv",
            initialfile="maazxdroid-lobby-capture.csv",
            filetypes=(("CSV files", "*.csv"),),
        )
        if not selected:
            return
        try:
            self.capture_file = open(selected, "w", newline="", encoding="utf-8")
        except OSError as error:
            messagebox.showerror("Could not create capture", str(error))
            return

        try:
            self.telemetry = SystemTelemetry()
        except (OSError, psutil.Error) as error:
            self.capture_file.close()
            self.capture_file = None
            messagebox.showerror("Could not start telemetry", str(error))
            return

        self.capture_path = selected
        self.capture_writer = csv.writer(self.capture_file)
        core_count = psutil.cpu_count(logical=True) or 1
        self.capture_fields = [
            "timestamp",
            "system_cpu_percent",
            "busiest_core_percent",
            "memory_total_mb",
            "memory_available_mb",
            "memory_used_mb",
            "memory_percent",
            "pagefile_total_mb",
            "pagefile_used_mb",
            "pagefile_percent",
            "disk_read_mb_per_second",
            "disk_write_mb_per_second",
            "disk_busy_percent",
        ]
        self.capture_fields.extend(f"core_{index}_percent" for index in range(core_count))
        self.capture_writer.writerow(self.capture_fields)
        self.samples = []
        self.last_warnings.clear()
        self.stop_event.clear()
        self.capture_thread = threading.Thread(target=self._sample_resources, daemon=True)
        self.capture_thread.start()
        self.capture_text.set("Recording")
        self.status_text.set("Capture active")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._log(f"Started one-second system capture: {selected}")
        self.root.after(250, self._drain_samples)

    def _sample_resources(self):
        while not self.stop_event.wait(1):
            try:
                self.sample_queue.put(self.telemetry.sample())
            except (OSError, psutil.Error) as error:
                self.sample_queue.put(error)
                return

    def _drain_samples(self):
        while True:
            try:
                sample = self.sample_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(sample, Exception):
                self.status_text.set("Telemetry error")
                self.status_label.configure(fg=self.WARNING)
                self._log(f"Telemetry stopped: {sample}")
                self._stop_capture()
                return
            self.samples.append(sample)
            self._write_sample(sample)
        if self.capture_file:
            self.root.after(250, self._drain_samples)

    def _write_sample(self, sample):
        megabyte = 1024**2
        values = [
            sample.timestamp,
            f"{sample.cpu_percent:.1f}",
            f"{max(sample.core_cpu_percent, default=0.0):.1f}",
            f"{sample.memory_total_bytes / megabyte:.1f}",
            f"{sample.memory_available_bytes / megabyte:.1f}",
            f"{sample.memory_used_bytes / megabyte:.1f}",
            f"{sample.memory_percent:.1f}",
            f"{sample.pagefile_total_bytes / megabyte:.1f}",
            f"{sample.pagefile_used_bytes / megabyte:.1f}",
            f"{sample.pagefile_percent:.1f}",
            f"{sample.disk_read_bytes_per_second / megabyte:.3f}",
            f"{sample.disk_write_bytes_per_second / megabyte:.3f}",
            f"{sample.disk_busy_percent:.1f}",
        ]
        values.extend(f"{usage:.1f}" for usage in sample.core_cpu_percent)
        self.capture_writer.writerow(values)
        self.capture_file.flush()

        busiest_core = max(sample.core_cpu_percent, default=0.0)
        self.cpu_text.set(f"{sample.cpu_percent:.0f} %")
        self.cpu_bar["value"] = sample.cpu_percent
        self.core_text.set(f"{busiest_core:.0f} %")
        self.core_bar["value"] = busiest_core
        self.memory_text.set(
            f"{sample.memory_available_bytes / (1024 ** 3):.2f} GB free"
        )
        memory_pressure = 100 - sample.memory_available_bytes / sample.memory_total_bytes * 100
        self.memory_bar["value"] = memory_pressure
        self.pagefile_text.set(
            f"{sample.pagefile_used_bytes / (1024 ** 3):.2f} / "
            f"{sample.pagefile_total_bytes / (1024 ** 3):.2f} GB"
        )
        self.pagefile_bar["value"] = sample.pagefile_percent
        self.disk_text.set(
            f"R {sample.disk_read_bytes_per_second / megabyte:.2f} / "
            f"W {sample.disk_write_bytes_per_second / megabyte:.2f} MB/s"
        )
        self.disk_bar["value"] = sample.disk_busy_percent

        current_warnings = set(sample.warnings)
        for warning in current_warnings - self.last_warnings:
            self._log(f"WARNING: {warning}")
        self.last_warnings = current_warnings
        if current_warnings:
            self.status_text.set("Resource pressure detected")
            self.status_label.configure(fg=self.WARNING)
        else:
            self.status_text.set("Capture active")
            self.status_label.configure(fg=self.ACCENT)

    def _stop_capture(self):
        if not self.capture_file:
            return
        self.stop_event.set()
        if self.capture_thread:
            self.capture_thread.join(timeout=1.5)
        self.capture_thread = None
        while not self.sample_queue.empty():
            try:
                sample = self.sample_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(sample, Exception):
                self._log(f"Telemetry stopped: {sample}")
                continue
            self.samples.append(sample)
            self._write_sample(sample)
        self.capture_file.close()
        self.capture_file = None
        self.capture_writer = None
        self.capture_text.set("Saved")
        self.status_text.set("Capture complete")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if self.samples:
            average_cpu = sum(sample.cpu_percent for sample in self.samples) / len(self.samples)
            peak_cpu = max(sample.cpu_percent for sample in self.samples)
            lowest_available = min(sample.memory_available_bytes for sample in self.samples)
            self._log(
                f"Capture summary: {len(self.samples)} samples, CPU avg/peak "
                f"{average_cpu:.1f}%/{peak_cpu:.1f}%, lowest available RAM "
                f"{lowest_available / (1024 ** 3):.2f} GB."
            )
        self._log(f"Saved CSV: {self.capture_path}")

    def _log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", f"{time.strftime('%H:%M:%S')}  {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _close(self):
        if self.capture_file:
            self._stop_capture()
        self.root.destroy()


def main():
    root = tk.Tk()
    MaazXdroidApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()