# Switch Remote Control - Auto Updater (PowerShell)
# Downloads the latest source from GitHub and rebuilds the .exe
#
# Usage:
#   Right-click -> Run with PowerShell
#   or: powershell -ExecutionPolicy Bypass -File update_windows.ps1

$ErrorActionPreference = "Continue"

$OWNER = "ArB1t3r"
$REPO = "remote-switch-stats"
$BRANCH = "main"
$ZIP_URL = "https://github.com/$OWNER/$REPO/archive/refs/heads/$BRANCH.zip"
$TEMP_ZIP = "$env:TEMP\switch-remote-update.zip"
$TEMP_DIR = "$env:TEMP\switch-remote-update"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Switch Remote Control - Auto Updater" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Repository: $OWNER/$REPO"
Write-Host "  Branch:     $BRANCH"
Write-Host ""

# Step 1: Download latest source
Write-Host "[1/4] Downloading latest source code..." -ForegroundColor Yellow

try {
    if (Test-Path $TEMP_ZIP) { Remove-Item $TEMP_ZIP -Force }
    if (Test-Path $TEMP_DIR) { Remove-Item $TEMP_DIR -Recurse -Force }

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $ZIP_URL -OutFile $TEMP_ZIP -UseBasicParsing
    Write-Host "  Download complete" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Download failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please check your network connection and try again."
    Write-Host "  If in China, GitHub may be slow. Please retry later."
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 2: Extract and overwrite source
Write-Host ""
Write-Host "[2/4] Extracting and updating source files..." -ForegroundColor Yellow

try {
    Expand-Archive -Path $TEMP_ZIP -DestinationPath $TEMP_DIR -Force
    $extractedFolder = Get-ChildItem -Path $TEMP_DIR -Directory | Select-Object -First 1

    if (-not $extractedFolder) {
        throw "Cannot find extracted folder"
    }

    $sourceRoot = $extractedFolder.FullName
    $targetRoot = $PSScriptRoot

    $filesToCopy = @(
        "main.py",
        "build.py",
        "requirements.txt",
        "build_windows.bat",
        "build_windows.ps1",
        "update_windows.ps1"
    )

    foreach ($file in $filesToCopy) {
        $src = Join-Path $sourceRoot $file
        if (Test-Path $src) {
            Copy-Item -Path $src -Destination (Join-Path $targetRoot $file) -Force
            Write-Host "  Updated: $file" -ForegroundColor Gray
        }
    }

    $srcDir = Join-Path $sourceRoot "src"
    if (Test-Path $srcDir) {
        $targetSrc = Join-Path $targetRoot "src"
        if (Test-Path $targetSrc) { Remove-Item $targetSrc -Recurse -Force }
        Copy-Item -Path $srcDir -Destination $targetSrc -Recurse -Force
        Write-Host "  Updated: src/ (entire directory)" -ForegroundColor Gray
    }

    Write-Host "  Source files updated" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Extract/copy failed: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 3: Write build SHA from the downloaded commit
Write-Host ""
Write-Host "[3/4] Recording version info..." -ForegroundColor Yellow

try {
    $apiUrl = "https://api.github.com/repos/$OWNER/$REPO/commits/$BRANCH"
    $headers = @{ "User-Agent" = "SwitchRemote-Updater" }
    $response = Invoke-RestMethod -Uri $apiUrl -Headers $headers -UseBasicParsing
    $sha = $response.sha.Substring(0, 12)
    Set-Content -Path (Join-Path $targetRoot ".build_sha") -Value $sha -NoNewline
    Write-Host "  Version SHA: $sha" -ForegroundColor Green
} catch {
    Write-Host "  [WARNING] Could not fetch commit SHA: $_" -ForegroundColor DarkYellow
    Write-Host "  The update will still work, but version detection may be inaccurate."
}

# Step 4: Rebuild
Write-Host ""
Write-Host "[4/4] Rebuilding executable..." -ForegroundColor Yellow
Write-Host ""

$buildScript = Join-Path $targetRoot "build_windows.ps1"
if (Test-Path $buildScript) {
    & powershell -ExecutionPolicy Bypass -File $buildScript
} else {
    Write-Host "  [WARNING] build_windows.ps1 not found, attempting direct build..." -ForegroundColor DarkYellow
    python build.py
}

# Cleanup
Write-Host ""
Write-Host "Cleaning up temporary files..." -ForegroundColor Gray
if (Test-Path $TEMP_ZIP) { Remove-Item $TEMP_ZIP -Force -ErrorAction SilentlyContinue }
if (Test-Path $TEMP_DIR) { Remove-Item $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  UPDATE COMPLETE!" -ForegroundColor Green
Write-Host ""
Write-Host "  The new SwitchRemote.exe is in: dist\SwitchRemote.exe"
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

$run = Read-Host "Launch the updated app now? (Y/N)"
if ($run -eq "Y" -or $run -eq "y") {
    $exeDir = Join-Path $targetRoot "dist\SwitchRemote\SwitchRemote.exe"
    $exeFile = Join-Path $targetRoot "dist\SwitchRemote.exe"
    if (Test-Path $exeDir) {
        Start-Process $exeDir
    } elseif (Test-Path $exeFile) {
        Start-Process $exeFile
    } else {
        Write-Host "  [WARNING] Executable not found at expected path" -ForegroundColor DarkYellow
    }
}
