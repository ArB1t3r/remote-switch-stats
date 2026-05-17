"""Virtual D-Pad widget drawn on a Canvas."""

import tkinter as tk
from typing import Callable, Optional


class DPad(tk.Canvas):
    """A cross-shaped D-Pad with Up/Down/Left/Right buttons."""

    DPAD_MAP = {
        "up": "DUP",
        "down": "DDOWN",
        "left": "DLEFT",
        "right": "DRIGHT",
    }

    def __init__(
        self,
        master: tk.Misc,
        size: int = 130,
        on_click: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master, width=size, height=size,
            bg="#1a1a2e", highlightthickness=0, **kwargs,
        )
        self._size = size
        self._on_click = on_click
        self._items: dict[str, int] = {}
        self._draw()

    def _draw(self) -> None:
        s = self._size
        u = s // 5  # unit

        dirs = {
            "up":    (2 * u, 0, 3 * u, 2 * u),
            "down":  (2 * u, 3 * u, 3 * u, 5 * u),
            "left":  (0, 2 * u, 2 * u, 3 * u),
            "right": (3 * u, 2 * u, 5 * u, 3 * u),
        }
        center = (2 * u, 2 * u, 3 * u, 3 * u)
        self.create_rectangle(*center, fill="#2d2d50", outline="")

        arrows = {
            "up": (2.5 * u, 0.6 * u, "\u25b2"),
            "down": (2.5 * u, 4.4 * u, "\u25bc"),
            "left": (0.6 * u, 2.5 * u, "\u25c0"),
            "right": (4.4 * u, 2.5 * u, "\u25b6"),
        }

        for direction, bbox in dirs.items():
            rect = self.create_rectangle(
                *bbox, fill="#2d2d50", outline="#3b3b5c", width=1,
            )
            ax, ay, arrow_char = arrows[direction]
            txt = self.create_text(
                ax, ay, text=arrow_char, fill="#9ca3af", font=("", 12),
            )
            self._items[direction] = rect
            for item in (rect, txt):
                self.tag_bind(item, "<Button-1>", lambda e, d=direction: self._press(d))
                self.tag_bind(item, "<Enter>", lambda e, r=rect: self.itemconfigure(r, fill="#4338ca"))
                self.tag_bind(item, "<Leave>", lambda e, r=rect: self.itemconfigure(r, fill="#2d2d50"))

    def _press(self, direction: str) -> None:
        btn = self.DPAD_MAP[direction]
        if self._on_click:
            self._on_click(btn)
