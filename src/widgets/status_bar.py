"""Bottom status bar showing connection state, Switch IP, and game info."""

import customtkinter as ctk

from src import theme


class StatusBar(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(master, height=32, corner_radius=0, **kwargs)
        self.grid_columnconfigure(2, weight=1)

        self._indicator = ctk.CTkLabel(
            self, text="●", text_color=theme.DANGER,
            font=("", 14), width=20,
        )
        self._indicator.grid(row=0, column=0, padx=(8, 2), pady=4)

        self._status_label = ctk.CTkLabel(
            self, text="未连接", font=theme.FONT_BODY, anchor="w",
        )
        self._status_label.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        self._info_label = ctk.CTkLabel(
            self, text="", font=theme.FONT_MONO_SM, anchor="e",
            text_color=theme.TEXT_MUTED,
        )
        self._info_label.grid(row=0, column=2, padx=(4, 12), pady=4, sticky="e")

    def set_connected(self, ip: str) -> None:
        self._indicator.configure(text_color=theme.SUCCESS)
        self._status_label.configure(text=f"已连接  {ip}:6000")

    def set_disconnected(self) -> None:
        self._indicator.configure(text_color=theme.DANGER)
        self._status_label.configure(text="未连接")
        self._info_label.configure(text="")

    def set_info(self, text: str) -> None:
        self._info_label.configure(text=text)


class DisconnectBanner(ctk.CTkFrame):
    """Slim banner shown above the status bar when not connected."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(
            master, height=26, corner_radius=0,
            fg_color="#7c2d12", **kwargs,
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        self._label = ctk.CTkLabel(
            self,
            text="⚠  尚未连接到 Switch — 切换到「设置与连接」页连接后再操作",
            font=theme.FONT_HINT,
            text_color="#fed7aa",
        )
        self._label.grid(row=0, column=0, padx=12, pady=2, sticky="w")

    def set_disconnected(self) -> None:
        self.grid()

    def set_connected(self) -> None:
        self.grid_remove()
