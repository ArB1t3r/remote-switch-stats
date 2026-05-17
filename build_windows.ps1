# Switch Remote Control - Windows Build Script (PowerShell)
# Usage: Right-click -> Run with PowerShell
#   or:  powershell -ExecutionPolicy Bypass -File build_windows.ps1

$ErrorActionPreference = "Continue"

# CRITICAL: Strip TCL/TK env vars (see comment in update_windows.ps1).
$envVarsToClean = @("TCL_LIBRARY", "TK_LIBRARY", "TCL_LIBRARY_PATH", "TIX_LIBRARY")
foreach ($v in $envVarsToClean) {
    if (Test-Path "Env:$v") {
        Write-Host "  [Cleanup] Removed inherited env: $v" -ForegroundColor DarkGray
        Remove-Item -Path "Env:$v"
    }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Switch Remote Control - Windows Build Tool" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# -- pip mirror: use Tsinghua mirror for faster downloads in China --
$PIP_MIRROR = "-i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn"

# Step 1: Find Python
Write-Host "[1/6] Detecting Python..." -ForegroundColor Yellow
$pycmd = $null

foreach ($cmd in @("py", "python", "python3")) {
    try {
        $null = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pycmd = $cmd
            break
        }
    } catch { }
}

if (-not $pycmd) {
    $searchPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
    )
    foreach ($p in $searchPaths) {
        if (Test-Path $p) {
            $pycmd = $p
            break
        }
    }
}

if (-not $pycmd) {
    Write-Host ""
    Write-Host "  [ERROR] Python not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please install Python 3.10+ from:"
    Write-Host "    https://www.python.org/downloads/" -ForegroundColor Blue
    Write-Host ""
    Write-Host "  IMPORTANT: Check these boxes during install:"
    Write-Host "    [x] Add Python to PATH"
    Write-Host "    [x] Install py launcher"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

$pyver = & $pycmd --version 2>&1
Write-Host "  Found $pyver (cmd: $pycmd)" -ForegroundColor Green

# Step 2: Check tkinter
Write-Host ""
Write-Host "[2/6] Checking tkinter..." -ForegroundColor Yellow
& $pycmd -c "import tkinter" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] tkinter not available!" -ForegroundColor Red
    Write-Host "  Re-run Python installer -> Modify -> enable: tcl/tk and IDLE"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "  tkinter OK" -ForegroundColor Green

# Step 3: Virtual environment
Write-Host ""
Write-Host "[3/6] Setting up virtual environment..." -ForegroundColor Yellow
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "  .venv already exists, skipping"
} else {
    Write-Host "  Creating .venv..."
    & $pycmd -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] Failed to create venv" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "  .venv created" -ForegroundColor Green
}

# Activate
& .venv\Scripts\Activate.ps1

# Step 4: Install dependencies
Write-Host ""
Write-Host "[4/6] Installing project dependencies..." -ForegroundColor Yellow
Write-Host "  (Using Tsinghua mirror for faster downloads)"
$pipCmd = "python -m pip install --upgrade pip $PIP_MIRROR"
Invoke-Expression $pipCmd 2>&1 | Out-Null
$pipCmd = "pip install -r requirements.txt $PIP_MIRROR"
Invoke-Expression $pipCmd
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "  Dependencies installed" -ForegroundColor Green

# Step 5: Install PyInstaller
Write-Host ""
Write-Host "[5/6] Installing PyInstaller..." -ForegroundColor Yellow
$pipCmd = "pip install pyinstaller $PIP_MIRROR"
Invoke-Expression $pipCmd
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Failed to install PyInstaller" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "  PyInstaller installed" -ForegroundColor Green

# Step 6: Build
Write-Host ""
Write-Host "[6/6] Building executable..." -ForegroundColor Yellow
Write-Host ""
python build.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  [ERROR] Build failed, check logs above" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
Write-Host ""
if (Test-Path "dist\SwitchRemote\SwitchRemote.exe") {
    Write-Host "  Output: dist\SwitchRemote\SwitchRemote.exe"
    Write-Host ""
    Write-Host "  Copy the entire 'dist\SwitchRemote' folder to any Windows PC."
    Write-Host "  Run SwitchRemote.exe inside that folder. No Python needed."
} else {
    Write-Host "  Output: dist\SwitchRemote.exe"
    Write-Host ""
    Write-Host "  You can copy this .exe to any Windows PC."
}
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

$exePath = if (Test-Path "dist\SwitchRemote\SwitchRemote.exe") { "dist\SwitchRemote\SwitchRemote.exe" } else { "dist\SwitchRemote.exe" }
$run = Read-Host "Launch now? (Y/N)"
if ($run -eq "Y" -or $run -eq "y") {
    Start-Process $exePath
}
