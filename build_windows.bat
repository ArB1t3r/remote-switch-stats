@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
title Switch Remote Control Builder
echo ============================================================
echo   Switch Remote Control - Windows Build Tool
echo ============================================================
echo.
echo [1/6] Detecting Python...
set "PY_CMD="
py --version >nul 2>&1
if !errorlevel! equ 0 (set "PY_CMD=py -3" & goto PY_OK)
python --version >nul 2>&1
if !errorlevel! equ 0 (set "PY_CMD=python" & goto PY_OK)
python3 --version >nul 2>&1
if !errorlevel! equ 0 (set "PY_CMD=python3" & goto PY_OK)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe" & goto PY_OK)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & goto PY_OK)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe" & goto PY_OK)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe" & goto PY_OK)
echo.
echo   [ERROR] Python not found!
echo.
echo   Please install Python 3.10+ from:
echo     https://www.python.org/downloads/
echo.
echo   IMPORTANT: Check these boxes during install:
echo     [x] Add Python to PATH
echo     [x] Install py launcher
echo.
pause
exit /b 1
:PY_OK
for /f "tokens=2 delims= " %%V in ('!PY_CMD! --version 2^>^&1') do set "PY_VER=%%V"
echo   Found Python !PY_VER! (cmd: !PY_CMD!)
echo.
echo [2/6] Checking tkinter...
!PY_CMD! -c "import tkinter" >nul 2>&1
if !errorlevel! neq 0 (
echo   [ERROR] tkinter not available!
echo   Re-run Python installer, click Modify, enable: tcl/tk and IDLE
echo.
pause
exit /b 1
)
echo   tkinter OK
echo.
echo [3/6] Setting up virtual environment...
if exist ".venv\Scripts\activate.bat" (
echo   .venv already exists, skipping
) else (
!PY_CMD! -m venv .venv
if !errorlevel! neq 0 (echo [ERROR] Failed to create venv & pause & exit /b 1)
echo   .venv created
)
call .venv\Scripts\activate.bat
echo.
echo [4/6] Installing project dependencies...
python -m pip install --upgrade pip -q 2>nul
pip install -r requirements.txt -q
if !errorlevel! neq 0 (echo [ERROR] Failed to install dependencies & pause & exit /b 1)
echo   Dependencies installed
echo.
echo [5/6] Installing PyInstaller...
pip install pyinstaller -q
if !errorlevel! neq 0 (echo [ERROR] Failed to install PyInstaller & pause & exit /b 1)
echo   PyInstaller installed
echo.
echo [6/6] Building executable...
echo.
python build.py
if !errorlevel! neq 0 (
echo.
echo   [ERROR] Build failed, check logs above
pause
exit /b 1
)
echo.
echo ============================================================
echo   BUILD COMPLETE!
echo.
echo   Output: dist\SwitchRemote.exe
echo.
echo   You can copy this .exe to any Windows PC.
echo   No Python or dependencies needed to run it.
echo ============================================================
echo.
set /p "RUN_NOW=Launch now? (Y/N): "
if /i "!RUN_NOW!"=="Y" (start "" "dist\SwitchRemote.exe")
pause
exit /b 0
