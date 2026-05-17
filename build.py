#!/usr/bin/env python3
"""
打包脚本 — 将 Switch Remote Control 打包为独立可执行文件。

用法:
    python build.py            # 默认打包
    python build.py --onedir   # 打包为文件夹模式（启动更快）

Windows 用户请直接双击 build_windows.bat，会自动处理所有环境依赖。
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

APP_NAME = "SwitchRemote"
ENTRY = "main.py"

HIDDEN_IMPORTS = [
    "customtkinter",
    "tkinter",
    "_tkinter",
    "tkinter.messagebox",
    "tkinter.filedialog",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
]

COLLECT_PACKAGES = [
    "customtkinter",
    "tkinter",
]


GITHUB_OWNER = "ArB1t3r"
GITHUB_REPO = "remote-switch-stats"


def write_build_sha(dist_path: Path) -> None:
    """Write current commit SHA to .build_sha in both project root and dist output."""
    sha = ""

    # Try git first
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()[:12]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: query GitHub API
    if not sha:
        try:
            url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/main"
            req = urllib.request.Request(url, headers={
                "User-Agent": "SwitchRemote-Build",
                "Accept": "application/vnd.github.v3+json",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                sha = data.get("sha", "")[:12]
        except Exception:
            pass

    if not sha:
        sha = "unknown"

    root = Path(__file__).parent.resolve()
    # Write to project root
    (root / ".build_sha").write_text(sha, encoding="utf-8")
    # Write to dist output (for bundled exe)
    dist_sha = dist_path / ".build_sha" if dist_path.is_dir() else dist_path.parent / ".build_sha"
    dist_sha.write_text(sha, encoding="utf-8")
    print(f"  Build SHA: {sha}")


def preflight_check() -> None:
    """Verify the environment before building."""
    errors: list[str] = []

    # Python version
    if sys.version_info < (3, 10):
        errors.append(
            f"Python 版本过低: {sys.version.split()[0]}，需要 3.10+"
        )

    # tkinter
    try:
        import tkinter  # noqa: F401
    except ImportError:
        errors.append(
            "tkinter 不可用。Windows 上请重新安装 Python 并勾选 tcl/tk 组件"
        )

    # pyinstaller
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        errors.append(
            "PyInstaller 未安装。请运行: pip install pyinstaller"
        )

    # project deps
    for mod_name, pkg_name in [("customtkinter", "customtkinter"), ("PIL", "Pillow")]:
        try:
            __import__(mod_name)
        except ImportError:
            errors.append(f"{pkg_name} 未安装。请运行: pip install -r requirements.txt")

    if errors:
        print("\n[环境检查失败]\n")
        for i, e in enumerate(errors, 1):
            print(f"  {i}. {e}")
        print()
        sys.exit(1)


def build(onedir: bool = False) -> None:
    preflight_check()

    root = Path(__file__).parent.resolve()
    entry = root / ENTRY

    if not entry.exists():
        print(f"[错误] 找不到入口文件: {entry}")
        sys.exit(1)

    is_mac = platform.system() == "Darwin"
    is_win = platform.system() == "Windows"

    # macOS: onefile+windowed is deprecated in PyInstaller 7
    if is_mac and not onedir:
        print("[提示] macOS 上自动切换为 onedir 模式")
        onedir = True

    # Windows: onedir is more reliable (avoids temp extraction issues with tkinter)
    if is_win and not onedir:
        print("[提示] Windows 上自动切换为 onedir 模式（避免 tkinter DLL 提取问题）")
        onedir = True

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        f"--name={APP_NAME}",
    ]

    if onedir:
        cmd.append("--onedir")
    else:
        cmd.append("--onefile")

    for pkg in COLLECT_PACKAGES:
        cmd.extend(["--collect-all", pkg])

    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])

    sep = ";" if is_win else ":"
    cmd.extend(["--add-data", f"src{sep}src"])

    # Include TCL/TK data (fixes "Tcl data directory not found" on Windows)
    if is_win:
        try:
            import tkinter
            tk_root = tkinter.Tk()
            tcl_lib = tk_root.tk.exprstring("$tcl_library")
            tk_lib = tk_root.tk.exprstring("$tk_library")
            tk_root.destroy()
            if os.path.isdir(tcl_lib):
                cmd.extend(["--add-data", f"{tcl_lib}{sep}tcl"])
            if os.path.isdir(tk_lib):
                cmd.extend(["--add-data", f"{tk_lib}{sep}tk"])
        except Exception:
            pass

    # Windows: embed icon if available
    icon_path = root / "assets" / "icon.ico"
    if is_win and icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    cmd.append(str(entry))

    print("=" * 60)
    print(f"  应用名称: {APP_NAME}")
    print(f"  打包模式: {'文件夹 (onedir)' if onedir else '单文件 (onefile)'}")
    print(f"  目标平台: {platform.system()} {platform.machine()}")
    print(f"  Python:   {sys.version.split()[0]}")
    print("=" * 60)
    print(f"\n执行命令:\n  {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(root))

    if result.returncode == 0:
        if onedir:
            out = root / "dist" / APP_NAME
        else:
            suffix = ".exe" if is_win else ""
            out = root / "dist" / f"{APP_NAME}{suffix}"

        write_build_sha(out)

        print("\n" + "=" * 60)
        print("  打包成功!")
        print(f"  输出路径: {out}")
        if not onedir and is_win:
            size_mb = out.stat().st_size / (1024 * 1024)
            print(f"  文件大小: {size_mb:.1f} MB")
        print("=" * 60)
    else:
        print(f"\n[错误] 打包失败，退出码: {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="打包 Switch Remote Control")
    parser.add_argument(
        "--onedir", action="store_true",
        help="使用文件夹模式（启动更快，但输出为整个目录）",
    )
    args = parser.parse_args()
    build(onedir=args.onedir)
