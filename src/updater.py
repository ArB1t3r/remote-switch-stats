"""Auto-update checker — compares local build SHA against GitHub main branch."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src import GITHUB_OWNER, GITHUB_REPO, APP_VERSION

GITHUB_API_URLS = [
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/main",
    f"https://ghfast.top/https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/main",
]

BUILD_SHA_FILE = ".build_sha"


@dataclass
class UpdateInfo:
    available: bool
    remote_sha: str = ""
    local_sha: str = ""
    message: str = ""
    commit_date: str = ""


def _get_local_sha() -> str:
    """Read the local build SHA from the .build_sha file next to the executable or in the project root."""
    candidates = [
        Path(getattr(sys, "_MEIPASS", "")) / BUILD_SHA_FILE,
        Path(sys.executable).parent / BUILD_SHA_FILE,
        Path(__file__).resolve().parent.parent / BUILD_SHA_FILE,
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return ""


def _fetch_latest_commit() -> dict:
    """Fetch the latest commit info from GitHub API. Tries mirror if direct access fails."""
    last_error: Exception | None = None
    for url in GITHUB_API_URLS:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": f"SwitchRemote/{APP_VERSION}",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            continue
    raise last_error or RuntimeError("所有 API 地址均不可用")


def check_for_update() -> UpdateInfo:
    """Synchronous update check. Returns UpdateInfo with comparison result."""
    local_sha = _get_local_sha()

    try:
        data = _fetch_latest_commit()
    except Exception as exc:
        return UpdateInfo(
            available=False,
            local_sha=local_sha,
            message=f"检查更新失败: {exc}",
        )

    remote_sha = data.get("sha", "")[:12]
    commit_msg = data.get("commit", {}).get("message", "").split("\n")[0]
    commit_date = data.get("commit", {}).get("committer", {}).get("date", "")[:10]

    if not local_sha:
        return UpdateInfo(
            available=True,
            remote_sha=remote_sha,
            local_sha="(未记录)",
            message=commit_msg,
            commit_date=commit_date,
        )

    if local_sha[:12] != remote_sha[:12]:
        return UpdateInfo(
            available=True,
            remote_sha=remote_sha,
            local_sha=local_sha[:12],
            message=commit_msg,
            commit_date=commit_date,
        )

    return UpdateInfo(
        available=False,
        remote_sha=remote_sha,
        local_sha=local_sha[:12],
        message="已是最新版本",
    )


def check_for_update_async(callback: Callable[[UpdateInfo], None]) -> None:
    """Run the update check in a background thread, then call `callback` with the result."""
    def _worker() -> None:
        info = check_for_update()
        callback(info)
    threading.Thread(target=_worker, daemon=True).start()


def _find_update_script() -> Path | None:
    """Locate update_windows.ps1 by checking multiple candidate directories."""
    exe_dir = Path(sys.executable).parent
    candidates = [
        exe_dir / "update_windows.ps1",
        exe_dir.parent / "update_windows.ps1",
        exe_dir.parent.parent / "update_windows.ps1",
        Path(__file__).resolve().parent.parent / "update_windows.ps1",
    ]
    if hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.insert(0, meipass.parent / "update_windows.ps1")
        candidates.insert(1, meipass.parent.parent / "update_windows.ps1")

    for path in candidates:
        if path.exists():
            return path
    return None


def launch_updater_script() -> bool:
    """Launch the update_windows.ps1 script as a separate process. Returns True if launched."""
    if platform.system() != "Windows":
        return False

    script = _find_update_script()
    if not script:
        return False

    subprocess.Popen(
        [
            "powershell",
            "-ExecutionPolicy", "Bypass",
            "-File", str(script),
        ],
        cwd=str(script.parent),
        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0,
    )
    return True
