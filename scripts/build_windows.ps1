$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $pythonCommand = Get-Command python -ErrorAction Stop
    $python = $pythonCommand.Source

    & $python -m pip install --upgrade pyinstaller Pillow
    if ($LASTEXITCODE -ne 0) { throw "Could not install Windows build dependencies." }

    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Could not install project dependencies." }

    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Unit tests failed; refusing to build the installer." }

    & $python scripts/create_icon.py
    if ($LASTEXITCODE -ne 0) { throw "Could not generate the application icon." }

    & $python -m PyInstaller --noconfirm --clean --onefile --windowed --name MaazXdroid --icon assets/maazxdroid.ico wsa_manager.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed to bundle the application." }

    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    $compilerCandidates = @(
        (Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $compiler = $compilerCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $compiler) {
        throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php and rerun this script."
    }

    & $compiler /Qp installer/MaazXdroid.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed to create the installer." }

    Write-Host "Installer created at dist\installer\MaazXdroidSetup.exe"
}
finally {
    Pop-Location
}