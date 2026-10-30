# MaazXdroid

MaazXdroid is a Windows desktop manager for a QEMU-based Android virtual machine. It does not launch or depend on GameLoop.

This repository contains the Windows manager and VM runtime prototype, not a new hypervisor or a finished custom Android distribution. The intended end-user flow is a prebuilt MaazXdroid QCOW2 system image plus a writable QCOW2 overlay; there is no Android system image artifact in the repository yet.

## Current Features

- Select a Windows QEMU executable and a MaazXdroid QCOW2 system image.
- Create a writable QCOW2 overlay backed by the system image without overwriting existing user data.
- Boot Android directly from the prepared system image and its writable overlay; no ISO or manual partitioning in the user flow.
- Configure guest memory from 1 GB to 2 GB in the UI; the low-end default is 1280 MB with two virtual CPUs.
- Capture aggregate/per-logical-core CPU, RAM, pagefile, and disk metrics to CSV while testing.

The VM uses WHPX acceleration and a standard virtual VGA device. WHPX requires Windows Hypervisor Platform support. The current graphics path does not provide verified 3D acceleration; many games may be slow or incompatible. ARM-only apps need a compatible translation layer, which this project does not include. The UI treats 60 FPS as a test target only, not a performance promise. The target laptop's panel is 60 Hz.

## Windows Requirements

- Windows 10/11 64-bit with Windows Hypervisor Platform available and enabled.
- A Windows QEMU distribution containing `qemu-system-x86_64.exe` and `qemu-img.exe` in the same folder.
- A MaazXdroid Android QCOW2 system image. The image build/distribution pipeline is not implemented yet, so the current app cannot boot Android until that artifact is supplied.
- For the target laptop: 4 GB RAM is tight. The 1280 MB default guest allocation may still cause host memory pressure; reduce it if Windows starts paging.

## Build and Install

Build the Windows installer on Windows (this Linux Codespaces workspace cannot produce a native Windows installer). Install Python 3.9+, Inno Setup 6, then run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build_windows.ps1
```

The output is `dist\installer\MaazXdroidSetup.exe`. It installs the MaazXdroid manager per-user. It does **not** bundle QEMU or Android system images in this milestone.

Alternatively, run the **Build Windows Installer** workflow in GitHub Actions and download its `MaazXdroidSetup` artifact.

## Intended First Boot Flow

1. Install the MaazXdroid manager and a compatible Windows QEMU build.
2. Obtain the versioned MaazXdroid Android QCOW2 image from the project release channel (not available yet).
3. Select QEMU and the system image, then prepare writable user data once.
4. Click **Start MaazXdroid** to boot Android directly. No ISO/partition screen should appear in the final UX.

Run the unit tests with `python -m unittest discover -s tests -v`. The VM command construction is tested in this repository; actual WHPX, Android boot, graphics, and game compatibility must be tested on the Windows laptop.

## Target Hardware Reality

The Vostro 3300 has an i3-M380, 4 GB RAM, first-generation Intel HD Graphics, a legacy WDDM 1.1 driver, and a 60 Hz display. A virtual Android guest adds overhead and the current virtual VGA does not pass the Intel GPU through to Android. A custom branded Android OS and gaming-grade GPU path would require separate Android image/build and graphics engineering; neither is included yet. No 100 FPS or game-compatibility guarantee is made.