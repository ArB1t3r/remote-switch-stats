"""Macro / sequence tab — build, save, and play command sequences."""

import json
import os
import threading
import time
import customtkinter as ctk

from src import theme
from src.protocol import SwitchConnection, BUTTONS


PRESETS = {
    "A 连打 (10次)": "A,W200,A,W200,A,W200,A,W200,A,W200,A,W200,A,W200,A,W200,A,W200,A",
    "导航: 右→右→A": "DRIGHT,W300,DRIGHT,W300,A",
    "导航: 下→下→A": "DDOWN,W300,DDOWN,W300,A",
    "Home 键": "HOME",
    "截图": "CAPTURE",
}

# Quick-builder token groups (button label, color, hover)
QUICK_FACE = [("A", theme.TOKEN_FACE), ("B", theme.TOKEN_FACE),
              ("X", theme.TOKEN_FACE), ("Y", theme.TOKEN_FACE)]
QUICK_DPAD = [("DUP", theme.TOKEN_DPAD), ("DDOWN", theme.TOKEN_DPAD),
              ("DLEFT", theme.TOKEN_DPAD), ("DRIGHT", theme.TOKEN_DPAD)]
QUICK_SHOULDER = [("L", theme.TOKEN_SHOULDER), ("R", theme.TOKEN_SHOULDER),
                  ("ZL", theme.TOKEN_SHOULDER), ("ZR", theme.TOKEN_SHOULDER)]
QUICK_SYSTEM = [("PLUS", theme.TOKEN_SYSTEM), ("MINUS", theme.TOKEN_SYSTEM),
                ("HOME", theme.ACCENT), ("CAPTURE", theme.INFO)]
QUICK_WAIT = [("W200", theme.TOKEN_WAIT), ("W500", theme.TOKEN_WAIT),
              ("W1000", theme.TOKEN_WAIT), ("W2000", theme.TOKEN_WAIT)]


class MacroView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        conn: SwitchConnection,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._conn = conn
        self._running = False
        self.grid_columnconfigure(0, weight=1)

        self._build_editor()
        self._build_presets()
        self._build_quick_builder()
        self._build_log()

    # ── Sequence editor ────────────────────────────────────────────

    def _build_editor(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=theme.CORNER_LG)
        sec.grid(row=0, column=0, padx=theme.SECTION_PADX, pady=(16, 8), sticky="ew")
        sec.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sec, text="宏序列编辑器", font=theme.FONT_SECTION).pack(
            padx=16, pady=(12, 4), anchor="w",
        )

        ctk.CTkLabel(
            sec, font=theme.FONT_HINT, text_color=theme.TEXT_MUTED,
            text="语法: 按键名=click, +按键=press, -按键=release, W毫秒=等待, "
                 "%X,Y=左摇杆, &X,Y=右摇杆。用逗号分隔。",
        ).pack(padx=16, pady=(0, 4), anchor="w")

        self._seq_text = ctk.CTkTextbox(sec, height=100, font=theme.FONT_MONO)
        self._seq_text.pack(fill="x", padx=16, pady=4)
        self._seq_text.insert("1.0", "A,W500,B,W500,A")

        btn_row = ctk.CTkFrame(sec, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 12))

        self._run_btn = ctk.CTkButton(
            btn_row, text="▶  执行", width=100, height=theme.BTN_H_MD,
            fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER,
            command=self._do_run,
        )
        self._run_btn.pack(side="left", padx=4)

        self._cancel_btn = ctk.CTkButton(
            btn_row, text="■  取消", width=100, height=theme.BTN_H_MD,
            fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            command=self._do_cancel, state="disabled",
        )
        self._cancel_btn.pack(side="left", padx=4)

        self._loop_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            btn_row, text="循环执行", variable=self._loop_var,
        ).pack(side="left", padx=12)

        ctk.CTkLabel(btn_row, text="循环次数:").pack(side="left", padx=(8, 4))
        self._loop_count = ctk.CTkEntry(btn_row, width=60, placeholder_text="∞")
        self._loop_count.pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row, text="保存", width=60, height=theme.BTN_H_MD,
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            command=self._do_save,
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            btn_row, text="加载", width=60, height=theme.BTN_H_MD,
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER,
            command=self._do_load,
        ).pack(side="right", padx=4)

    # ── Presets ────────────────────────────────────────────────────

    def _build_presets(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=theme.CORNER_LG)
        sec.grid(row=1, column=0, padx=theme.SECTION_PADX, pady=8, sticky="ew")

        ctk.CTkLabel(sec, text="预设宏", font=theme.FONT_SUBSECTION).pack(
            padx=16, pady=(12, 4), anchor="w",
        )
        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 12))

        for name, seq in PRESETS.items():
            ctk.CTkButton(
                row, text=name, height=theme.BTN_H_MD,
                fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                command=lambda s=seq: self._insert_preset(s),
            ).pack(side="left", padx=4)

    def _insert_preset(self, seq: str) -> None:
        self._seq_text.delete("1.0", "end")
        self._seq_text.insert("1.0", seq)

    # ── Quick builder ──────────────────────────────────────────────

    def _build_quick_builder(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=theme.CORNER_LG)
        sec.grid(row=2, column=0, padx=theme.SECTION_PADX, pady=8, sticky="ew")

        ctk.CTkLabel(sec, text="快速构建", font=theme.FONT_SUBSECTION).pack(
            padx=16, pady=(12, 4), anchor="w",
        )

        self._build_token_row(sec, "功能键", QUICK_FACE)
        self._build_token_row(sec, "方向", QUICK_DPAD)
        self._build_token_row(sec, "肩键", QUICK_SHOULDER)
        self._build_token_row(sec, "系统", QUICK_SYSTEM)
        self._build_token_row(sec, "等待", QUICK_WAIT, last=True)

    def _build_token_row(
        self, parent: ctk.CTkFrame, label: str,
        tokens: list[tuple[str, str]], last: bool = False,
    ) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(2, 12 if last else 2))

        ctk.CTkLabel(
            row, text=label, width=40, anchor="w",
            font=theme.FONT_HINT, text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))

        for btn, color in tokens:
            ctk.CTkButton(
                row, text=btn, width=64, height=theme.BTN_H_SM,
                fg_color=color, hover_color=theme.darken(color, 0.85),
                font=theme.FONT_BODY_BOLD,
                command=lambda v=btn: self._append_to_seq(v),
            ).pack(side="left", padx=2)

    def _append_to_seq(self, token: str) -> None:
        current = self._seq_text.get("1.0", "end").strip()
        if current:
            self._seq_text.insert("end", f",{token}")
        else:
            self._seq_text.insert("end", token)

    # ── Execution ──────────────────────────────────────────────────

    def _do_run(self) -> None:
        seq = self._seq_text.get("1.0", "end").strip()
        if not seq:
            return
        self._running = True
        self._run_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._log_msg(f"▶ 执行序列: {seq[:80]}{'…' if len(seq) > 80 else ''}")

        def _task() -> None:
            loop = self._loop_var.get()
            count_str = self._loop_count.get().strip()
            max_loops = int(count_str) if count_str.isdigit() else 999999
            iteration = 0

            while self._running and (not loop or iteration < max_loops):
                resp = self._conn.click_seq(seq)
                iteration += 1
                self.after(0, lambda i=iteration, r=resp: self._log_msg(
                    f"  轮次 {i} 完成 (resp: {r})",
                ))
                if not loop:
                    break
                time.sleep(0.1)

            self._running = False
            self.after(0, self._execution_done)

        threading.Thread(target=_task, daemon=True).start()

    def _do_cancel(self) -> None:
        self._running = False
        threading.Thread(target=self._conn.click_cancel, daemon=True).start()
        self._log_msg("■ 已取消执行")
        self._execution_done()

    def _execution_done(self) -> None:
        self._run_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")

    # ── Save / Load ────────────────────────────────────────────────

    def _do_save(self) -> None:
        seq = self._seq_text.get("1.0", "end").strip()
        save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        path = os.path.join(save_dir, "switch_macro.json")
        try:
            data = {"sequence": seq, "loop": self._loop_var.get()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._log_msg(f"已保存: {path}")
        except Exception as e:
            self._log_msg(f"保存失败: {e}")

    def _do_load(self) -> None:
        path = os.path.join(os.path.expanduser("~"), "Desktop", "switch_macro.json")
        if not os.path.exists(path):
            self._log_msg(f"文件不存在: {path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._seq_text.delete("1.0", "end")
            self._seq_text.insert("1.0", data.get("sequence", ""))
            self._loop_var.set(data.get("loop", False))
            self._log_msg(f"已加载: {path}")
        except Exception as e:
            self._log_msg(f"加载失败: {e}")

    # ── Log ────────────────────────────────────────────────────────

    def _build_log(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=theme.CORNER_LG)
        sec.grid(row=3, column=0, padx=theme.SECTION_PADX, pady=(8, 16), sticky="ew")
        sec.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(sec, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(header, text="执行日志", font=theme.FONT_SUBSECTION).pack(side="left")
        ctk.CTkButton(
            header, text="清空", width=50, height=24,
            fg_color=theme.NEUTRAL_SOFT, hover_color=theme.NEUTRAL_SOFT_HOVER,
            command=self._clear_log,
        ).pack(side="right")

        self._log = ctk.CTkTextbox(sec, height=120, font=theme.FONT_MONO_SM, state="disabled")
        self._log.pack(fill="x", padx=16, pady=(0, 12))

    def _log_msg(self, msg: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
