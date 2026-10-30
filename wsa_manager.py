"""MaazXdroid companion UI for an already-installed Windows Subsystem for Android."""

import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

import psutil

from wsa_runtime import WsaController


class MaazXdroidWsaApp:
    BACKGROUND = "#100b1b"
    PANEL = "#1b1229"
    PANEL_ALT = "#26183a"
    TEXT = "#f5edff"
    MUTED = "#b6a4ca"
    ACCENT = "#d46bff"
    WARNING = "#ffc857"

    def __init__(self, root):
        self.root = root
        self.root.title("MaazXdroid | Android Companion")
        self.root.geometry("940x700")
        self.root.minsize(820, 620)
        self.root.configure(bg=self.BACKGROUND)
        try:
            self.root.attributes("-alpha", 0.97)
        except tk.TclError:
            pass

        self.window_icon = tk.PhotoImage(width=32, height=32)
        self.window_icon.put(self.BACKGROUND, to=(0, 0, 32, 32))
        for offset in range(5, 27):
            self.window_icon.put(self.ACCENT, to=(offset, offset, offset + 3, offset + 3))
            self.window_icon.put(self.ACCENT, to=(29 - offset, offset, 32 - offset, offset + 3))
        self.root.iconphoto(True, self.window_icon)

        self.adb_path = tk.StringVar(value=shutil.which("adb") or "")
        self.endpoint = tk.StringVar(value="127.0.0.1:58526")
        self.device_text = tk.StringVar(value="WSA not connected")
        self.android_text = tk.StringVar(value="Android: --")
        self.abi_text = tk.StringVar(value="ABI: --")
        self.gms_text = tk.StringVar(value="Google Play services: unknown")
        self.host_text = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready")
        self.action_queue = queue.Queue()
        self.action_busy = False

        total_memory = psutil.virtual_memory().total / (1024**3)
        self.host_text.set(f"Host RAM {total_memory:.1f} GB")
        self.low_memory = total_memory < 8.0

        self._configure_styles()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.after(150, self._poll_actions)
        self.root.after(1000, self._refresh_host_metrics)

    def _configure_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Neon.Horizontal.TProgressbar",
            troughcolor=self.PANEL_ALT,
            background=self.ACCENT,
            bordercolor=self.PANEL_ALT,
            lightcolor=self.ACCENT,
            darkcolor=self.ACCENT,
        )

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=self.BACKGROUND, padx=28, pady=22)
        outer.pack(fill="both", expand=True)

        tk.Label(
            outer,
            text="MAAZXDROID",
            bg=self.BACKGROUND,
            fg=self.ACCENT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            outer,
            text="Android app companion",
            bg=self.BACKGROUND,
            fg=self.TEXT,
            font=("Segoe UI", 25, "bold"),
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            outer,
            text="Connect to a separately installed Windows Subsystem for Android runtime.",
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 14))

        requirements = self._panel(outer)
        requirements.pack(fill="x", pady=(0, 12))
        tk.Label(
            requirements,
            textvariable=self.host_text,
            bg=self.PANEL,
            fg=self.WARNING if self.low_memory else self.ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        requirement_message = (
            "WSAOnWin10 documents 8 GB minimum RAM. This host is below that requirement; expect failures or severe paging."
            if self.low_memory
            else "WSA is discontinued upstream. This app does not install or modify WSA."
        )
        tk.Label(
            requirements,
            text=requirement_message,
            bg=self.PANEL,
            fg=self.MUTED,
            justify="left",
            wraplength=820,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        runtime = self._panel(outer)
        runtime.pack(fill="x", pady=(0, 12))
        tk.Label(
            runtime,
            text="01  CONNECT TO WSA",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        self._path_row(runtime, "ADB executable", self.adb_path, "Browse", self._browse_adb)

        endpoint_row = tk.Frame(runtime, bg=self.PANEL)
        endpoint_row.pack(fill="x", pady=(8, 0))
        tk.Label(
            endpoint_row,
            text="ADB endpoint",
            width=18,
            anchor="w",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 8))
        tk.Entry(
            endpoint_row,
            textvariable=self.endpoint,
            bg=self.PANEL_ALT,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            font=("Segoe UI", 9),
        ).pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self.connect_button = self._button(endpoint_row, "Connect & inspect", self._connect)
        self.connect_button.pack(side="left")

        runtime_actions = tk.Frame(runtime, bg=self.PANEL)
        runtime_actions.pack(fill="x", pady=(10, 0))
        self._button(
            runtime_actions,
            "Open WSA Settings",
            self._open_wsa_settings,
            secondary=True,
        ).pack(side="left")
        tk.Label(
            runtime_actions,
            textvariable=self.device_text,
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(14, 0))

        device_info = tk.Frame(runtime, bg=self.PANEL_ALT, padx=12, pady=9)
        device_info.pack(fill="x", pady=(10, 0))
        for variable in (self.android_text, self.abi_text, self.gms_text):
            tk.Label(
                device_info,
                textvariable=variable,
                bg=self.PANEL_ALT,
                fg=self.MUTED,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(0, 22))

        apk_panel = self._panel(outer)
        apk_panel.pack(fill="x", pady=(0, 12))
        tk.Label(
            apk_panel,
            text="02  INSTALL ANDROID APPS",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        store_buttons = tk.Frame(apk_panel, bg=self.PANEL)
        store_buttons.pack(fill="x", pady=(10, 0))
        self.install_button = self._button(store_buttons, "Select APK to install", self._install_apk)
        self.install_button.pack(side="left", padx=(0, 8))
        self._button(
            store_buttons,
            "Uptodown",
            lambda: self._open_store("https://en.uptodown.com/android"),
            secondary=True,
        ).pack(side="left", padx=(0, 8))
        self._button(
            store_buttons,
            "APKMirror",
            lambda: self._open_store("https://www.apkmirror.com/"),
            secondary=True,
        ).pack(side="left")
        tk.Label(
            apk_panel,
            text="Google sign-in requires Google Play services in the WSA image. Play Store is detected separately; APKs are installed only when you select them.",
            bg=self.PANEL,
            fg=self.MUTED,
            wraplength=820,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(9, 0))

        performance = self._panel(outer)
        performance.pack(fill="x", pady=(0, 12))
        performance_header = tk.Frame(performance, bg=self.PANEL)
        performance_header.pack(fill="x")
        tk.Label(
            performance_header,
            text="03  PERFORMANCE CHECK",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        self.status_label = tk.Label(
            performance_header,
            textvariable=self.status_text,
            bg=self.PANEL,
            fg=self.ACCENT,
            font=("Segoe UI", 9, "bold"),
        )
        self.status_label.pack(side="right")
        metrics = tk.Frame(performance, bg=self.PANEL)
        metrics.pack(fill="x", pady=(9, 8))
        self.cpu_text = tk.StringVar(value="CPU --%")
        self.available_text = tk.StringVar(value="RAM available -- GB")
        tk.Label(
            metrics,
            textvariable=self.cpu_text,
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=(0, 24))
        tk.Label(
            metrics,
            textvariable=self.available_text,
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")
        tk.Label(
            performance,
            text="60 FPS is a test target, not a guarantee. A 60 Hz display cannot show more than 60 refreshes per second.",
            bg=self.PANEL,
            fg=self.WARNING,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(8, 0))

        self.log = tk.Text(
            outer,
            height=5,
            bg=self.PANEL_ALT,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            wrap="word",
            font=("Consolas", 9),
            padx=10,
            pady=8,
            state="disabled",
        )
        self.log.pack(fill="both", expand=True)
        self._log("WSA companion only: WSA, Google apps, and APK stores are not bundled.")
        self._log("Use trusted APK sources and verify signatures before installing.")

    def _panel(self, parent):
        return tk.Frame(
            parent,
            bg=self.PANEL,
            padx=16,
            pady=13,
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
        tk.Entry(
            row,
            textvariable=variable,
            bg=self.PANEL_ALT,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            font=("Segoe UI", 9),
        ).pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self._button(row, button_text, command, secondary=True).pack(side="left")

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
            padx=13,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        )

    def _controller(self):
        return WsaController(self.adb_path.get().strip(), self.endpoint.get().strip())

    def _browse_adb(self):
        selected = filedialog.askopenfilename(
            title="Select Android Platform Tools adb.exe",
            filetypes=(("ADB executable", "adb.exe"), ("Applications", "*.exe")),
        )
        if selected:
            self.adb_path.set(selected)

    def _open_wsa_settings(self):
        if os.name != "nt":
            messagebox.showinfo("Windows only", "Open WSA Settings from the Windows Start menu.")
            return
        app_id = "shell:AppsFolder\\MicrosoftCorporationII.WindowsSubsystemForAndroid_8wekyb3d8bbwe!Settings"
        try:
            subprocess.Popen(["explorer.exe", app_id], shell=False)
        except OSError as error:
            messagebox.showerror("Could not open WSA Settings", str(error))

    def _connect(self):
        self._submit("connect", self._connect_and_inspect)

    def _connect_and_inspect(self):
        controller = self._controller()
        message = controller.connect()
        return message, controller.inspect()

    def _install_apk(self):
        apk_path = filedialog.askopenfilename(
            title="Choose an Android APK",
            filetypes=(("Android packages", "*.apk"),),
        )
        if apk_path:
            self._submit("install", lambda: self._controller().install_apk(apk_path))

    def _open_store(self, url):
        webbrowser.open(url, new=2)

    def _submit(self, action, callback):
        if self.action_busy:
            return
        self.action_busy = True
        self.status_text.set("Working...")
        self.connect_button.configure(state="disabled")
        self.install_button.configure(state="disabled")

        def worker():
            try:
                self.action_queue.put((action, callback(), None))
            except Exception as error:
                self.action_queue.put((action, None, error))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_actions(self):
        try:
            action, result, error = self.action_queue.get_nowait()
        except queue.Empty:
            self.root.after(150, self._poll_actions)
            return

        self.action_busy = False
        self.connect_button.configure(state="normal")
        self.install_button.configure(state="normal")
        if error:
            self.status_text.set("Action failed")
            self.status_label.configure(fg=self.WARNING)
            self._log(f"{action.title()} failed: {error}")
            messagebox.showerror("MaazXdroid action failed", str(error))
        elif action == "connect":
            message, info = result
            self._show_device(info)
            self.status_text.set("WSA connected")
            self.status_label.configure(fg=self.ACCENT)
            self._log(message)
        else:
            self.status_text.set("APK installed")
            self.status_label.configure(fg=self.ACCENT)
            self._log(result or "ADB reported successful APK installation.")
        self.root.after(150, self._poll_actions)

    def _show_device(self, info):
        self.device_text.set(f"Connected: {info.serial}")
        self.android_text.set(f"Android: {info.android_release}")
        self.abi_text.set(f"ABI: {info.cpu_abi}")
        if info.has_google_play_services:
            store_state = "Play Store present" if info.has_play_store else "Play Store absent"
            self.gms_text.set(f"Google sign-in: services present; {store_state}")
        else:
            self.gms_text.set("Google sign-in: Play services not detected")

    def _refresh_host_metrics(self):
        memory = psutil.virtual_memory()
        self.cpu_text.set(f"CPU {psutil.cpu_percent(interval=None):.0f}%")
        self.available_text.set(f"RAM available {memory.available / (1024**3):.2f} GB")
        self.root.after(1000, self._refresh_host_metrics)

    def _log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", f"{message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")


def main():
    root = tk.Tk()
    MaazXdroidWsaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
