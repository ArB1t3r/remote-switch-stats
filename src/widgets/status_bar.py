"""Bottom status bar showing connection state, Switch IP, and game info."""

import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(master, height=32, corner_radius=0, **kwargs)
        self.grid_columnconfigure(2, weight=1)

        self._indicator = ctk.CTkLabel(
            self, text="\u25cf", text_color="#ef4444", font=("", 14), width=20,
        )
        self._indicator.grid(row=0, column=0, padx=(8, 2), pady=4)

        self._status_label = ctk.CTkLabel(
            self, text="未连接", font=("", 12), anchor="w",
        )
        self._status_label.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        self._info_label = ctk.CTkLabel(
            self, text="", font=("", 12), anchor="e", text_color="gray",
        )
        self._info_label.grid(row=0, column=2, padx=(4, 12), pady=4, sticky="e")

    def set_connected(self, ip: str) -> None:
        self._indicator.configure(text_color="#22c55e")
        self._status_label.configure(text=f"已连接  {ip}:6000")

    def set_disconnected(self) -> None:
        self._indicator.configure(text_color="#ef4444")
        self._status_label.configure(text="未连接")
        self._info_label.configure(text="")

    def set_info(self, text: str) -> None:
        self._info_label.configure(text=text)
