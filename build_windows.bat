@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================
::  Switch Remote Control — Windows 一键打包脚本
::  双击运行即可，自动处理全部环境依赖。
:: ============================================================

title Switch Remote Control - 打包工具

echo ============================================================
echo   Switch Remote Control — Windows 一键打包
echo ============================================================
echo.

:: ── 第1步：检测 Python ─────────────────────────────────────

echo [1/6] 检测 Python 环境...

:: 按优先级尝试多种 Python 命令
set "PY_CMD="

:: 优先使用 py launcher (Windows 官方安装器自带)
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py -3"
    goto :py_found
)

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :py_found
)

python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python3"
    goto :py_found
)

:: 检查常见安装路径
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (
        set "PY_CMD=%%~P"
        goto :py_found
    )
)

:: Python 未找到 — 提示安装
echo.
echo   [错误] 未检测到 Python！
echo.
echo   请先安装 Python 3.10 或更高版本:
echo     下载地址: https://www.python.org/downloads/
echo.
echo   安装时请务必勾选:
echo     [x] Add Python to PATH
echo     [x] Install py launcher
echo.
echo   安装完成后重新运行此脚本。
echo.
pause
exit /b 1

:py_found

:: 验证版本 >= 3.10
for /f "tokens=2 delims= " %%V in ('%PY_CMD% --version 2^>^&1') do set "PY_VER=%%V"
for /f "tokens=1,2 delims=." %%A in ("%PY_VER%") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)

if %PY_MAJOR% lss 3 goto :py_too_old
if %PY_MAJOR% equ 3 if %PY_MINOR% lss 10 goto :py_too_old
goto :py_version_ok

:py_too_old
echo.
echo   [错误] Python 版本过低: %PY_VER%
echo   需要 Python 3.10 或更高版本。
echo   下载地址: https://www.python.org/downloads/
echo.
pause
exit /b 1

:py_version_ok
echo   已找到 Python %PY_VER%  (命令: %PY_CMD%)

:: ── 第2步：检测 tkinter ───────────────────────────────────

echo.
echo [2/6] 检测 tkinter 模块...

%PY_CMD% -c "import tkinter; print('tkinter OK')" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   [错误] tkinter 模块不可用！
    echo.
    echo   这通常是因为安装 Python 时没有勾选 tcl/tk 组件。
    echo   请重新运行 Python 安装程序，选择 "Modify"，确保勾选:
    echo     [x] tcl/tk and IDLE
    echo.
    echo   或者重新下载安装，使用默认选项即可。
    echo.
    pause
    exit /b 1
)
echo   tkinter 可用

:: ── 第3步：创建虚拟环境 ───────────────────────────────────

echo.
echo [3/6] 准备虚拟环境...

if exist ".venv\Scripts\activate.bat" (
    echo   虚拟环境已存在，跳过创建
) else (
    echo   正在创建虚拟环境...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo   [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo   虚拟环境创建成功
)

:: 激活虚拟环境
call .venv\Scripts\activate.bat

:: ── 第4步：安装依赖 ───────────────────────────────────────

echo.
echo [4/6] 安装项目依赖...

python -m pip install --upgrade pip --quiet 2>nul
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo   [错误] 安装项目依赖失败
    pause
    exit /b 1
)
echo   项目依赖安装完成

:: ── 第5步：安装 PyInstaller ───────────────────────────────

echo.
echo [5/6] 安装 PyInstaller...

pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo   [错误] 安装 PyInstaller 失败
    pause
    exit /b 1
)
echo   PyInstaller 安装完成

:: ── 第6步：执行打包 ──────────────────────────────────────

echo.
echo [6/6] 开始打包...
echo.

python build.py
if %errorlevel% neq 0 (
    echo.
    echo   [错误] 打包失败，请检查上方日志
    pause
    exit /b 1
)

:: ── 完成 ──────────────────────────────────────────────────

echo.
echo ============================================================
echo   全部完成！
echo.
echo   可执行文件位于:
echo     dist\SwitchRemote.exe
echo.
echo   你可以将此 .exe 复制到任意 Windows 电脑上运行，
echo   无需安装 Python 或任何依赖。
echo ============================================================
echo.

:: 询问是否立即运行
set /p "RUN_NOW=是否立即运行？(Y/N): "
if /i "%RUN_NOW%"=="Y" (
    echo.
    echo 正在启动 SwitchRemote...
    start "" "dist\SwitchRemote.exe"
)

pause
exit /b 0
