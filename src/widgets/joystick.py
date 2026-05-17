"""Virtual analog joystick widget drawn on a Canvas."""

import math
import tkinter as tk
from typing import Callable, Optional


class VirtualJoystick(tk.Canvas):
    """
    A draggable virtual joystick that maps to Switch stick values
    (-0x8000 .. 0x7FFF).
    """

    STICK_MAX = 0x7FFF
    STICK_MIN = -0x8000

    def __init__(
        self,
        master: tk.Misc,
        size: int = 150,
        label: str = "",
        on_move: Optional[Callable[[int, int], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            bg="#1a1a2e",
            highlightthickness=0,
            **kwargs,
        )
        self._size = size
        self._center = size // 2
        self._radius = size // 2 - 10
        self._knob_radius = 18
        self._on_move = on_move
        self._on_release = on_release

        self._bg_circle = self.create_oval(
            10, 10, size - 10, size - 10,
            outline="#3b3b5c", width=2, fill="#16162a",
        )
        self.create_line(
            self._center, 10, self._center, size - 10,
            fill="#2a2a44", dash=(2, 4),
        )
        self.create_line(
            10, self._center, size - 10, self._center,
            fill="#2a2a44", dash=(2, 4),
        )

        self._knob = self.create_oval(
            self._center - self._knob_radius,
            self._center - self._knob_radius,
            self._center + self._knob_radius,
            self._center + self._knob_radius,
            fill="#6366f1", outline="#818cf8", width=2,
        )

        if label:
            self.create_text(
                self._center, size - 4,
                text=label, fill="#9ca3af", font=("", 9),
            )

        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_btn_release)
        self.bind("<Button-1>", self._on_drag)

        self._kx = 0
        self._ky = 0

    def _on_drag(self, event: tk.Event) -> None:
        dx = event.x - self._center
        dy = event.y - self._center
        dist = math.hypot(dx, dy)
        if dist > self._radius:
            scale = self._radius / dist
            dx = dx * scale
            dy = dy * scale
        nx = self._center + dx
        ny = self._center + dy
        self.coords(
            self._knob,
            nx - self._knob_radius, ny - self._knob_radius,
            nx + self._knob_radius, ny + self._knob_radius,
        )
        sx = int((dx / self._radius) * self.STICK_MAX)
        sy = int((-dy / self._radius) * self.STICK_MAX)  # invert Y
        self._kx = sx
        self._ky = sy
        if self._on_move:
            self._on_move(sx, sy)

    def _on_btn_release(self, event: tk.Event) -> None:
        self.coords(
            self._knob,
            self._center - self._knob_radius,
            self._center - self._knob_radius,
            self._center + self._knob_radius,
            self._center + self._knob_radius,
        )
        self._kx = 0
        self._ky = 0
        if self._on_release:
            self._on_release()

    def get_values(self) -> tuple[int, int]:
        return self._kx, self._ky
