"""Main application window — tabbed interface hosting all views."""

import sys
import customtkinter as ctk
from tkinter import messagebox

from src import APP_VERSION
from src.protocol import SwitchConnection
from src.updater import UpdateInfo, check_for_update_async, launch_updater_script
from src.widgets.status_bar import StatusBar
from src.views.setup_view import SetupView
from src.views.controller_view import ControllerView
from src.views.memory_view import MemoryView
from src.views.screen_view import ScreenView
from src.views.macro_view import MacroView
from src.views.recorder_view import RecorderView


APP_TITLE = "Switch Remote Control — sys-botbase Client"
APP_SIZE = (960, 740)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(APP_TITLE)
        self.geometry(f"{APP_SIZE[0]}x{APP_SIZE[1]}")
        self.minsize(800, 600)

        self._conn = SwitchConnection()
        self._conn.set_status_callback(self._on_connection_change)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_tabs()
        self._build_status_bar()

    # ── Header ─────────────────────────────────────────────────────

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0, height=48, fg_color="#1e1b4b")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="\U0001f3ae  Switch Remote Control",
            font=("", 18, "bold"), text_color="white",
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")

        right_frame = ctk.CTkFrame(header, fg_color="transparent")
        right_frame.grid(row=0, column=1, padx=16, pady=10, sticky="e")

        self._version_label = ctk.CTkLabel(
            right_frame, text=f"v{APP_VERSION}",
            font=("", 12), text_color="#94a3b8",
        )
        self._version_label.pack(side="left", padx=(0, 8))

        self._update_btn = ctk.CTkButton(
            right_frame, text="检查更新...", width=90, height=28,
            font=("", 12), fg_color="#334155", hover_color="#475569",
            command=self._on_update_click,
        )
        self._update_btn.pack(side="left")
        self._update_btn.configure(state="disabled")

        self._update_info: UpdateInfo | None = None
        self.after(1500, self._start_update_check)

    # ── Tabs ───────────────────────────────────────────────────────

    def _build_tabs(self) -> None:
        self._tabview = ctk.CTkTabview(self, corner_radius=8)
        self._tabview.grid(row=1, column=0, padx=8, pady=(4, 0), sticky="nsew")

        tab_setup = self._tabview.add("设置与连接")
        tab_ctrl = self._tabview.add("控制器")
        tab_recorder = self._tabview.add("信息采集")
        tab_mem = self._tabview.add("内存工具")
        tab_screen = self._tabview.add("屏幕捕捉")
        tab_macro = self._tabview.add("宏序列")

        for tab in (tab_setup, tab_ctrl, tab_recorder, tab_mem, tab_screen, tab_macro):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self._setup_view = SetupView(tab_setup, self._conn)
        self._setup_view.grid(row=0, column=0, sticky="nsew")

        self._ctrl_view = ControllerView(tab_ctrl, self._conn)
        self._ctrl_view.grid(row=0, column=0, sticky="nsew")

        self._recorder_view = RecorderView(tab_recorder, self._conn)
        self._recorder_view.grid(row=0, column=0, sticky="nsew")

        self._mem_view = MemoryView(tab_mem, self._conn)
        self._mem_view.grid(row=0, column=0, sticky="nsew")

        self._screen_view = ScreenView(tab_screen, self._conn)
        self._screen_view.grid(row=0, column=0, sticky="nsew")

        self._macro_view = MacroView(tab_macro, self._conn)
        self._macro_view.grid(row=0, column=0, sticky="nsew")

    # ── Status bar ─────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        self._status_bar = StatusBar(self)
        self._status_bar.grid(row=2, column=0, sticky="ew")

    # ── Connection callback ────────────────────────────────────────

    def _on_connection_change(self, connected: bool) -> None:
        def _update() -> None:
            if connected:
                self._status_bar.set_connected(self._conn.ip or "")
            else:
                self._status_bar.set_disconnected()
        self.after(0, _update)

    # ── Auto-update ─────────────────────────────────────────────────

    def _start_update_check(self) -> None:
        check_for_update_async(self._on_update_result)

    def _on_update_result(self, info: UpdateInfo) -> None:
        self._update_info = info
        self.after(0, self._apply_update_ui)

    def _apply_update_ui(self) -> None:
        info = self._update_info
        if not info:
            return

        self._update_btn.configure(state="normal")

        if info.available:
            self._update_btn.configure(
                text="\u2b06 有新版本",
                fg_color="#16a34a",
                hover_color="#15803d",
                text_color="white",
            )
        elif "失败" in info.message:
            self._update_btn.configure(
                text="\u26a0 检查失败",
                fg_color="#92400e",
                hover_color="#78350f",
                text_color="white",
            )
        else:
            self._update_btn.configure(
                text="\u2713 已是最新",
                fg_color="#334155",
                hover_color="#475569",
            )

    def _on_update_click(self) -> None:
        info = self._update_info
        if not info:
            return

        if not info.available:
            messagebox.showinfo(
                "版本检查",
                f"当前版本: v{APP_VERSION}\n"
                f"本地 SHA: {info.local_sha}\n\n"
                "已是最新版本，无需更新。",
            )
            return

        result = messagebox.askyesno(
            "发现新版本",
            f"当前版本: v{APP_VERSION} ({info.local_sha})\n"
            f"最新提交: {info.remote_sha} ({info.commit_date})\n"
            f"更新内容: {info.message}\n\n"
            "是否立即更新？\n"
            "（将启动更新脚本并关闭当前程序）",
        )

        if result:
            launched = launch_updater_script()
            if launched:
                self.destroy()
                sys.exit(0)
            else:
                messagebox.showwarning(
                    "更新失败",
                    "无法启动更新脚本。\n\n"
                    "可能的原因：\n"
                    "- 当前不在 Windows 系统\n"
                    "- update_windows.ps1 文件缺失\n\n"
                    "请手动下载最新源码并运行 build_windows.ps1",
                )
