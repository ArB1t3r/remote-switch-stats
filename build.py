#!/usr/bin/env python3
"""
打包脚本 — 将 Switch Remote Control 打包为独立可执行文件。

用法:
    python build.py            # 默认打包
    python build.py --onedir   # 打包为文件夹模式（启动更快）

Windows 用户请直接双击 build_windows.bat，会自动处理所有环境依赖。
"""

import os
import sys

# CRITICAL: Strip polluted TCL/TK env vars BEFORE importing tkinter.
# Background: when this script is invoked from the auto-updater spawned by a
# running PyInstaller bundle, the bundle's runtime hook has set TCL_LIBRARY to
# point at the bundle's _internal/_tcl_data, which gets inherited by all child
# processes. tkinter.Tcl() then tries to initialize from that path and fails.
# Removing these env vars forces tkinter to use the system's default Python
# installation, which is what we want during the build.
for _polluted in ("TCL_LIBRARY", "TK_LIBRARY", "TCL_LIBRARY_PATH", "TIX_LIBRARY"):
    val = os.environ.pop(_polluted, None)
    if val:
        print(f"  [清理] 已移除污染的环境变量 {_polluted}={val}")

import argparse
import json
import platform
import shutil
import subprocess
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


def _find_tcl_tk_dirs() -> tuple[str, str]:
    """
    Locate TCL and TK data directories without creating a Tk window.
    Returns (tcl_lib_path, tk_lib_path). Either may be "" if not found.
    """
    tcl_lib = ""
    tk_lib = ""

    # Strategy 1: Use Tcl() interpreter (no display needed)
    try:
        import tkinter
        tcl = tkinter.Tcl()
        tcl_lib = os.path.abspath(tcl.eval("info library"))
        # TK library is usually a sibling directory
        try:
            tk_version = tcl.eval("package require Tk")
            tk_lib = os.path.join(os.path.dirname(tcl_lib), f"tk{tk_version}")
            if not os.path.isdir(tk_lib):
                major_minor = ".".join(tk_version.split(".")[:2])
                tk_lib = os.path.join(os.path.dirname(tcl_lib), f"tk{major_minor}")
        except Exception:
            # Tk package might not load without display, find tk dir by pattern
            parent = os.path.dirname(tcl_lib)
            for name in sorted(os.listdir(parent), reverse=True):
                if name.startswith("tk") and os.path.isdir(os.path.join(parent, name)):
                    tk_lib = os.path.join(parent, name)
                    break
        tcl.destroy()
        print(f"  [TCL/TK 定位] Strategy 1 - Tcl(): tcl={tcl_lib}, tk={tk_lib}")
    except Exception as e:
        print(f"  [TCL/TK 定位] Strategy 1 failed: {e}")

    # Strategy 2: Search common locations relative to sys.prefix
    if not tcl_lib or not os.path.isdir(tcl_lib):
        prefix = Path(sys.prefix)
        candidates = [
            prefix / "tcl",
            prefix / "lib",
            prefix / "Library" / "lib",
            prefix / "Lib",
        ]
        for base in candidates:
            if not base.is_dir():
                continue
            for d in sorted(base.iterdir(), reverse=True):
                if (d.name.startswith("tcl8") or d.name.startswith("tcl9")) and d.is_dir():
                    if (d / "init.tcl").exists():
                        tcl_lib = str(d.resolve())
                        print(f"  [TCL/TK 定位] Strategy 2 - found tcl: {tcl_lib}")
                        break
            if tcl_lib:
                break

    if not tk_lib or not os.path.isdir(tk_lib):
        if tcl_lib:
            parent = Path(tcl_lib).parent
            for d in sorted(parent.iterdir(), reverse=True):
                if (d.name.startswith("tk8") or d.name.startswith("tk9")) and d.is_dir():
                    tk_lib = str(d.resolve())
                    print(f"  [TCL/TK 定位] Strategy 2 - found tk: {tk_lib}")
                    break

    # Strategy 3: Use environment variables
    if not tcl_lib or not os.path.isdir(tcl_lib):
        env_tcl = os.environ.get("TCL_LIBRARY", "")
        if env_tcl and os.path.isdir(env_tcl):
            tcl_lib = os.path.abspath(env_tcl)
            print(f"  [TCL/TK 定位] Strategy 3 - env TCL_LIBRARY: {tcl_lib}")
    if not tk_lib or not os.path.isdir(tk_lib):
        env_tk = os.environ.get("TK_LIBRARY", "")
        if env_tk and os.path.isdir(env_tk):
            tk_lib = os.path.abspath(env_tk)
            print(f"  [TCL/TK 定位] Strategy 3 - env TK_LIBRARY: {tk_lib}")

    # Final validation: ensure both are absolute and exist
    if tcl_lib and not os.path.isabs(tcl_lib):
        tcl_lib = os.path.abspath(tcl_lib)
    if tk_lib and not os.path.isabs(tk_lib):
        tk_lib = os.path.abspath(tk_lib)

    return tcl_lib, tk_lib


def _ensure_tcl_tk_in_dist(dist_path: Path) -> None:
    """Post-build: verify TCL/TK data exists in dist, copy manually if missing."""
    internal = dist_path / "_internal"
    if not internal.is_dir():
        return

    tcl_dest = internal / "_tcl_data"
    tk_dest = internal / "_tk_data"

    if tcl_dest.is_dir() and tk_dest.is_dir():
        # Check they have content
        if any(tcl_dest.iterdir()) and any(tk_dest.iterdir()):
            print(f"  TCL/TK 数据已正确复制到 _internal/")
            return

    print(f"  [修复] TCL/TK 数据缺失，正在手动复制...")
    tcl_lib, tk_lib = _find_tcl_tk_dirs()

    if tcl_lib and os.path.isdir(tcl_lib):
        if tcl_dest.exists():
            shutil.rmtree(tcl_dest)
        shutil.copytree(tcl_lib, tcl_dest)
        print(f"  已复制 TCL: {tcl_lib} -> {tcl_dest}")
    else:
        print(f"  [错误] 无法找到 TCL 数据目录!")

    if tk_lib and os.path.isdir(tk_lib):
        if tk_dest.exists():
            shutil.rmtree(tk_dest)
        shutil.copytree(tk_lib, tk_dest)
        print(f"  已复制 TK: {tk_lib} -> {tk_dest}")
    else:
        print(f"  [错误] 无法找到 TK 数据目录!")


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

    # Bundle default page profiles + reference images
    defaults_dir = root / "assets" / "default_pages"
    if defaults_dir.is_dir():
        cmd.extend(["--add-data", f"{defaults_dir}{sep}assets/default_pages"])
        print(f"  默认页面配置: {defaults_dir}")

    # Include TCL/TK data (fixes "Tcl data directory not found" on Windows)
    # PyInstaller 6+ expects these at _tcl_data and _tk_data inside _internal/
    if is_win:
        print("\n  --- TCL/TK 数据定位 ---")
        tcl_lib, tk_lib = _find_tcl_tk_dirs()
        tcl_ok = tcl_lib and os.path.isdir(tcl_lib)
        tk_ok = tk_lib and os.path.isdir(tk_lib)

        if tcl_ok:
            add_data_tcl = f"{tcl_lib}{sep}_tcl_data"
            cmd.extend(["--add-data", add_data_tcl])
            print(f"  --add-data \"{add_data_tcl}\"")
        else:
            print(f"  [警告] TCL 数据目录未找到 (tcl_lib={tcl_lib!r})")

        if tk_ok:
            add_data_tk = f"{tk_lib}{sep}_tk_data"
            cmd.extend(["--add-data", add_data_tk])
            print(f"  --add-data \"{add_data_tk}\"")
        else:
            print(f"  [警告] TK 数据目录未找到 (tk_lib={tk_lib!r})")

        if not tcl_ok or not tk_ok:
            print(f"  构建后将尝试手动复制 (post-build fix)")
        print("  ---")

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

        # Post-build: ensure TCL/TK data is present (Windows onedir)
        if is_win and onedir and out.is_dir():
            _ensure_tcl_tk_in_dist(out)

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
