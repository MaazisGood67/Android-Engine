# MaazXdroid

MaazXdroid is a purple-glass Windows companion for an already-installed Windows Subsystem for Android (WSA) runtime. Its hub has Dashboard, Apps, Performance, and Settings pages; it connects through standard ADB, reports Android/ABI/Google Play Services status, lists user-installed packages, and sideloads an APK selected by the user. Uptodown, APKPure, and APKMirror buttons open their websites; their apps/APKs are not bundled.

This is not a custom Android OS image and does not install or modify WSA. The cloned upstream WSAOnWin10 repository is kept under `upstream/WSAOnWin10/` for local reference and ignored by the MaazXdroid Git repository. It is archived, AGPL-3.0 licensed, and contains/depends on separate Microsoft WSA components. Do not remove upstream copyright/license notices or redistribute Microsoft/Google payloads without appropriate rights.

## Runtime Requirements

- Windows 10 build and updates supported by the selected WSAOnWin10 release, with virtualization enabled.
- WSA installed separately; enable Developer mode and use its displayed ADB endpoint.
- Android Platform Tools (`adb.exe`).
- The WSAOnWin10 project documents 8 GB RAM minimum and 16 GB recommended. This Vostro has 4 GB and is below that minimum; expect paging, failed starts, or severe slowdown.

WSA was discontinued by Microsoft in 2025, and the WSAOnWin10 repository is archived with its latest listed build from 2024. MaazXdroid does not make this stack supported or update its Android security patches.

## Use

1. Install and start a compatible WSA build separately; open WSA Settings and enable Developer mode.
2. Launch MaazXdroid, select `adb.exe`, enter the ADB endpoint shown by WSA, and connect.
3. Check Android ABI and Google Play Services status. Gmail sign-in inside an app requires compatible Google Play Services in that WSA image; this app cannot add them.
4. Choose a trusted `.apk` file and install it through ADB, or open Uptodown/APKPure/APKMirror in a browser.

The low-end UI toggle removes window translucency to reduce desktop composition overhead; it does not tune WSA's VM or GPU. The Performance page reports host CPU and available RAM only. Google sign-in requires a WSA image that includes compatible Google Play Services; the manager only detects whether services and Play Store are present.

The manager does not root WSA, inject DLLs, modify game files, or bypass anti-cheat. Free Fire compatibility and frame rate are not verified. The UI's 60 FPS text is a test target only, not a guarantee; this host has 4 GB RAM, legacy Intel HD graphics, and a 60 Hz display.

## Build MaazXdroidSetup.exe

Build on Windows with Python 3.9+ and Inno Setup 6:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build_windows.ps1
```

The setup installs the MaazXdroid companion UI only; it does not bundle WSA, Google apps, APK stores, or a game. End users install MaazXdroid through the graphical setup wizard; PowerShell is only used by developers/CI to build the installer.

Run the test suite with `python -m unittest discover -s tests -v`. Actual WSA connection and game tests require a compatible Windows machine.