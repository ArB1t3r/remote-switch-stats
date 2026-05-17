"""Pokemon Stats Recorder tab — automated multi-Pokemon screenshot collection."""

import os
import platform
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from src import theme
from src.protocol import SwitchConnection
from src.recorder import (
    PokemonRecorder, RecorderCallbacks, RecorderProgress,
    Step, POKEMON_DETAIL_STEPS,
)
from src.page_profile import load_profiles


ALL_BUTTONS = [
    "A", "B", "X", "Y",
    "DUP", "DDOWN", "DLEFT", "DRIGHT",
    "L", "R", "ZL", "ZR",
    "PLUS", "MINUS", "HOME", "CAPTURE",
    "LSTICK", "RSTICK",
]


def _step_display(step: Step) -> str:
    """Human-readable one-line description of a step."""
    if step.is_verify:
        return f"✔ 验证页面: {step.verify_page}"
    label = f"按 {step.button}"
    if step.screenshot_name:
        label += f"  →  截图 [{step.screenshot_name}]"
    return label


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
        self._custom_steps: list[Step] = list(POKEMON_DETAIL_STEPS)
        self._selected_idx: Optional[int] = None
        self._drag_idx: Optional[int] = None
        self._drag_target: Optional[int] = None
        self._is_running = False
        self._running_step_idx: Optional[int] = None  # 0-indexed current step
        self._running_pokemon_idx: int = 0            # 1-indexed current pokemon
        self._completed_step_idx: int = -1            # last completed step (0-indexed)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_config()
        self._build_controls()
        self._build_main_area()
        self._build_log()

    # ── Config panel ───────────────────────────────────────────────

    def _build_config(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=theme.CORNER_LG)
        sec.grid(row=0, column=0, padx=theme.SECTION_PADX, pady=(16, 8), sticky="ew")

        ctk.CTkLabel(sec, text="Pokemon 信息采集", font=theme.FONT_TITLE).pack(
            padx=16, pady=(12, 4), anchor="w",
        )
        ctk.CTkLabel(
            sec, font=theme.FONT_HINT, text_color=theme.TEXT_MUTED,
            text="右侧步骤列表可直接编辑：点击选中、拖拽排序、工具栏添加/删除指令",
        ).pack(padx=16, pady=(0, 8), anchor="w")

        # Use grid for the params row so labels/entries align even when window resizes.
        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))
        for i in (1, 3, 5, 7):
            row.grid_columnconfigure(i, weight=0)
        row.grid_columnconfigure(8, weight=1)

        ctk.CTkLabel(row, text="采集数量:").grid(row=0, column=0, padx=(0, 4), sticky="w")
        self._count_entry = ctk.CTkEntry(row, width=60, placeholder_text="6")
        self._count_entry.insert(0, "6")
        self._count_entry.grid(row=0, column=1, padx=(0, 16))

        ctk.CTkLabel(row, text="每步等待(ms):").grid(row=0, column=2, padx=(0, 4), sticky="w")
        self._wait_entry = ctk.CTkEntry(row, width=70, placeholder_text="500")
        self._wait_entry.insert(0, "500")
        self._wait_entry.grid(row=0, column=3, padx=(0, 16))

        ctk.CTkLabel(row, text="差异阈值:").grid(row=0, column=4, padx=(0, 4), sticky="w")
        self._threshold_entry = ctk.CTkEntry(row, width=70, placeholder_text="0.02")
        self._threshold_entry.insert(0, "0.02")
        self._threshold_entry.grid(row=0, column=5, padx=(0, 16))

        ctk.CTkLabel(row, text="最大重试:").grid(row=0, column=6, padx=(0, 4), sticky="w")
        self._retry_entry = ctk.CTkEntry(row, width=50, placeholder_text="3")
        self._retry_entry.insert(0, "3")
        self._retry_entry.grid(row=0, column=7, padx=(0, 4))

    # ── Control buttons ────────────────────────────────────────────

    def _build_controls(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=theme.CORNER_LG)
        sec.grid(row=1, column=0, padx=theme.SECTION_PADX, pady=4, sticky="ew")

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=10)

        self._start_btn = ctk.CTkButton(
            row, text="▶  开始采集", width=120, height=theme.BTN_H_LG,
            fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER,
            font=theme.FONT_SUBSECTION,
            command=self._do_start,
        )
        self._start_btn.pack(side="left", padx=4)

        self._pause_btn = ctk.CTkButton(
            row, text="⏸  暂停", width=80, height=theme.BTN_H_LG,
            fg_color=theme.WARNING, hover_color=theme.WARNING_HOVER,
            font=theme.FONT_SUBSECTION,
            command=self._do_pause, state="disabled",
        )
        self._pause_btn.pack(side="left", padx=4)

        self._stop_btn = ctk.CTkButton(
            row, text="■  停止", width=80, height=theme.BTN_H_LG,
            fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            font=theme.FONT_SUBSECTION,
            command=self._do_stop, state="disabled",
        )
        self._stop_btn.pack(side="left", padx=4)

        self._open_dir_btn = ctk.CTkButton(
            row, text="打开保存目录", width=110, height=theme.BTN_H_LG,
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            command=self._do_open_dir, state="disabled",
        )
        self._open_dir_btn.pack(side="right", padx=4)

        # Progress
        prog_row = ctk.CTkFrame(sec, fg_color="transparent")
        prog_row.pack(fill="x", padx=16, pady=(0, 10))

        self._progress_bar = ctk.CTkProgressBar(prog_row)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", side="left", expand=True, padx=(0, 8))

        self._progress_label = ctk.CTkLabel(
            prog_row, text="就绪", font=theme.FONT_BODY,
            text_color=theme.TEXT_MUTED, width=260,
        )
        self._progress_label.pack(side="right")

    # ── Main area: preview + step editor ─────────────────────────

    def _build_main_area(self) -> None:
        main = ctk.CTkFrame(self, corner_radius=theme.CORNER_LG)
        main.grid(row=2, column=0, padx=theme.SECTION_PADX, pady=4, sticky="nsew")
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        # Left: screenshot preview
        preview_frame = ctk.CTkFrame(main, fg_color="transparent")
        preview_frame.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(preview_frame, text="实时预览", font=theme.FONT_SUBSECTION).grid(
            row=0, column=0, padx=8, pady=(4, 0), sticky="w",
        )
        self._preview_canvas = tk.Canvas(
            preview_frame, bg=theme.SURFACE_DARK, highlightthickness=0,
        )
        self._preview_canvas.grid(row=1, column=0, padx=8, pady=8, sticky="nsew")
        self._preview_name = ctk.CTkLabel(
            preview_frame, text="", font=theme.FONT_MONO, text_color=theme.TEXT_MUTED,
        )
        self._preview_name.grid(row=2, column=0, padx=8, pady=(0, 4))

        # Right: step editor
        editor_frame = ctk.CTkFrame(main, fg_color="transparent")
        editor_frame.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        editor_frame.grid_rowconfigure(2, weight=1)
        editor_frame.grid_columnconfigure(0, weight=1)

        # Header
        ctk.CTkLabel(editor_frame, text="采集步骤", font=theme.FONT_SUBSECTION).grid(
            row=0, column=0, padx=8, pady=(4, 2), sticky="w",
        )

        # Toolbar (always visible)
        self._build_editor_toolbar(editor_frame)

        # Step list
        self._steps_scroll = ctk.CTkScrollableFrame(editor_frame, fg_color=theme.SURFACE_MID)
        self._steps_scroll.grid(row=2, column=0, padx=4, pady=4, sticky="nsew")

        # Step count label
        self._step_count_label = ctk.CTkLabel(
            editor_frame, text="", font=theme.FONT_SMALL, text_color=theme.TEXT_SUBTLE,
        )
        self._step_count_label.grid(row=3, column=0, padx=8, pady=(2, 4), sticky="w")

        self._render_step_list()

    def _build_editor_toolbar(self, parent: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(parent, fg_color=theme.SURFACE_HEADER, corner_radius=theme.CORNER_MD, height=36)
        bar.grid(row=1, column=0, padx=4, pady=(2, 4), sticky="ew")

        self._toolbar_buttons: list[ctk.CTkButton] = []

        btn_add_press = ctk.CTkButton(
            bar, text="+ 按键", width=60, height=theme.BTN_H_SM,
            font=theme.FONT_BODY_BOLD, fg_color=theme.TOKEN_FACE, hover_color=theme.TOKEN_FACE_HOVER,
            command=self._add_press_step,
        )
        btn_add_press.pack(side="left", padx=(6, 2), pady=5)
        self._toolbar_buttons.append(btn_add_press)

        btn_add_verify = ctk.CTkButton(
            bar, text="+ 验证", width=60, height=theme.BTN_H_SM,
            font=theme.FONT_BODY_BOLD, fg_color="#8b5cf6", hover_color="#7c3aed",
            command=self._add_verify_step,
        )
        btn_add_verify.pack(side="left", padx=2, pady=5)
        self._toolbar_buttons.append(btn_add_verify)

        btn_delete = ctk.CTkButton(
            bar, text="✖", width=30, height=theme.BTN_H_SM,
            font=("", 12), fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            command=self._delete_selected,
        )
        btn_delete.pack(side="left", padx=(8, 2), pady=5)
        self._toolbar_buttons.append(btn_delete)

        btn_up = ctk.CTkButton(
            bar, text="▲", width=28, height=theme.BTN_H_SM,
            font=("", 11), fg_color=theme.NEUTRAL_SOFT, hover_color=theme.NEUTRAL_SOFT_HOVER,
            command=self._move_up,
        )
        btn_up.pack(side="left", padx=1, pady=5)
        self._toolbar_buttons.append(btn_up)

        btn_down = ctk.CTkButton(
            bar, text="▼", width=28, height=theme.BTN_H_SM,
            font=("", 11), fg_color=theme.NEUTRAL_SOFT, hover_color=theme.NEUTRAL_SOFT_HOVER,
            command=self._move_down,
        )
        btn_down.pack(side="left", padx=1, pady=5)
        self._toolbar_buttons.append(btn_down)

        btn_reset = ctk.CTkButton(
            bar, text="重置默认", width=70, height=theme.BTN_H_SM,
            font=theme.FONT_SMALL, fg_color="#92400e", hover_color="#78350f",
            command=self._reset_steps,
        )
        btn_reset.pack(side="right", padx=(2, 6), pady=5)
        self._toolbar_buttons.append(btn_reset)

    # ── Step list rendering ──────────────────────────────────────

    def _render_step_list(self) -> None:
        for w in self._steps_scroll.winfo_children():
            w.destroy()

        for i, step in enumerate(self._custom_steps):
            is_selected = (not self._is_running) and (i == self._selected_idx)
            is_drag_target = (not self._is_running) and (i == self._drag_target)

            # Running-mode states take priority
            is_current = self._is_running and (i == self._running_step_idx)
            is_done = self._is_running and (i <= self._completed_step_idx)

            if is_current:
                bg = theme.RUNNING_BG
            elif is_done:
                bg = theme.DONE_BG
            elif is_selected:
                bg = theme.SELECT_BG
            elif is_drag_target:
                bg = theme.DRAG_BG
            else:
                bg = "transparent"

            frame_kwargs = {
                "height": 32,
                "corner_radius": theme.CORNER_SM,
                "fg_color": bg,
            }
            if is_drag_target:
                frame_kwargs["border_width"] = 1
                frame_kwargs["border_color"] = theme.DRAG_BORDER

            row = ctk.CTkFrame(self._steps_scroll, **frame_kwargs)
            row.pack(fill="x", padx=2, pady=1)
            row.pack_propagate(False)

            # Status indicator (replaces drag handle when running)
            if is_current:
                status_text, status_color = "▶", "#fef08a"
            elif is_done:
                status_text, status_color = "✓", "#bbf7d0"
            else:
                status_text, status_color = "", theme.TEXT_SUBTLE

            idx_lbl = ctk.CTkLabel(
                row, text=f"{i+1:2d}.", width=28,
                font=theme.FONT_MONO_XS,
                text_color="#94a3b8" if (is_current or is_done) else theme.TEXT_SUBTLE,
            )
            idx_lbl.pack(side="left", padx=(4, 0))

            if status_text:
                ctk.CTkLabel(
                    row, text=status_text, width=14,
                    font=("", 12, "bold"), text_color=status_color,
                ).pack(side="left", padx=(0, 2))

            # Step type indicator
            if step.is_verify:
                type_color = "#fef08a" if is_current else ("#dcfce7" if is_done else "#a78bfa")
                type_text = "验证"
            else:
                type_color = "#fef08a" if is_current else ("#dcfce7" if is_done else "#38bdf8")
                type_text = step.button
            type_lbl = ctk.CTkLabel(
                row, text=type_text, width=50,
                font=theme.FONT_MONO_BOLD, text_color=type_color,
            )
            type_lbl.pack(side="left", padx=(2, 4))

            # Description
            desc = step.verify_page if step.is_verify else step.screenshot_name
            if is_current or is_done:
                text_color = theme.TEXT_PRIMARY
            elif is_selected:
                text_color = "#e2e8f0"
            else:
                text_color = theme.TEXT_ON_DARK
            desc_lbl = ctk.CTkLabel(
                row, text=desc, anchor="w",
                font=theme.FONT_MONO_SM, text_color=text_color,
            )
            desc_lbl.pack(side="left", fill="x", expand=True, padx=2)

            # Drag handle (hidden during running)
            if not self._is_running:
                handle = ctk.CTkLabel(
                    row, text="☰", width=20,
                    font=("", 12), text_color=theme.NEUTRAL, cursor="hand2",
                )
                handle.pack(side="right", padx=(2, 6))

                handle.bind("<Button-1>", lambda e, idx=i: self._on_drag_start(e, idx))
                handle.bind("<B1-Motion>", self._on_drag_motion)
                handle.bind("<ButtonRelease-1>", self._on_drag_end)

                # Bind click to select
                for widget in (row, idx_lbl, type_lbl, desc_lbl):
                    widget.bind("<Button-1>", lambda e, idx=i: self._on_click(idx))

        if self._is_running:
            self._step_count_label.configure(
                text=f"运行中 · 宝可梦 {self._running_pokemon_idx} · 步骤 {(self._running_step_idx or 0) + 1}/{len(self._custom_steps)}"
            )
        else:
            self._step_count_label.configure(
                text=f"共 {len(self._custom_steps)} 步  |  点击选中 · 拖拽 ☰ 排序"
            )

    def _on_click(self, idx: int) -> None:
        self._selected_idx = idx if self._selected_idx != idx else None
        self._render_step_list()

    def _on_drag_start(self, event: tk.Event, idx: int) -> None:
        self._drag_idx = idx
        self._selected_idx = idx
        self._drag_target = None

    def _on_drag_motion(self, event: tk.Event) -> None:
        if self._drag_idx is None:
            return
        # Determine target index based on mouse y position relative to scroll frame
        children = self._steps_scroll.winfo_children()
        if not children:
            return

        # Get mouse y relative to the scroll frame
        try:
            y = event.widget.winfo_pointery() - self._steps_scroll.winfo_rooty()
        except Exception:
            return

        row_h = 34  # approximate row height
        target = max(0, min(len(self._custom_steps) - 1, int(y / row_h)))

        if target != self._drag_target:
            self._drag_target = target
            self._render_step_list()

    def _on_drag_end(self, event: tk.Event) -> None:
        if self._drag_idx is not None and self._drag_target is not None:
            if self._drag_idx != self._drag_target:
                step = self._custom_steps.pop(self._drag_idx)
                self._custom_steps.insert(self._drag_target, step)
                self._selected_idx = self._drag_target
        self._drag_idx = None
        self._drag_target = None
        self._render_step_list()

    # ── Editor actions ───────────────────────────────────────────

    def _add_press_step(self) -> None:
        dialog = _PressStepDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            button, name, capture = dialog.result
            step = Step(button=button, screenshot_name=name if capture else "")
            insert_at = (self._selected_idx + 1) if self._selected_idx is not None else len(self._custom_steps)
            self._custom_steps.insert(insert_at, step)
            self._selected_idx = insert_at
            self._render_step_list()

    def _add_verify_step(self) -> None:
        profiles = load_profiles()
        if not profiles:
            self._log("没有已配置的页面，请先到「页面配置」标签页创建")
            return
        dialog = _PagePickerDialog(self, profiles=[p.name for p in profiles])
        self.wait_window(dialog)
        if dialog.result:
            step = Step(button="", screenshot_name="", action="verify", verify_page=dialog.result)
            insert_at = (self._selected_idx + 1) if self._selected_idx is not None else len(self._custom_steps)
            self._custom_steps.insert(insert_at, step)
            self._selected_idx = insert_at
            self._render_step_list()

    def _delete_selected(self) -> None:
        if self._selected_idx is None:
            return
        del self._custom_steps[self._selected_idx]
        if self._selected_idx >= len(self._custom_steps):
            self._selected_idx = len(self._custom_steps) - 1 if self._custom_steps else None
        self._render_step_list()

    def _move_up(self) -> None:
        idx = self._selected_idx
        if idx is None or idx == 0:
            return
        self._custom_steps[idx - 1], self._custom_steps[idx] = self._custom_steps[idx], self._custom_steps[idx - 1]
        self._selected_idx = idx - 1
        self._render_step_list()

    def _move_down(self) -> None:
        idx = self._selected_idx
        if idx is None or idx >= len(self._custom_steps) - 1:
            return
        self._custom_steps[idx + 1], self._custom_steps[idx] = self._custom_steps[idx], self._custom_steps[idx + 1]
        self._selected_idx = idx + 1
        self._render_step_list()

    def _reset_steps(self) -> None:
        self._custom_steps = list(POKEMON_DETAIL_STEPS)
        self._selected_idx = None
        self._render_step_list()

    # ── Log ────────────────────────────────────────────────────────

    def _build_log(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=theme.CORNER_LG)
        sec.grid(row=3, column=0, padx=theme.SECTION_PADX, pady=(4, 16), sticky="ew")
        sec.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(sec, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(header, text="采集日志", font=theme.FONT_SUBSECTION).pack(side="left")
        ctk.CTkButton(
            header, text="清空", width=50, height=24,
            fg_color=theme.NEUTRAL_SOFT, hover_color=theme.NEUTRAL_SOFT_HOVER,
            command=self._clear_log,
        ).pack(side="right")

        self._log_text = ctk.CTkTextbox(sec, height=120, font=theme.FONT_MONO_SM, state="disabled")
        self._log_text.pack(fill="x", padx=16, pady=(0, 10))

    # ── Actions ────────────────────────────────────────────────────

    def _do_start(self) -> None:
        if not self._conn.connected:
            self._log("未连接到 Switch，请先在「设置与连接」页连接")
            return

        if not self._custom_steps:
            self._log("步骤列表为空，请添加至少一个步骤")
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
            on_verify_failed=lambda page, prog: self.after(
                0, lambda p=page, pr=prog: self._on_verify_failed(p, pr),
            ),
            on_state_changed=lambda is_run: self.after(
                0, lambda r=is_run: self._set_running_state(r),
            ),
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
        if self._recorder.is_paused:
            self._recorder.resume()
            self._pause_btn.configure(text="⏸  暂停", fg_color=theme.WARNING)
            self._log("已恢复")
        else:
            self._recorder.pause()
            self._pause_btn.configure(text="▶  继续", fg_color=theme.SUCCESS)
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
        pct = int(overall * 100)
        self._progress_label.configure(
            text=f"{pct}%  ·  Pokemon {poke_idx}/{poke_total}  ·  步骤 {step_idx}/{step_total}",
            text_color=theme.TEXT_PRIMARY,
        )
        self._running_pokemon_idx = poke_idx
        self._completed_step_idx = self._running_step_idx if self._running_step_idx is not None else -1
        # New pokemon — reset completed marker
        if step_idx == 1:
            self._completed_step_idx = -1
        self._running_step_idx = step_idx - 1
        self._render_step_list()

    def _set_running_state(self, is_running: bool) -> None:
        self._is_running = is_running
        for btn in self._toolbar_buttons:
            btn.configure(state="disabled" if is_running else "normal")
        if not is_running:
            self._running_step_idx = None
            self._completed_step_idx = -1
        self._render_step_list()

    def _on_verify_failed(self, page_name: str, progress: RecorderProgress) -> None:
        title = "验证失败"
        msg = (
            f"页面验证失败: 「{page_name}」\n\n"
            f"进度统计:\n"
            f"  · 已完成宝可梦: {progress.pokemon_done} / {progress.pokemon_total}\n"
            f"  · 当前正在采集第 {progress.current_pokemon} 只\n"
            f"  · 当前步骤: {progress.current_step} / {progress.total_steps_per_pokemon}\n"
            f"  · 已保存截图: {progress.screenshots_taken} 张\n\n"
            "采集已暂停，请检查 Switch 当前界面后点「继续」恢复，或点「停止」结束采集。"
        )
        self._log(f"[暂停] {title}: {page_name}")
        messagebox.showwarning(title, msg, parent=self.winfo_toplevel())

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
        self._progress_label.configure(text="100%  ·  采集完成!", text_color=theme.SUCCESS)

    def _reset_buttons(self) -> None:
        self._start_btn.configure(state="normal")
        self._pause_btn.configure(state="disabled", text="⏸  暂停", fg_color=theme.WARNING)
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
        self.geometry("300x220")
        self.resizable(False, False)
        self.result: Optional[str] = None

        self.grab_set()
        self.focus_set()

        ctk.CTkLabel(self, text="选择要验证的页面:", font=theme.FONT_BODY).pack(
            padx=16, pady=(16, 8), anchor="w",
        )

        scroll = ctk.CTkScrollableFrame(self, height=120)
        scroll.pack(fill="x", padx=16, pady=4)

        for name in profiles:
            ctk.CTkButton(
                scroll, text=name, height=30, anchor="w",
                fg_color=theme.SLATE, hover_color=theme.SLATE_HOVER,
                command=lambda n=name: self._pick(n),
            ).pack(fill="x", padx=4, pady=2)

    def _pick(self, name: str) -> None:
        self.result = name
        self.destroy()


class _PressStepDialog(ctk.CTkToplevel):
    """Modal dialog to add a button-press + optional capture step."""

    def __init__(self, parent: ctk.CTkBaseClass) -> None:
        super().__init__(parent)
        self.title("添加按键指令")
        self.geometry("340x280")
        self.resizable(False, False)
        self.result: Optional[tuple[str, str, bool]] = None  # (button, name, capture)

        self.grab_set()
        self.focus_set()

        # Button selection
        ctk.CTkLabel(self, text="按键:", font=theme.FONT_BODY).pack(padx=16, pady=(16, 4), anchor="w")
        self._btn_var = ctk.StringVar(value="A")
        ctk.CTkOptionMenu(
            self, variable=self._btn_var,
            values=ALL_BUTTONS, width=200,
        ).pack(padx=16, pady=(0, 8), anchor="w")

        # Capture toggle
        self._capture_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self, text="按键后截图", variable=self._capture_var,
            command=self._toggle_capture,
        ).pack(padx=16, pady=(4, 4), anchor="w")

        # Screenshot name
        ctk.CTkLabel(self, text="截图名称:", font=theme.FONT_BODY).pack(padx=16, pady=(8, 4), anchor="w")
        self._name_entry = ctk.CTkEntry(self, width=220, placeholder_text="例: moves_page_1")
        self._name_entry.pack(padx=16, pady=(0, 12), anchor="w")
        self._name_entry.bind("<Return>", lambda e: self._confirm())

        ctk.CTkButton(
            self, text="确定添加", width=120, height=theme.BTN_H_MD,
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            command=self._confirm,
        ).pack(pady=(8, 16))

    def _toggle_capture(self) -> None:
        state = "normal" if self._capture_var.get() else "disabled"
        self._name_entry.configure(state=state)

    def _confirm(self) -> None:
        button = self._btn_var.get()
        capture = self._capture_var.get()
        name = self._name_entry.get().strip() if capture else ""
        if capture and not name:
            name = f"cap_{button.lower()}"
        self.result = (button, name, capture)
        self.destroy()
