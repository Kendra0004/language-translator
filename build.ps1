<#
.SYNOPSIS
  One-command Windows build: produces dist\LanguageTranslator\LanguageTranslator.exe

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

  If PowerShell blocks the script, run:
  powershell -ExecutionPolicy Bypass -File .\build.ps1
#>
param([switch]$OneFile, [switch]$Offline)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Fail([string]$Msg) {
    Write-Host ""
    Write-Host "ERROR: $Msg" -ForegroundColor Red
    exit 1
}

# Run a native command and stop WITH CONTEXT when it fails. Plain
# $ErrorActionPreference="Stop" does not catch non-zero exit codes of
# pip/pyinstaller, which used to cascade into confusing later errors.
function Step([string]$What, [scriptblock]$Block) {
    & $Block
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Fail "$What failed (exit code $LASTEXITCODE) - see the output above."
    }
}

# --- pick a Python --------------------------------------------------------
# editdistance (an epitran dependency) is at its final release 0.8.1 with
# prebuilt Windows wheels only up to Python 3.12. On 3.13 pip would have to
# compile C code, which needs the MSVC Build Tools - so prefer 3.10-3.12.
function Get-PyMajorMinor([string]$exe, [string[]]$preArgs) {
    try {
        $out = & $exe @preArgs "--version" 2>&1
    } catch { return $null }
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { return $null }
    if ("$out" -match "Python 3\.(\d+)") { return [int]$Matches[1] }
    return $null
}

$python = $null
$pythonArgs = @()
$newerSeen = $null
foreach ($candidate in @(
        @("py", @("-3.12")),
        @("py", @("-3.11")),
        @("py", @("-3.10")),
        @("py", @("-3")),
        @("python", @())
    )) {
    $ver = Get-PyMajorMinor $candidate[0] $candidate[1]
    if ($null -eq $ver) { continue }
    if ($ver -le 12) {
        $python = $candidate[0]
        $pythonArgs = $candidate[1]
        break
    }
    if ($null -eq $newerSeen) { $newerSeen = $ver }
}

if (-not $python) {
    if ($null -ne $newerSeen) {
        Fail ("Python $newerSeen found, but Python 3.10-3.12 is required on Windows: " +
              "the 'editdistance' dependency has no prebuilt wheel for Python 3.13+, " +
              "so installing it would need the MSVC Build Tools.`n" +
              "Install Python 3.12 from https://www.python.org/downloads/ " +
              "(tick 'Add python.exe to PATH', prefer the python.org installer over the " +
              "Microsoft Store one) and re-run this script.")
    }
    Fail "Python 3.10-3.12 not found. Install it from https://www.python.org/downloads/ and re-run."
}

function Invoke-Py([string[]]$PyArgs) {
    if ($pythonArgs.Count -gt 0) { & $python @pythonArgs @PyArgs }
    else { & $python @PyArgs }
}

Write-Host "Using: $python $($pythonArgs -join ' ')" -ForegroundColor DarkGray

Write-Host "[1/5] Creating virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path ".venv-build")) {
    Step "venv creation" { Invoke-Py @("-m", "venv", ".venv-build") }
}
$pip = ".\.venv-build\Scripts\pip.exe"
$pyi = ".\.venv-build\Scripts\pyinstaller.exe"
$venvPy = ".\.venv-build\Scripts\python.exe"

Write-Host "[2/5] Installing dependencies (PySide6 is ~200 MB, first run only)" -ForegroundColor Cyan
# Self-upgrade is best-effort: it needs the package index, but once
# .venv-build exists the build must also succeed with no network at all
# (everything else below is already satisfied locally), so a failure here
# must warn instead of aborting like a real Step.
& $pip install --upgrade pip --retries 1 --timeout 5
if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Host "  (pip self-upgrade skipped - no network?)" -ForegroundColor DarkYellow
}
if ($Offline) {
    Step "dependency install" { & $pip install -r requirements-offline.txt pyinstaller }
} else {
    Step "dependency install" { & $pip install -r requirements.txt pyinstaller }
}

Write-Host "[3/5] Running tests..." -ForegroundColor Cyan
Step "pytest install" { & $pip install pytest *> $null }
Step "tests" { & $venvPy -m pytest tests -q }

Write-Host "[4/5] Building the exe..." -ForegroundColor Cyan
# PyInstaller rejects --onefile whenever a .spec file is given, so the spec
# reads LT_ONEFILE from the environment instead.
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
if ($OneFile) { $env:LT_ONEFILE = "1" }
else { Remove-Item Env:LT_ONEFILE -ErrorAction SilentlyContinue }
Step "PyInstaller build" { & $pyi translator.spec --noconfirm }

if ($OneFile) { $bin = "dist\LanguageTranslator.exe" }
else { $bin = "dist\LanguageTranslator\LanguageTranslator.exe" }
if (-not (Test-Path $bin)) { Fail "Build finished but no exe found at $bin - check the log above." }
Write-Host ""
Write-Host "BUILD OK -> $bin" -ForegroundColor Green

Write-Host "[5/5] Smoke-testing the exe (startup + pronunciation panel)..." -ForegroundColor Cyan
$smokeLog = Join-Path (Get-Location) "smoke.log"
Remove-Item $smokeLog -ErrorAction SilentlyContinue
$env:LT_SMOKE = "1"
$env:LT_SMOKE_LOG = $smokeLog
$env:QT_QPA_PLATFORM = "offscreen"
$proc = Start-Process -FilePath $bin -Wait -PassThru
Remove-Item Env:LT_SMOKE, Env:LT_SMOKE_LOG, Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
if (Test-Path $smokeLog) { Get-Content $smokeLog | ForEach-Object { Write-Host $_ } }
if ($proc.ExitCode -ne 0) {
    Fail "smoke test failed (exit code $($proc.ExitCode)) - the exe starts but something inside is broken (see above)."
}
Write-Host "SMOKE OK" -ForegroundColor Green
