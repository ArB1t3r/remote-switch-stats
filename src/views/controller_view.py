"""Controller simulation tab — buttons, D-pad, joysticks, touch."""

import threading
from typing import Callable, Optional
import customtkinter as ctk

from src import theme
from src.protocol import SwitchConnection, BUTTONS
from src.widgets.joystick import VirtualJoystick
from src.widgets.dpad import DPad


# ── Face button layout (label, row, col, color) ─────────────────────
FACE_BUTTONS = [
    (0, 1, "X", theme.WARNING),
    (1, 0, "Y", theme.SUCCESS),
    (1, 2, "A", theme.DANGER),
    (2, 1, "B", "#3b82f6"),
]
SYSTEM_BUTTONS = [
    ("MINUS", theme.NEUTRAL_SOFT),
    ("PLUS", theme.NEUTRAL_SOFT),
    ("HOME", theme.ACCENT),
    ("CAPTURE", theme.INFO),
]
SHOULDER_BUTTONS = ["L", "ZL", "LSTICK", "RSTICK", "ZR", "R"]


class ControllerView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        conn: SwitchConnection,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._conn = conn
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._stick_pending: dict[str, tuple[int, int] | None] = {"LEFT": None, "RIGHT": None}
        self._stick_sending: dict[str, bool] = {"LEFT": False, "RIGHT": False}
        self._stick_lock = threading.Lock()
        self._float_window: Optional[FloatingController] = None

        self._build_top_bar()
        self._build_ui()

    # ── Top bar with detach toggle ────────────────────────────────

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 0), sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bar, text="使用控制器时，可点击右侧「浮窗模式」让控制器始终悬浮在窗口顶部，方便切换到其他页面操作时仍能控制。",
            font=theme.FONT_HINT, text_color=theme.TEXT_MUTED, anchor="w",
            justify="left", wraplength=560,
        ).grid(row=0, column=0, sticky="w", padx=4)

        self._float_btn = ctk.CTkButton(
            bar, text="🪟  浮窗模式", width=110, height=theme.BTN_H_SM,
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            font=theme.FONT_BODY_BOLD,
            command=self._toggle_float,
        )
        self._float_btn.grid(row=0, column=1, sticky="e", padx=4)

    def _build_ui(self) -> None:
        # ── Left column: D-Pad + Left Stick ───────────────────────
        left_col = ctk.CTkFrame(self, fg_color="transparent")
        left_col.grid(row=1, column=0, padx=8, pady=8, sticky="nsew")

        self._build_left_stick_section(left_col)
        self._build_dpad_section(left_col)

        # ── Right column: Buttons + Right Stick ───────────────────
        right_col = ctk.CTkFrame(self, fg_color="transparent")
        right_col.grid(row=1, column=1, padx=8, pady=8, sticky="nsew")

        self._build_face_buttons(right_col)
        self._build_right_stick_section(right_col)

        # ── Bottom: shoulder/system buttons + log ─────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, columnspan=2, padx=8, pady=8, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        self._build_shoulder_buttons(bottom)
        self._build_system_buttons(bottom)
        self._build_log(bottom)

    # ── Left stick ─────────────────────────────────────────────────

    def _build_left_stick_section(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=theme.CORNER_LG)
        sec.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(sec, text="左摇杆", font=theme.FONT_SUBSECTION).pack(padx=12, pady=(10, 4), anchor="w")
        self._left_stick = VirtualJoystick(
            sec, size=160, label="L",
            on_move=lambda x, y: self._stick_move("LEFT", x, y),
            on_release=lambda: self._stick_move("LEFT", 0, 0),
        )
        self._left_stick.pack(padx=12, pady=(4, 4))
        self._lstick_label = ctk.CTkLabel(
            sec, text="X: 0  Y: 0", font=theme.FONT_MONO_SM, text_color=theme.TEXT_MUTED,
        )
        self._lstick_label.pack(padx=12, pady=(0, 10))

    # ── D-Pad ──────────────────────────────────────────────────────

    def _build_dpad_section(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=theme.CORNER_LG)
        sec.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(sec, text="十字键", font=theme.FONT_SUBSECTION).pack(padx=12, pady=(10, 4), anchor="w")
        self._dpad = DPad(sec, size=130, on_click=self._dpad_click)
        self._dpad.pack(padx=12, pady=(4, 10))

    # ── Face buttons (A B X Y) ─────────────────────────────────────

    def _build_face_buttons(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=theme.CORNER_LG)
        sec.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(sec, text="功能键", font=theme.FONT_SUBSECTION).pack(padx=12, pady=(10, 4), anchor="w")

        grid = ctk.CTkFrame(sec, fg_color="transparent")
        grid.pack(padx=12, pady=(4, 10))

        for r, c, label, color in FACE_BUTTONS:
            b = ctk.CTkButton(
                grid, text=label, width=50, height=50,
                corner_radius=25, fg_color=color,
                hover_color=theme.darken(color),
                font=("", 16, "bold"),
                command=lambda btn=label: self._click_btn(btn),
            )
            b.grid(row=r, column=c, padx=6, pady=6)

    # ── Right stick ────────────────────────────────────────────────

    def _build_right_stick_section(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=theme.CORNER_LG)
        sec.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(sec, text="右摇杆", font=theme.FONT_SUBSECTION).pack(padx=12, pady=(10, 4), anchor="w")
        self._right_stick = VirtualJoystick(
            sec, size=160, label="R",
            on_move=lambda x, y: self._stick_move("RIGHT", x, y),
            on_release=lambda: self._stick_move("RIGHT", 0, 0),
        )
        self._right_stick.pack(padx=12, pady=(4, 4))
        self._rstick_label = ctk.CTkLabel(
            sec, text="X: 0  Y: 0", font=theme.FONT_MONO_SM, text_color=theme.TEXT_MUTED,
        )
        self._rstick_label.pack(padx=12, pady=(0, 10))

    # ── Shoulder buttons ───────────────────────────────────────────

    def _build_shoulder_buttons(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=theme.CORNER_LG)
        sec.grid(row=0, column=0, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(sec, text="肩键", font=theme.FONT_SUBSECTION).pack(padx=12, pady=(10, 4), anchor="w")

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(padx=12, pady=(4, 10))

        for label in SHOULDER_BUTTONS:
            ctk.CTkButton(
                row, text=label, width=70, height=36,
                fg_color=theme.TOKEN_SHOULDER, hover_color=theme.TOKEN_SHOULDER_HOVER,
                font=theme.FONT_BODY_BOLD,
                command=lambda b=label: self._click_btn(b),
            ).pack(side="left", padx=4)

    # ── System buttons ─────────────────────────────────────────────

    def _build_system_buttons(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=theme.CORNER_LG)
        sec.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(sec, text="系统键", font=theme.FONT_SUBSECTION).pack(padx=12, pady=(10, 4), anchor="w")

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(padx=12, pady=(4, 10))

        for label, color in SYSTEM_BUTTONS:
            ctk.CTkButton(
                row, text=label, width=80, height=36,
                fg_color=color, hover_color=theme.darken(color),
                font=theme.FONT_BODY_BOLD,
                command=lambda b=label: self._click_btn(b),
            ).pack(side="left", padx=4)

        ctk.CTkButton(
            row, text="Detach", width=80, height=36,
            fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            font=theme.FONT_BODY_BOLD,
            command=self._detach,
        ).pack(side="left", padx=(16, 4))

    # ── Command log ────────────────────────────────────────────────

    def _build_log(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=theme.CORNER_LG)
        sec.grid(row=2, column=0, padx=8, pady=(4, 8), sticky="ew")

        header = ctk.CTkFrame(sec, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(header, text="操作日志", font=theme.FONT_SUBSECTION).pack(side="left")
        ctk.CTkButton(
            header, text="清空", width=50, height=24,
            fg_color=theme.NEUTRAL_SOFT, hover_color=theme.NEUTRAL_SOFT_HOVER,
            command=self._clear_log,
        ).pack(side="right")

        self._log_text = ctk.CTkTextbox(sec, height=80, font=theme.FONT_MONO_SM, state="disabled")
        self._log_text.pack(fill="x", padx=12, pady=(0, 10))

    # ── Actions ────────────────────────────────────────────────────

    def _click_btn(self, button: str) -> None:
        self._log(f"click {button}")

        def _task() -> None:
            self._conn.click(button)

        threading.Thread(target=_task, daemon=True).start()

    def _dpad_click(self, button: str) -> None:
        self._click_btn(button)

    def _stick_move(self, stick: str, x: int, y: int) -> None:
        label_w = self._lstick_label if stick == "LEFT" else self._rstick_label
        label_w.configure(text=f"X: {x}  Y: {y}")

        with self._stick_lock:
            self._stick_pending[stick] = (x, y)
            if self._stick_sending[stick]:
                return
            self._stick_sending[stick] = True

        threading.Thread(target=self._stick_sender, args=(stick,), daemon=True).start()

    def _stick_sender(self, stick: str) -> None:
        """Drain pending stick values, only sending the latest position."""
        while True:
            with self._stick_lock:
                pos = self._stick_pending[stick]
                self._stick_pending[stick] = None
                if pos is None:
                    self._stick_sending[stick] = False
                    return
            self._conn.set_stick(stick, pos[0], pos[1])

    def _detach(self) -> None:
        self._log("detachController")
        threading.Thread(target=self._conn.detach_controller, daemon=True).start()

    def _log(self, msg: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ── Floating window ────────────────────────────────────────────

    def _toggle_float(self) -> None:
        if self._float_window is not None and self._float_window.winfo_exists():
            self._float_window.destroy()
            self._float_window = None
            self._float_btn.configure(text="🪟  浮窗模式", fg_color=theme.PRIMARY)
            return

        self._float_window = FloatingController(
            self.winfo_toplevel(),
            conn=self._conn,
            log_callback=self._log,
            on_close=self._on_float_closed,
        )
        self._float_btn.configure(text="✕  关闭浮窗", fg_color=theme.DANGER)

    def _on_float_closed(self) -> None:
        self._float_window = None
        self._float_btn.configure(text="🪟  浮窗模式", fg_color=theme.PRIMARY)


# ── Floating controller window ────────────────────────────────────────

class FloatingController(ctk.CTkToplevel):
    """Always-on-top compact controller for use across tabs."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        conn: SwitchConnection,
        log_callback: Callable[[str], None],
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._log = log_callback
        self._on_close = on_close

        self._stick_pending: dict[str, tuple[int, int] | None] = {"LEFT": None, "RIGHT": None}
        self._stick_sending: dict[str, bool] = {"LEFT": False, "RIGHT": False}
        self._stick_lock = threading.Lock()

        self.title("Switch Controller — 浮窗")
        self.geometry("460x560")
        self.minsize(420, 540)
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

        # Default: always on top + 95% opacity
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.95)
        except Exception:
            pass

        self._build_topbar()
        self._build_body()

    # ── Topbar (always-on-top toggle + opacity) ────────────────────

    def _build_topbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.SURFACE_HEADER, corner_radius=0, height=36)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        self._topmost_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            bar, text="始终置顶", variable=self._topmost_var,
            font=theme.FONT_HINT, command=self._toggle_topmost,
            checkbox_width=16, checkbox_height=16,
        ).pack(side="left", padx=(10, 12), pady=6)

        ctk.CTkLabel(bar, text="透明度", font=theme.FONT_HINT, text_color=theme.TEXT_MUTED).pack(
            side="left", padx=(4, 4), pady=6,
        )
        self._alpha_slider = ctk.CTkSlider(
            bar, from_=0.5, to=1.0, width=120, number_of_steps=50,
            command=self._set_alpha,
        )
        self._alpha_slider.set(0.95)
        self._alpha_slider.pack(side="left", padx=4, pady=6)

        self._alpha_label = ctk.CTkLabel(
            bar, text="95%", width=40, font=theme.FONT_MONO_SM, text_color=theme.TEXT_MUTED,
        )
        self._alpha_label.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            bar, text="✕", width=28, height=24, font=("", 12, "bold"),
            fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            command=self._handle_close,
        ).pack(side="right", padx=(4, 8), pady=6)

    def _toggle_topmost(self) -> None:
        self.attributes("-topmost", bool(self._topmost_var.get()))

    def _set_alpha(self, value: float) -> None:
        try:
            self.attributes("-alpha", float(value))
        except Exception:
            pass
        self._alpha_label.configure(text=f"{int(value * 100)}%")

    def _handle_close(self) -> None:
        try:
            self._on_close()
        finally:
            self.destroy()

    # ── Body ───────────────────────────────────────────────────────

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        # Left column: D-pad + L/ZL + LSTICK
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=4)

        self._dpad = DPad(left, size=110, on_click=self._click_btn)
        self._dpad.pack(pady=(4, 6))

        l_stick_box = ctk.CTkFrame(left, corner_radius=theme.CORNER_MD)
        l_stick_box.pack(fill="x", pady=4)
        self._left_stick = VirtualJoystick(
            l_stick_box, size=130, label="L",
            on_move=lambda x, y: self._stick_move("LEFT", x, y),
            on_release=lambda: self._stick_move("LEFT", 0, 0),
        )
        self._left_stick.pack(padx=8, pady=6)

        l_shoulder = ctk.CTkFrame(left, fg_color="transparent")
        l_shoulder.pack(pady=4)
        for label in ["L", "ZL"]:
            ctk.CTkButton(
                l_shoulder, text=label, width=55, height=30,
                fg_color=theme.TOKEN_SHOULDER, hover_color=theme.TOKEN_SHOULDER_HOVER,
                font=theme.FONT_BODY_BOLD,
                command=lambda b=label: self._click_btn(b),
            ).pack(side="left", padx=3)

        # Right column: ABXY + R/ZR + RSTICK
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=4)

        face_grid = ctk.CTkFrame(right, fg_color="transparent")
        face_grid.pack(pady=(4, 6))
        for r, c, label, color in FACE_BUTTONS:
            ctk.CTkButton(
                face_grid, text=label, width=42, height=42,
                corner_radius=21, fg_color=color,
                hover_color=theme.darken(color),
                font=("", 14, "bold"),
                command=lambda b=label: self._click_btn(b),
            ).grid(row=r, column=c, padx=4, pady=4)

        r_stick_box = ctk.CTkFrame(right, corner_radius=theme.CORNER_MD)
        r_stick_box.pack(fill="x", pady=4)
        self._right_stick = VirtualJoystick(
            r_stick_box, size=130, label="R",
            on_move=lambda x, y: self._stick_move("RIGHT", x, y),
            on_release=lambda: self._stick_move("RIGHT", 0, 0),
        )
        self._right_stick.pack(padx=8, pady=6)

        r_shoulder = ctk.CTkFrame(right, fg_color="transparent")
        r_shoulder.pack(pady=4)
        for label in ["R", "ZR"]:
            ctk.CTkButton(
                r_shoulder, text=label, width=55, height=30,
                fg_color=theme.TOKEN_SHOULDER, hover_color=theme.TOKEN_SHOULDER_HOVER,
                font=theme.FONT_BODY_BOLD,
                command=lambda b=label: self._click_btn(b),
            ).pack(side="left", padx=3)

        # Bottom: system row spanning both columns
        sys_row = ctk.CTkFrame(body, fg_color="transparent")
        sys_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 0))
        for label, color in SYSTEM_BUTTONS:
            ctk.CTkButton(
                sys_row, text=label, width=70, height=30,
                fg_color=color, hover_color=theme.darken(color),
                font=theme.FONT_BODY_BOLD,
                command=lambda b=label: self._click_btn(b),
            ).pack(side="left", padx=3, expand=True, fill="x")

    # ── Actions (shared with main view via conn + log_callback) ────

    def _click_btn(self, button: str) -> None:
        self._log(f"[浮窗] click {button}")
        threading.Thread(target=lambda: self._conn.click(button), daemon=True).start()

    def _stick_move(self, stick: str, x: int, y: int) -> None:
        with self._stick_lock:
            self._stick_pending[stick] = (x, y)
            if self._stick_sending[stick]:
                return
            self._stick_sending[stick] = True
        threading.Thread(target=self._stick_sender, args=(stick,), daemon=True).start()

    def _stick_sender(self, stick: str) -> None:
        while True:
            with self._stick_lock:
                pos = self._stick_pending[stick]
                self._stick_pending[stick] = None
                if pos is None:
                    self._stick_sending[stick] = False
                    return
            self._conn.set_stick(stick, pos[0], pos[1])
