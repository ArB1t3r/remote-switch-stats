"""Pokemon Stats Recorder tab — automated multi-Pokemon screenshot collection."""

import os
import platform
import subprocess
import threading
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from src.protocol import SwitchConnection
from src.recorder import PokemonRecorder, RecorderCallbacks, POKEMON_DETAIL_STEPS


class RecorderView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        conn: SwitchConnection,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._conn = conn
        self._recorder: Optional[PokemonRecorder] = None
        self._photo_ref: Optional[ImageTk.PhotoImage] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_config()
        self._build_controls()
        self._build_main_area()
        self._build_log()

    # ── Config panel ───────────────────────────────────────────────

    def _build_config(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")

        ctk.CTkLabel(sec, text="Pokemon 信息采集", font=("", 18, "bold")).pack(
            padx=16, pady=(12, 4), anchor="w",
        )
        ctk.CTkLabel(
            sec, font=("", 11), text_color="#9ca3af",
            text="自动翻页截取每只宝可梦的招式/持有物/队友/能力/EV/特性页面，每只 11 张截图",
        ).pack(padx=16, pady=(0, 8), anchor="w")

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(row, text="采集数量:").pack(side="left", padx=(0, 4))
        self._count_entry = ctk.CTkEntry(row, width=50, placeholder_text="6")
        self._count_entry.insert(0, "6")
        self._count_entry.pack(side="left", padx=4)

        ctk.CTkLabel(row, text="每步等待(ms):").pack(side="left", padx=(16, 4))
        self._wait_entry = ctk.CTkEntry(row, width=60, placeholder_text="500")
        self._wait_entry.insert(0, "500")
        self._wait_entry.pack(side="left", padx=4)

        ctk.CTkLabel(row, text="差异阈值:").pack(side="left", padx=(16, 4))
        self._threshold_entry = ctk.CTkEntry(row, width=60, placeholder_text="0.02")
        self._threshold_entry.insert(0, "0.02")
        self._threshold_entry.pack(side="left", padx=4)

        ctk.CTkLabel(row, text="最大重试:").pack(side="left", padx=(16, 4))
        self._retry_entry = ctk.CTkEntry(row, width=40, placeholder_text="3")
        self._retry_entry.insert(0, "3")
        self._retry_entry.pack(side="left", padx=4)

    # ── Control buttons ────────────────────────────────────────────

    def _build_controls(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=1, column=0, padx=16, pady=4, sticky="ew")

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=10)

        self._start_btn = ctk.CTkButton(
            row, text="\u25b6  开始采集", width=120, fg_color="#22c55e",
            hover_color="#16a34a", font=("", 13, "bold"),
            command=self._do_start,
        )
        self._start_btn.pack(side="left", padx=4)

        self._pause_btn = ctk.CTkButton(
            row, text="\u23f8  暂停", width=80, fg_color="#eab308",
            hover_color="#ca8a04", font=("", 13, "bold"),
            command=self._do_pause, state="disabled",
        )
        self._pause_btn.pack(side="left", padx=4)

        self._stop_btn = ctk.CTkButton(
            row, text="\u25a0  停止", width=80, fg_color="#ef4444",
            hover_color="#dc2626", font=("", 13, "bold"),
            command=self._do_stop, state="disabled",
        )
        self._stop_btn.pack(side="left", padx=4)

        self._open_dir_btn = ctk.CTkButton(
            row, text="打开保存目录", width=110, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_open_dir, state="disabled",
        )
        self._open_dir_btn.pack(side="right", padx=4)

        # Progress
        prog_row = ctk.CTkFrame(sec, fg_color="transparent")
        prog_row.pack(fill="x", padx=16, pady=(0, 10))

        self._progress_bar = ctk.CTkProgressBar(prog_row)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", side="left", expand=True, padx=(0, 8))

        self._progress_label = ctk.CTkLabel(
            prog_row, text="就绪", font=("", 12), text_color="#9ca3af", width=220,
        )
        self._progress_label.pack(side="right")

    # ── Main area: preview + step table ────────────────────────────

    def _build_main_area(self) -> None:
        main = ctk.CTkFrame(self, corner_radius=12)
        main.grid(row=2, column=0, padx=16, pady=4, sticky="nsew")
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        # Left: screenshot preview
        preview_frame = ctk.CTkFrame(main, fg_color="transparent")
        preview_frame.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(preview_frame, text="实时预览", font=("", 14, "bold")).grid(
            row=0, column=0, padx=8, pady=(4, 0), sticky="w",
        )
        import tkinter as tk
        self._preview_canvas = tk.Canvas(
            preview_frame, bg="#0f0f1a", highlightthickness=0,
        )
        self._preview_canvas.grid(row=1, column=0, padx=8, pady=8, sticky="nsew")
        self._preview_name = ctk.CTkLabel(
            preview_frame, text="", font=("Consolas", 12), text_color="#9ca3af",
        )
        self._preview_name.grid(row=2, column=0, padx=8, pady=(0, 4))

        # Right: step reference table
        table_frame = ctk.CTkFrame(main, fg_color="transparent")
        table_frame.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")

        ctk.CTkLabel(table_frame, text="采集步骤", font=("", 14, "bold")).pack(
            padx=8, pady=(4, 4), anchor="w",
        )

        self._step_labels: list[ctk.CTkLabel] = []
        steps_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        steps_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        for i, step in enumerate(POKEMON_DETAIL_STEPS):
            row = ctk.CTkFrame(steps_scroll, fg_color="transparent", height=24)
            row.pack(fill="x", padx=2, pady=1)

            lbl = ctk.CTkLabel(
                row,
                text=f"  {step.screenshot_name}",
                font=("Consolas", 11),
                text_color="#6b7280",
                anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True)

            btn_lbl = ctk.CTkLabel(
                row, text=step.button, font=("Consolas", 10),
                text_color="#4b5563", width=60,
            )
            btn_lbl.pack(side="right")

            self._step_labels.append(lbl)

    # ── Log ────────────────────────────────────────────────────────

    def _build_log(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=3, column=0, padx=16, pady=(4, 16), sticky="ew")
        sec.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(sec, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(header, text="采集日志", font=("", 14, "bold")).pack(side="left")
        ctk.CTkButton(
            header, text="清空", width=50, height=24,
            fg_color="#6b7280", hover_color="#4b5563",
            command=self._clear_log,
        ).pack(side="right")

        self._log_text = ctk.CTkTextbox(sec, height=120, font=("Consolas", 11), state="disabled")
        self._log_text.pack(fill="x", padx=16, pady=(0, 10))

    # ── Actions ────────────────────────────────────────────────────

    def _do_start(self) -> None:
        if not self._conn.connected:
            self._log("未连接到 Switch，请先在「设置与连接」页连接")
            return

        try:
            count = int(self._count_entry.get())
            wait = int(self._wait_entry.get())
            threshold = float(self._threshold_entry.get())
            retries = int(self._retry_entry.get())
        except ValueError:
            self._log("参数格式错误，请检查输入")
            return

        self._start_btn.configure(state="disabled")
        self._pause_btn.configure(state="normal")
        self._stop_btn.configure(state="normal")

        callbacks = RecorderCallbacks(
            on_log=lambda msg: self.after(0, lambda m=msg: self._log(m)),
            on_progress=lambda pi, pt, si, st: self.after(
                0, lambda: self._update_progress(pi, pt, si, st),
            ),
            on_screenshot=lambda img, name: self.after(
                0, lambda i=img, n=name: self._show_preview(i, n),
            ),
            on_error=lambda msg: self.after(0, lambda m=msg: self._log(f"[ERROR] {m}")),
            on_complete=lambda d: self.after(0, lambda: self._on_complete(d)),
        )

        self._recorder = PokemonRecorder(
            conn=self._conn,
            pokemon_count=count,
            wait_ms=wait,
            diff_threshold=threshold,
            max_retries=retries,
            callbacks=callbacks,
        )

        threading.Thread(target=self._recorder.run, daemon=True).start()

    def _do_pause(self) -> None:
        if not self._recorder:
            return
        if self._recorder._paused:
            self._recorder.resume()
            self._pause_btn.configure(text="\u23f8  暂停", fg_color="#eab308")
            self._log("已恢复")
        else:
            self._recorder.pause()
            self._pause_btn.configure(text="\u25b6  继续", fg_color="#22c55e")
            self._log("已暂停")

    def _do_stop(self) -> None:
        if self._recorder:
            self._recorder.stop()
        self._reset_buttons()
        self._log("已手动停止")

    def _do_open_dir(self) -> None:
        if not self._recorder:
            return
        d = self._recorder.session_dir
        if not os.path.isdir(d):
            return
        if platform.system() == "Windows":
            os.startfile(d)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", d])
        else:
            subprocess.Popen(["xdg-open", d])

    # ── UI updates ─────────────────────────────────────────────────

    def _update_progress(self, poke_idx: int, poke_total: int, step_idx: int, step_total: int) -> None:
        overall = ((poke_idx - 1) * step_total + step_idx) / (poke_total * step_total)
        self._progress_bar.set(overall)
        self._progress_label.configure(
            text=f"Pokemon {poke_idx}/{poke_total}  |  步骤 {step_idx}/{step_total}",
        )

        # Highlight current step in the table
        for i, lbl in enumerate(self._step_labels):
            if i == step_idx - 1:
                lbl.configure(text_color="#6366f1", font=("Consolas", 11, "bold"))
            elif i < step_idx - 1:
                lbl.configure(text_color="#22c55e", font=("Consolas", 11))
            else:
                lbl.configure(text_color="#6b7280", font=("Consolas", 11))

    def _show_preview(self, img: Image.Image, name: str) -> None:
        cw = max(self._preview_canvas.winfo_width(), 320)
        ch = max(self._preview_canvas.winfo_height(), 180)

        ratio = min(cw / img.width, ch / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)

        self._photo_ref = ImageTk.PhotoImage(resized)
        self._preview_canvas.delete("all")
        self._preview_canvas.create_image(cw // 2, ch // 2, image=self._photo_ref, anchor="center")
        self._preview_name.configure(text=name)

    def _on_complete(self, save_dir: str) -> None:
        self._reset_buttons()
        self._open_dir_btn.configure(state="normal")
        self._progress_bar.set(1.0)
        self._progress_label.configure(text="采集完成!")

    def _reset_buttons(self) -> None:
        self._start_btn.configure(state="normal")
        self._pause_btn.configure(state="disabled", text="\u23f8  暂停", fg_color="#eab308")
        self._stop_btn.configure(state="disabled")

    # ── Log helpers ────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")
