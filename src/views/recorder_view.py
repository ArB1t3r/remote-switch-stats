"""Pokemon Stats Recorder tab — automated multi-Pokemon screenshot collection."""

import os
import platform
import subprocess
import threading
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from src.protocol import SwitchConnection
from src.recorder import PokemonRecorder, RecorderCallbacks, Step, POKEMON_DETAIL_STEPS
from src.page_profile import load_profiles


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
        self._edit_mode = False
        self._custom_steps: list[Step] = list(POKEMON_DETAIL_STEPS)
        self._selected_step_idx: Optional[int] = None

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

        # Right: step table with edit mode
        self._table_frame = ctk.CTkFrame(main, fg_color="transparent")
        self._table_frame.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")

        # Header with edit toggle
        table_header = ctk.CTkFrame(self._table_frame, fg_color="transparent")
        table_header.pack(fill="x", padx=8, pady=(4, 4))

        ctk.CTkLabel(table_header, text="采集步骤", font=("", 14, "bold")).pack(
            side="left",
        )

        self._edit_btn = ctk.CTkButton(
            table_header, text="编辑", width=60, height=26,
            font=("", 11), fg_color="#6366f1", hover_color="#4f46e5",
            command=self._toggle_edit_mode,
        )
        self._edit_btn.pack(side="right", padx=4)

        # Edit toolbar (hidden until edit mode)
        self._edit_toolbar = ctk.CTkFrame(self._table_frame, fg_color="transparent")

        ctk.CTkButton(
            self._edit_toolbar, text="+验证", width=60, height=24,
            font=("", 10), fg_color="#22c55e", hover_color="#16a34a",
            command=self._insert_verify_step,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._edit_toolbar, text="+按键", width=60, height=24,
            font=("", 10), fg_color="#3b82f6", hover_color="#2563eb",
            command=self._insert_press_step,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._edit_toolbar, text="删除", width=50, height=24,
            font=("", 10), fg_color="#ef4444", hover_color="#dc2626",
            command=self._delete_selected_step,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._edit_toolbar, text="上移", width=40, height=24,
            font=("", 10), fg_color="#6b7280", hover_color="#4b5563",
            command=self._move_step_up,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._edit_toolbar, text="下移", width=40, height=24,
            font=("", 10), fg_color="#6b7280", hover_color="#4b5563",
            command=self._move_step_down,
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            self._edit_toolbar, text="重置", width=50, height=24,
            font=("", 10), fg_color="#92400e", hover_color="#78350f",
            command=self._reset_steps,
        ).pack(side="right", padx=2)

        # Step list (scrollable)
        self._step_labels: list[ctk.CTkLabel] = []
        self._steps_scroll = ctk.CTkScrollableFrame(self._table_frame, fg_color="transparent")
        self._steps_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        self._render_step_list()

    # ── Step list rendering ────────────────────────────────────────

    def _render_step_list(self) -> None:
        for w in self._steps_scroll.winfo_children():
            w.destroy()
        self._step_labels.clear()

        for i, step in enumerate(self._custom_steps):
            row = ctk.CTkFrame(self._steps_scroll, fg_color="transparent", height=26)
            row.pack(fill="x", padx=2, pady=1)

            is_selected = (self._edit_mode and i == self._selected_step_idx)

            if step.is_verify:
                text = f"  \u2714 [验证] {step.verify_page}"
                color = "#a78bfa" if not is_selected else "#ffffff"
            else:
                text = f"  {step.screenshot_name}"
                color = "#6b7280" if not is_selected else "#ffffff"

            bg = "#4f46e5" if is_selected else "transparent"

            lbl = ctk.CTkLabel(
                row, text=text, font=("Consolas", 11),
                text_color=color, anchor="w", fg_color=bg,
                corner_radius=4,
            )
            lbl.pack(side="left", fill="x", expand=True)

            if self._edit_mode:
                lbl.bind("<Button-1>", lambda e, idx=i: self._select_step(idx))

            btn_text = step.button if not step.is_verify else ""
            btn_lbl = ctk.CTkLabel(
                row, text=btn_text, font=("Consolas", 10),
                text_color="#4b5563", width=60,
            )
            btn_lbl.pack(side="right")

            self._step_labels.append(lbl)

    def _select_step(self, idx: int) -> None:
        self._selected_step_idx = idx
        self._render_step_list()

    # ── Edit mode ────────────────────────────────────────────────────

    def _toggle_edit_mode(self) -> None:
        self._edit_mode = not self._edit_mode
        if self._edit_mode:
            self._edit_btn.configure(text="完成", fg_color="#22c55e", hover_color="#16a34a")
            self._edit_toolbar.pack(fill="x", padx=8, pady=(0, 4), after=self._edit_toolbar.master.winfo_children()[0])
            # Re-pack toolbar right after header
            self._edit_toolbar.pack_forget()
            self._edit_toolbar.pack(fill="x", padx=8, pady=(0, 4), before=self._steps_scroll)
        else:
            self._edit_btn.configure(text="编辑", fg_color="#6366f1", hover_color="#4f46e5")
            self._edit_toolbar.pack_forget()
            self._selected_step_idx = None
        self._render_step_list()

    def _insert_verify_step(self) -> None:
        """Insert a verify step after the selected step (or at end)."""
        profiles = load_profiles()
        if not profiles:
            self._log("没有已保存的页面配置，请先到「页面配置」标签页创建")
            return

        insert_idx = (self._selected_step_idx + 1) if self._selected_step_idx is not None else len(self._custom_steps)

        # Show a dialog to pick the page name
        dialog = _PagePickerDialog(self, profiles=[p.name for p in profiles])
        self.wait_window(dialog)

        if dialog.result:
            step = Step(
                button="", screenshot_name="",
                action="verify", verify_page=dialog.result,
            )
            self._custom_steps.insert(insert_idx, step)
            self._selected_step_idx = insert_idx
            self._render_step_list()

    def _insert_press_step(self) -> None:
        """Insert a button-press step after the selected step (or at end)."""
        insert_idx = (self._selected_step_idx + 1) if self._selected_step_idx is not None else len(self._custom_steps)

        dialog = _PressStepDialog(self)
        self.wait_window(dialog)

        if dialog.result:
            button, name = dialog.result
            step = Step(button=button, screenshot_name=name)
            self._custom_steps.insert(insert_idx, step)
            self._selected_step_idx = insert_idx
            self._render_step_list()

    def _delete_selected_step(self) -> None:
        if self._selected_step_idx is None:
            return
        del self._custom_steps[self._selected_step_idx]
        if self._selected_step_idx >= len(self._custom_steps):
            self._selected_step_idx = len(self._custom_steps) - 1 if self._custom_steps else None
        self._render_step_list()

    def _move_step_up(self) -> None:
        idx = self._selected_step_idx
        if idx is None or idx == 0:
            return
        self._custom_steps[idx - 1], self._custom_steps[idx] = self._custom_steps[idx], self._custom_steps[idx - 1]
        self._selected_step_idx = idx - 1
        self._render_step_list()

    def _move_step_down(self) -> None:
        idx = self._selected_step_idx
        if idx is None or idx >= len(self._custom_steps) - 1:
            return
        self._custom_steps[idx + 1], self._custom_steps[idx] = self._custom_steps[idx], self._custom_steps[idx + 1]
        self._selected_step_idx = idx + 1
        self._render_step_list()

    def _reset_steps(self) -> None:
        self._custom_steps = list(POKEMON_DETAIL_STEPS)
        self._selected_step_idx = None
        self._render_step_list()

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
            steps=self._custom_steps,
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

        for i, lbl in enumerate(self._step_labels):
            if i == step_idx - 1:
                lbl.configure(text_color="#6366f1", font=("Consolas", 11, "bold"))
            elif i < step_idx - 1:
                lbl.configure(text_color="#22c55e", font=("Consolas", 11))
            else:
                step = self._custom_steps[i] if i < len(self._custom_steps) else None
                color = "#a78bfa" if (step and step.is_verify) else "#6b7280"
                lbl.configure(text_color=color, font=("Consolas", 11))

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


# ── Dialogs ──────────────────────────────────────────────────────────


class _PagePickerDialog(ctk.CTkToplevel):
    """Modal dialog to pick a page profile name."""

    def __init__(self, parent: ctk.CTkBaseClass, profiles: list[str]) -> None:
        super().__init__(parent)
        self.title("选择验证页面")
        self.geometry("300x200")
        self.resizable(False, False)
        self.result: Optional[str] = None

        self.grab_set()
        self.focus_set()

        ctk.CTkLabel(self, text="选择要验证的页面:", font=("", 13)).pack(
            padx=16, pady=(16, 8), anchor="w",
        )

        self._listbox_frame = ctk.CTkScrollableFrame(self, height=100)
        self._listbox_frame.pack(fill="x", padx=16, pady=4)

        self._selected: Optional[str] = None
        self._buttons: list[ctk.CTkButton] = []

        for name in profiles:
            btn = ctk.CTkButton(
                self._listbox_frame, text=name, height=28,
                fg_color="#334155", hover_color="#475569",
                command=lambda n=name: self._pick(n),
            )
            btn.pack(fill="x", padx=4, pady=2)
            self._buttons.append(btn)

    def _pick(self, name: str) -> None:
        self.result = name
        self.destroy()


class _PressStepDialog(ctk.CTkToplevel):
    """Modal dialog to add a button-press step."""

    COMMON_BUTTONS = ["A", "B", "X", "Y", "DUP", "DDOWN", "DLEFT", "DRIGHT", "L", "R", "ZL", "ZR", "PLUS", "MINUS"]

    def __init__(self, parent: ctk.CTkBaseClass) -> None:
        super().__init__(parent)
        self.title("添加按键步骤")
        self.geometry("320x220")
        self.resizable(False, False)
        self.result: Optional[tuple[str, str]] = None

        self.grab_set()
        self.focus_set()

        ctk.CTkLabel(self, text="按键:", font=("", 13)).pack(padx=16, pady=(16, 4), anchor="w")
        self._btn_var = ctk.StringVar(value="A")
        btn_menu = ctk.CTkOptionMenu(
            self, variable=self._btn_var,
            values=self.COMMON_BUTTONS, width=200,
        )
        btn_menu.pack(padx=16, pady=(0, 8), anchor="w")

        ctk.CTkLabel(self, text="截图名称:", font=("", 13)).pack(padx=16, pady=(8, 4), anchor="w")
        self._name_entry = ctk.CTkEntry(self, width=200, placeholder_text="例: custom_page")
        self._name_entry.pack(padx=16, pady=(0, 12), anchor="w")

        ctk.CTkButton(
            self, text="确定", width=100, fg_color="#6366f1", hover_color="#4f46e5",
            command=self._confirm,
        ).pack(pady=(8, 16))

    def _confirm(self) -> None:
        button = self._btn_var.get()
        name = self._name_entry.get().strip()
        if not name:
            name = f"step_{button.lower()}"
        self.result = (button, name)
        self.destroy()
