"""Main application window — tabbed interface hosting all views."""

import customtkinter as ctk

from src.protocol import SwitchConnection
from src.widgets.status_bar import StatusBar
from src.views.setup_view import SetupView
from src.views.controller_view import ControllerView
from src.views.memory_view import MemoryView
from src.views.screen_view import ScreenView
from src.views.macro_view import MacroView


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

    # ── Tabs ───────────────────────────────────────────────────────

    def _build_tabs(self) -> None:
        self._tabview = ctk.CTkTabview(self, corner_radius=8)
        self._tabview.grid(row=1, column=0, padx=8, pady=(4, 0), sticky="nsew")

        tab_setup = self._tabview.add("设置与连接")
        tab_ctrl = self._tabview.add("控制器")
        tab_mem = self._tabview.add("内存工具")
        tab_screen = self._tabview.add("屏幕捕捉")
        tab_macro = self._tabview.add("宏序列")

        for tab in (tab_setup, tab_ctrl, tab_mem, tab_screen, tab_macro):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self._setup_view = SetupView(tab_setup, self._conn)
        self._setup_view.grid(row=0, column=0, sticky="nsew")

        self._ctrl_view = ControllerView(tab_ctrl, self._conn)
        self._ctrl_view.grid(row=0, column=0, sticky="nsew")

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
