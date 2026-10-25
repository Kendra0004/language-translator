<#
.SYNOPSIS
  One-command Windows build: produces dist\LimitedTranslator\LimitedTranslator.exe

.PARAMETER OneFile
  Single .exe instead of a folder (takes a few seconds to unpack on start).

.PARAMETER Offline
  Bundle the offline translation engine (argostranslate + torch: ~1 GB extra).
  Without it the app still falls back offline later if you pip-install
  requirements-offline.txt into the build venv.

.EXAMPLE
  .\build.ps1              # normal (fast-starting) onedir build
  .\build.ps1 -OneFile     # single .exe
  .\build.ps1 -Offline     # include the offline translation engine
#>
param([switch]$OneFile, [switch]$Offline)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- pick a Python -------------------------------------------------------
$python = $null
foreach ($candidate in @("py", "python")) {
    try {
        & $candidate --version *> $null
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) { $python = $candidate; break }
    } catch { }
}
if (-not $python) {
    Write-Error "Python 3.10+ not found. Install it from https://python.org and re-run."
    exit 1
}

Write-Host "[1/4] Creating virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path ".venv-build")) {
    & $python -m venv .venv-build
}
$pip = ".\.venv-build\Scripts\pip.exe"
$pyi = ".\.venv-build\Scripts\pyinstaller.exe"

Write-Host "[2/4] Installing dependencies (PySide6 is ~200 MB, first run only)..." -ForegroundColor Cyan
& $pip install --upgrade pip
if ($Offline) {
    & $pip install -r requirements-offline.txt pyinstaller
} else {
    & $pip install -r requirements.txt pyinstaller
}

Write-Host "[3/4] Running tests..." -ForegroundColor Cyan
& $pip install pytest *> $null
& ".\.venv-build\Scripts\python.exe" -m pytest tests -q

Write-Host "[4/4] Building the exe..." -ForegroundColor Cyan
if ($OneFile) {
    & $pyi translator.spec --noconfirm --onefile
} else {
    & $pyi translator.spec --noconfirm
}

if (Test-Path "dist\LimitedTranslator\LimitedTranslator.exe") {
    Write-Host ""
    Write-Host "BUILD OK -> dist\LimitedTranslator\LimitedTranslator.exe" -ForegroundColor Green
    Write-Host "(onefile variant: dist\LimitedTranslator.exe)" -ForegroundColor DarkGray
} elseif (Test-Path "dist\LimitedTranslator.exe") {
    Write-Host ""
    Write-Host "BUILD OK -> dist\LimitedTranslator.exe" -ForegroundColor Green
} else {
    Write-Error "Build finished but no exe found - check the log above."
    exit 1
}
