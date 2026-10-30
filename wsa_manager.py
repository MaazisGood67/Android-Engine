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

from host_compatibility import assess_host
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
        self.installed_apps_text = tk.StringVar(value="Connect to WSA to inspect installed apps.")
        self.host_text = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready")
        self.action_queue = queue.Queue()
        self.action_busy = False

        total_memory = psutil.virtual_memory().total / (1024**3)
        self.host_text.set(f"Host RAM {total_memory:.1f} GB")
        self.low_memory = total_memory < 8.0
        self.low_end_mode = tk.BooleanVar(value=self.low_memory)
        self.current_page = None
        self.pages = {}
        self.nav_buttons = {}

        self._configure_styles()
        self._build_hub_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.after(150, self._poll_actions)
        self._apply_low_end_mode()
        self.root.after(1000, self._refresh_host_metrics)

    def _apply_low_end_mode(self):
        try:
            self.root.attributes("-alpha", 1.0 if self.low_end_mode.get() else 0.97)
        except tk.TclError:
            pass

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

    def _build_hub_ui(self):
        shell = tk.Frame(self.root, bg=self.BACKGROUND, padx=22, pady=18)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=self.BACKGROUND)
        header.pack(fill="x", pady=(0, 15))
        brand = tk.Frame(header, bg=self.BACKGROUND)
        brand.pack(side="left", fill="x", expand=True)
        tk.Label(
            brand,
            text="MAAZX GAMING HUB",
            bg=self.BACKGROUND,
            fg=self.ACCENT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            brand,
            text="Android Companion",
            bg=self.BACKGROUND,
            fg=self.TEXT,
            font=("Segoe UI", 21, "bold"),
        ).pack(anchor="w", pady=(2, 0))

        low_end_toggle = tk.Checkbutton(
            header,
            text="Low-End UI Mode",
            variable=self.low_end_mode,
            command=self._apply_low_end_mode,
            bg=self.BACKGROUND,
            fg=self.TEXT,
            activebackground=self.BACKGROUND,
            activeforeground=self.ACCENT,
            selectcolor=self.PANEL_ALT,
            font=("Segoe UI", 9, "bold"),
        )
        low_end_toggle.pack(side="right", padx=(10, 0))
        tk.Label(
            header,
            textvariable=self.status_text,
            bg=self.BACKGROUND,
            fg=self.ACCENT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        body = tk.Frame(shell, bg=self.BACKGROUND)
        body.pack(fill="both", expand=True)
        sidebar = tk.Frame(body, bg=self.PANEL, width=190, padx=10, pady=12)
        sidebar.pack(side="left", fill="y", padx=(0, 14))
        sidebar.pack_propagate(False)
        content = tk.Frame(body, bg=self.BACKGROUND)
        content.pack(side="left", fill="both", expand=True)

        for page_name in ("Dashboard", "Apps", "Performance", "Settings"):
            button = tk.Button(
                sidebar,
                text=page_name,
                command=lambda name=page_name: self._show_page(name),
                anchor="w",
                bg=self.PANEL_ALT,
                fg=self.TEXT,
                activebackground=self.ACCENT,
                activeforeground=self.BACKGROUND,
                relief="flat",
                borderwidth=0,
                padx=13,
                pady=11,
                cursor="hand2",
                font=("Segoe UI", 10, "bold"),
            )
            button.pack(fill="x", pady=3)
            self.nav_buttons[page_name] = button
            page = tk.Frame(content, bg=self.BACKGROUND)
            self.pages[page_name] = page

        self._build_dashboard_page(self.pages["Dashboard"])
        self._build_apps_page(self.pages["Apps"])
        self._build_performance_page(self.pages["Performance"])
        self._build_settings_page(self.pages["Settings"])
        self._show_page("Dashboard")

    def _page_heading(self, parent, title, description):
        tk.Label(
            parent,
            text=title,
            bg=self.BACKGROUND,
            fg=self.TEXT,
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w")
        tk.Label(
            parent,
            text=description,
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("Segoe UI", 9),
            wraplength=680,
            justify="left",
        ).pack(anchor="w", pady=(3, 12))

    def _build_dashboard_page(self, page):
        self._page_heading(
            page,
            "Configuration Panel",
            "Connect to WSA, inspect the Android image, and see which app services are present.",
        )
        status_panel = self._panel(page)
        status_panel.pack(fill="x", pady=(0, 10))
        tk.Label(
            status_panel,
            textvariable=self.device_text,
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        self.connect_button = self._button(status_panel, "Connect & inspect WSA", self._connect)
        self.connect_button.pack(anchor="w", pady=(9, 0))

        device_row = tk.Frame(page, bg=self.BACKGROUND)
        device_row.pack(fill="x", pady=(0, 10))
        for title, variable in (
            ("ANDROID", self.android_text),
            ("ABI", self.abi_text),
            ("GOOGLE SERVICES", self.gms_text),
        ):
            card = self._panel(device_row)
            card.pack(side="left", fill="both", expand=True, padx=(0, 7))
            tk.Label(
                card,
                text=title,
                bg=self.PANEL,
                fg=self.MUTED,
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor="w")
            tk.Label(
                card,
                textvariable=variable,
                bg=self.PANEL,
                fg=self.TEXT,
                wraplength=190,
                justify="left",
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w", pady=(8, 0))

        apps_panel = self._panel(page)
        apps_panel.pack(fill="both", expand=True)
        tk.Label(
            apps_panel,
            text="INSTALLED USER APPS",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            apps_panel,
            textvariable=self.installed_apps_text,
            bg=self.PANEL,
            fg=self.TEXT,
            justify="left",
            wraplength=680,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(10, 0))

        requirements = self._panel(page)
        requirements.pack(fill="x", pady=(0, 10))
        tk.Label(
            requirements,
            text="HOST COMPATIBILITY",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")
        for check in assess_host():
            color = self.WARNING if check.status not in {"OK", "MINIMUM ONLY"} else self.ACCENT
            tk.Label(
                requirements,
                text=f"{check.status}  {check.name}: {check.detail}",
                bg=self.PANEL,
                fg=color,
                wraplength=680,
                justify="left",
                font=("Segoe UI", 8),
            ).pack(anchor="w", pady=(5, 0))

    def _build_apps_page(self, page):
        self._page_heading(
            page,
            "App Configurations",
            "Sideload APKs into the connected WSA runtime. MaazXdroid does not bundle third-party app stores.",
        )
        install_panel = self._panel(page)
        install_panel.pack(fill="x", pady=(0, 10))
        tk.Label(
            install_panel,
            text="INSTALL A LOCAL APK",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        self.install_button = self._button(
            install_panel, "Browse APK and install", self._install_apk
        )
        self.install_button.pack(anchor="w", pady=(10, 0))

        stores = self._panel(page)
        stores.pack(fill="x", pady=(0, 10))
        tk.Label(
            stores,
            text="APP SOURCES",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        links = tk.Frame(stores, bg=self.PANEL)
        links.pack(anchor="w", pady=(10, 0))
        for title, url in (
            ("Uptodown", "https://en.uptodown.com/android"),
            ("APKMirror", "https://www.apkmirror.com/"),
            ("APKPure", "https://apkpure.com/"),
        ):
            self._button(
                links,
                title,
                lambda target=url: self._open_store(target),
                secondary=True,
            ).pack(side="left", padx=(0, 8))
        tk.Label(
            stores,
            text="Download only from sources you trust. Check APK signatures and ABI compatibility before installation.",
            bg=self.PANEL,
            fg=self.MUTED,
            wraplength=680,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(10, 0))

    def _build_performance_page(self, page):
        self._page_heading(
            page,
            "Performance Tuning",
            "The dashboard measures host load. WSA manages its own VM resources; MaazXdroid does not fake RAM/GPU controls.",
        )
        summary = self._panel(page)
        summary.pack(fill="x", pady=(0, 10))
        self.cpu_text = tk.StringVar(value="CPU --%")
        self.available_text = tk.StringVar(value="RAM available -- GB")
        for title, variable in (("SYSTEM CPU", self.cpu_text), ("AVAILABLE RAM", self.available_text)):
            item = tk.Frame(summary, bg=self.PANEL)
            item.pack(side="left", fill="x", expand=True)
            tk.Label(item, text=title, bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(item, textvariable=variable, bg=self.PANEL, fg=self.TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(6, 0))

        limits = self._panel(page)
        limits.pack(fill="x")
        checks = assess_host()
        ram_check = next(check for check in checks if check.name == "Memory")
        tk.Label(
            limits,
            text=f"{ram_check.detail} Low-End UI Mode reduces window translucency only; it does not tune WSA resources. 60 FPS is a test target, not a guarantee; GPU acceleration and Free Fire compatibility are unverified.",
            bg=self.PANEL,
            fg=self.WARNING,
            wraplength=680,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w")

    def _build_settings_page(self, page):
        self._page_heading(
            page,
            "Settings",
            "Connect MaazXdroid to an existing WSA installation. Windows/WSA setup remains separate.",
        )
        settings = self._panel(page)
        settings.pack(fill="x", pady=(0, 10))
        self._path_row(settings, "ADB executable", self.adb_path, "Browse", self._browse_adb)
        endpoint_row = tk.Frame(settings, bg=self.PANEL)
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
        self._button(endpoint_row, "Connect", self._connect).pack(side="left")
        self._button(
            settings,
            "Open WSA Settings",
            self._open_wsa_settings,
            secondary=True,
        ).pack(anchor="w", pady=(10, 0))
        notice = self._panel(page)
        notice.pack(fill="x")
        tk.Label(
            notice,
            text="WSAOnWin10 is archived and AGPL-3.0 licensed. Microsoft WSA and Google components keep their own terms. This manager does not install, rename, or redistribute those binaries.",
            bg=self.PANEL,
            fg=self.MUTED,
            wraplength=680,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w")

    def _show_page(self, name):
        if self.current_page:
            self.pages[self.current_page].pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        self.current_page = name
        for page_name, button in self.nav_buttons.items():
            selected = page_name == name
            button.configure(
                bg=self.ACCENT if selected else self.PANEL_ALT,
                fg=self.BACKGROUND if selected else self.TEXT,
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
        return message, controller.inspect(), controller.list_user_apps()

    def _install_apk(self):
        apk_path = filedialog.askopenfilename(
            title="Choose an Android APK",
            filetypes=(("Android packages", "*.apk"),),
        )
        if apk_path:
            self._submit("install", lambda: self._install_and_refresh(apk_path))

    def _install_and_refresh(self, apk_path):
        controller = self._controller()
        result = controller.install_apk(apk_path)
        return result, controller.list_user_apps()

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
            message, info, apps = result
            self._show_device(info)
            self._show_apps(apps)
            self.status_text.set("WSA connected")
            self.status_label.configure(fg=self.ACCENT)
            self._log(message)
        else:
            result, apps = result
            self._show_apps(apps)
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

    def _show_apps(self, package_names):
        if package_names:
            self.installed_apps_text.set("\n".join(package_names))
        else:
            self.installed_apps_text.set("No third-party packages reported by WSA.")

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
