"""Screen capture tab — capture, display, save screenshots."""

import io
import os
import threading
import time
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from src.protocol import SwitchConnection


class ScreenView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        conn: SwitchConnection,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._conn = conn
        self._auto_capture = False
        self._photo_ref: Optional[ImageTk.PhotoImage] = None
        self._last_image: Optional[Image.Image] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_toolbar()
        self._build_display()
        self._build_status()

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(self, corner_radius=12)
        bar.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")

        ctk.CTkLabel(bar, text="屏幕捕捉", font=("", 16, "bold")).pack(
            side="left", padx=16, pady=10,
        )

        self._capture_btn = ctk.CTkButton(
            bar, text="截取屏幕", width=100, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_capture,
        )
        self._capture_btn.pack(side="left", padx=4, pady=10)

        self._auto_btn = ctk.CTkButton(
            bar, text="自动刷新: 关", width=120, fg_color="#4b5563",
            hover_color="#374151", command=self._toggle_auto,
        )
        self._auto_btn.pack(side="left", padx=4, pady=10)

        ctk.CTkLabel(bar, text="间隔(秒):").pack(side="left", padx=(12, 4), pady=10)
        self._interval_entry = ctk.CTkEntry(bar, width=50, placeholder_text="2")
        self._interval_entry.insert(0, "2")
        self._interval_entry.pack(side="left", padx=4, pady=10)

        self._save_btn = ctk.CTkButton(
            bar, text="保存图片", width=80, fg_color="#22c55e",
            hover_color="#16a34a", command=self._do_save,
        )
        self._save_btn.pack(side="left", padx=4, pady=10)

        # Screen on/off
        ctk.CTkButton(
            bar, text="开屏", width=60, fg_color="#f97316",
            hover_color="#ea580c",
            command=lambda: threading.Thread(target=self._conn.screen_on, daemon=True).start(),
        ).pack(side="right", padx=4, pady=10)

        ctk.CTkButton(
            bar, text="关屏", width=60, fg_color="#6b7280",
            hover_color="#4b5563",
            command=lambda: threading.Thread(target=self._conn.screen_off, daemon=True).start(),
        ).pack(side="right", padx=4, pady=10)

    def _build_display(self) -> None:
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        import tkinter as tk
        self._canvas = tk.Canvas(frame, bg="#0f0f1a", highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._canvas.create_text(
            400, 200, text="点击「截取屏幕」获取 Switch 画面",
            fill="#6b7280", font=("", 14),
        )

    def _build_status(self) -> None:
        self._status_label = ctk.CTkLabel(
            self, text="", font=("", 12), text_color="#9ca3af",
        )
        self._status_label.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")

    # ── Capture logic ──────────────────────────────────────────────

    def _do_capture(self) -> None:
        self._status_label.configure(text="正在捕捉…")

        def _task() -> None:
            raw = self._conn.pixel_peek()
            if not raw:
                self.after(0, lambda: self._status_label.configure(text="捕捉失败 — 无数据"))
                return

            img = self._decode_image(raw)
            if img is None:
                self.after(0, lambda: self._status_label.configure(text="捕捉失败 — 解码错误"))
                return

            self._last_image = img
            self.after(0, lambda: self._show_image(img))

        threading.Thread(target=_task, daemon=True).start()

    def _decode_image(self, data: bytes) -> Optional[Image.Image]:
        """
        sys-botbase pixelPeek returns data that could be:
        1. Raw JPG bytes
        2. Hex-encoded JPG string (terminated by \\n)
        """
        try:
            return Image.open(io.BytesIO(data))
        except Exception:
            pass

        try:
            hex_str = data.strip().decode("ascii", errors="ignore")
            jpg_bytes = bytes.fromhex(hex_str)
            return Image.open(io.BytesIO(jpg_bytes))
        except Exception:
            return None

    def _show_image(self, img: Image.Image) -> None:
        cw = self._canvas.winfo_width() or 800
        ch = self._canvas.winfo_height() or 450

        ratio = min(cw / img.width, ch / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)

        self._photo_ref = ImageTk.PhotoImage(resized)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, image=self._photo_ref, anchor="center")
        self._status_label.configure(
            text=f"已捕捉  {img.width}×{img.height}  |  {datetime.now().strftime('%H:%M:%S')}",
        )

    # ── Auto-refresh ───────────────────────────────────────────────

    def _toggle_auto(self) -> None:
        self._auto_capture = not self._auto_capture
        if self._auto_capture:
            self._auto_btn.configure(text="自动刷新: 开", fg_color="#22c55e", hover_color="#16a34a")
            threading.Thread(target=self._auto_loop, daemon=True).start()
        else:
            self._auto_btn.configure(text="自动刷新: 关", fg_color="#4b5563", hover_color="#374151")

    def _auto_loop(self) -> None:
        while self._auto_capture:
            try:
                interval = float(self._interval_entry.get())
            except ValueError:
                interval = 2.0
            interval = max(0.5, interval)

            raw = self._conn.pixel_peek()
            if raw:
                img = self._decode_image(raw)
                if img:
                    self._last_image = img
                    self.after(0, lambda i=img: self._show_image(i))
            time.sleep(interval)

    # ── Save ───────────────────────────────────────────────────────

    def _do_save(self) -> None:
        if self._last_image is None:
            self._status_label.configure(text="没有可保存的图片")
            return
        save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(save_dir, f"switch_capture_{ts}.jpg")
        try:
            self._last_image.save(path, "JPEG")
            self._status_label.configure(text=f"已保存: {path}")
        except Exception as e:
            self._status_label.configure(text=f"保存失败: {e}")
