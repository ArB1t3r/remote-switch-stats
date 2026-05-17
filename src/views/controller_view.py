"""Controller simulation tab — buttons, D-pad, joysticks, touch."""

import threading
import time
import customtkinter as ctk

from src.protocol import SwitchConnection, BUTTONS
from src.widgets.joystick import VirtualJoystick
from src.widgets.dpad import DPad


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

        self._build_ui()

    def _build_ui(self) -> None:
        # ── Left column: D-Pad + Left Stick ───────────────────────
        left_col = ctk.CTkFrame(self, fg_color="transparent")
        left_col.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

        self._build_left_stick_section(left_col)
        self._build_dpad_section(left_col)

        # ── Right column: Buttons + Right Stick ───────────────────
        right_col = ctk.CTkFrame(self, fg_color="transparent")
        right_col.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")

        self._build_face_buttons(right_col)
        self._build_right_stick_section(right_col)

        # ── Bottom: shoulder/system buttons + log ─────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, columnspan=2, padx=8, pady=8, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        self._build_shoulder_buttons(bottom)
        self._build_system_buttons(bottom)
        self._build_log(bottom)

    # ── Left stick ─────────────────────────────────────────────────

    def _build_left_stick_section(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=12)
        sec.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(sec, text="左摇杆", font=("", 14, "bold")).pack(padx=12, pady=(10, 4), anchor="w")
        self._left_stick = VirtualJoystick(
            sec, size=160, label="L",
            on_move=lambda x, y: self._stick_move("LEFT", x, y),
            on_release=lambda: self._stick_move("LEFT", 0, 0),
        )
        self._left_stick.pack(padx=12, pady=(4, 4))
        self._lstick_label = ctk.CTkLabel(sec, text="X: 0  Y: 0", font=("Consolas", 11), text_color="#9ca3af")
        self._lstick_label.pack(padx=12, pady=(0, 10))

    # ── D-Pad ──────────────────────────────────────────────────────

    def _build_dpad_section(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=12)
        sec.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(sec, text="十字键", font=("", 14, "bold")).pack(padx=12, pady=(10, 4), anchor="w")
        self._dpad = DPad(sec, size=130, on_click=self._dpad_click)
        self._dpad.pack(padx=12, pady=(4, 10))

    # ── Face buttons (A B X Y) ─────────────────────────────────────

    def _build_face_buttons(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=12)
        sec.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(sec, text="功能键", font=("", 14, "bold")).pack(padx=12, pady=(10, 4), anchor="w")

        grid = ctk.CTkFrame(sec, fg_color="transparent")
        grid.pack(padx=12, pady=(4, 10))

        btn_layout = [
            (0, 1, "X", "#eab308"),
            (1, 0, "Y", "#22c55e"),
            (1, 2, "A", "#ef4444"),
            (2, 1, "B", "#3b82f6"),
        ]
        for r, c, label, color in btn_layout:
            b = ctk.CTkButton(
                grid, text=label, width=50, height=50,
                corner_radius=25, fg_color=color,
                hover_color=self._darken(color),
                font=("", 16, "bold"),
                command=lambda btn=label: self._click_btn(btn),
            )
            b.grid(row=r, column=c, padx=6, pady=6)

    # ── Right stick ────────────────────────────────────────────────

    def _build_right_stick_section(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=12)
        sec.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(sec, text="右摇杆", font=("", 14, "bold")).pack(padx=12, pady=(10, 4), anchor="w")
        self._right_stick = VirtualJoystick(
            sec, size=160, label="R",
            on_move=lambda x, y: self._stick_move("RIGHT", x, y),
            on_release=lambda: self._stick_move("RIGHT", 0, 0),
        )
        self._right_stick.pack(padx=12, pady=(4, 4))
        self._rstick_label = ctk.CTkLabel(sec, text="X: 0  Y: 0", font=("Consolas", 11), text_color="#9ca3af")
        self._rstick_label.pack(padx=12, pady=(0, 10))

    # ── Shoulder buttons ───────────────────────────────────────────

    def _build_shoulder_buttons(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=12)
        sec.grid(row=0, column=0, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(sec, text="肩键", font=("", 14, "bold")).pack(padx=12, pady=(10, 4), anchor="w")

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(padx=12, pady=(4, 10))

        for label in ["L", "ZL", "LSTICK", "RSTICK", "ZR", "R"]:
            ctk.CTkButton(
                row, text=label, width=70, height=36,
                fg_color="#4338ca", hover_color="#3730a3",
                font=("", 12, "bold"),
                command=lambda b=label: self._click_btn(b),
            ).pack(side="left", padx=4)

    # ── System buttons ─────────────────────────────────────────────

    def _build_system_buttons(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=12)
        sec.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(sec, text="系统键", font=("", 14, "bold")).pack(padx=12, pady=(10, 4), anchor="w")

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(padx=12, pady=(4, 10))

        system_btns = [
            ("MINUS", "#6b7280"), ("PLUS", "#6b7280"),
            ("HOME", "#f97316"), ("CAPTURE", "#06b6d4"),
        ]
        for label, color in system_btns:
            ctk.CTkButton(
                row, text=label, width=80, height=36,
                fg_color=color, hover_color=self._darken(color),
                font=("", 12, "bold"),
                command=lambda b=label: self._click_btn(b),
            ).pack(side="left", padx=4)

        ctk.CTkButton(
            row, text="Detach", width=80, height=36,
            fg_color="#ef4444", hover_color="#dc2626",
            font=("", 12, "bold"),
            command=self._detach,
        ).pack(side="left", padx=(16, 4))

    # ── Command log ────────────────────────────────────────────────

    def _build_log(self, parent: ctk.CTkFrame) -> None:
        sec = ctk.CTkFrame(parent, corner_radius=12)
        sec.grid(row=2, column=0, padx=8, pady=(4, 8), sticky="ew")

        header = ctk.CTkFrame(sec, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(header, text="操作日志", font=("", 14, "bold")).pack(side="left")
        ctk.CTkButton(
            header, text="清空", width=50, height=24,
            fg_color="#6b7280", hover_color="#4b5563",
            command=self._clear_log,
        ).pack(side="right")

        self._log_text = ctk.CTkTextbox(sec, height=80, font=("Consolas", 11), state="disabled")
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

    @staticmethod
    def _darken(hex_color: str) -> str:
        """Return a slightly darker hex colour."""
        c = hex_color.lstrip("#")
        r, g, b = int(c[:2], 16), int(c[2:4], 16), int(c[4:], 16)
        f = 0.8
        return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"
