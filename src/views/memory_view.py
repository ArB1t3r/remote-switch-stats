"""Memory tools tab — peek / poke / freeze / pointer operations."""

import threading
import textwrap
import customtkinter as ctk

from src.protocol import SwitchConnection


class MemoryView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        conn: SwitchConnection,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._conn = conn
        self.grid_columnconfigure(0, weight=1)

        self._build_peek_section()
        self._build_poke_section()
        self._build_pointer_section()
        self._build_freeze_section()
        self._build_output()

    # ── Peek (read) ────────────────────────────────────────────────

    def _build_peek_section(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        sec.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(sec, text="内存读取 (Peek)", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=5, padx=16, pady=(12, 8), sticky="w",
        )

        self._peek_mode = ctk.CTkSegmentedButton(
            sec, values=["Heap", "Absolute", "Main"],
        )
        self._peek_mode.set("Heap")
        self._peek_mode.grid(row=1, column=0, columnspan=2, padx=(16, 4), pady=8)

        ctk.CTkLabel(sec, text="地址:").grid(row=2, column=0, padx=(16, 4), pady=4, sticky="w")
        self._peek_addr = ctk.CTkEntry(sec, placeholder_text="0x12345678", width=200)
        self._peek_addr.grid(row=2, column=1, padx=4, pady=4, sticky="w")

        ctk.CTkLabel(sec, text="字节数:").grid(row=2, column=2, padx=(12, 4), pady=4, sticky="w")
        self._peek_size = ctk.CTkEntry(sec, placeholder_text="4", width=80)
        self._peek_size.grid(row=2, column=3, padx=4, pady=4, sticky="w")

        ctk.CTkButton(
            sec, text="读取", width=70, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_peek,
        ).grid(row=2, column=4, padx=(4, 16), pady=4)

    def _do_peek(self) -> None:
        mode = self._peek_mode.get()
        addr = self._peek_addr.get().strip()
        size_str = self._peek_size.get().strip()
        if not addr or not size_str:
            self._append_output("[错误] 请输入地址和字节数\n")
            return
        try:
            size = int(size_str)
        except ValueError:
            self._append_output("[错误] 字节数必须为整数\n")
            return

        fn_map = {"Heap": self._conn.peek, "Absolute": self._conn.peek_absolute, "Main": self._conn.peek_main}
        fn = fn_map[mode]

        def _task() -> None:
            resp = fn(addr, size)
            formatted = self._format_hex(resp)
            self.after(0, lambda: self._append_output(
                f"[PEEK {mode}] {addr} ({size} bytes):\n{formatted}\n\n",
            ))

        threading.Thread(target=_task, daemon=True).start()

    # ── Poke (write) ───────────────────────────────────────────────

    def _build_poke_section(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        sec.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(sec, text="内存写入 (Poke)", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=5, padx=16, pady=(12, 8), sticky="w",
        )

        self._poke_mode = ctk.CTkSegmentedButton(
            sec, values=["Heap", "Absolute", "Main"],
        )
        self._poke_mode.set("Heap")
        self._poke_mode.grid(row=1, column=0, columnspan=2, padx=(16, 4), pady=8)

        ctk.CTkLabel(sec, text="地址:").grid(row=2, column=0, padx=(16, 4), pady=4, sticky="w")
        self._poke_addr = ctk.CTkEntry(sec, placeholder_text="0x12345678", width=200)
        self._poke_addr.grid(row=2, column=1, padx=4, pady=4, sticky="w")

        ctk.CTkLabel(sec, text="数据 (hex):").grid(row=2, column=2, padx=(12, 4), pady=4, sticky="w")
        self._poke_data = ctk.CTkEntry(sec, placeholder_text="0xDEADBEEF", width=200)
        self._poke_data.grid(row=2, column=3, padx=4, pady=4, sticky="w")

        ctk.CTkButton(
            sec, text="写入", width=70, fg_color="#ef4444",
            hover_color="#dc2626", command=self._do_poke,
        ).grid(row=2, column=4, padx=(4, 16), pady=4)

    def _do_poke(self) -> None:
        mode = self._poke_mode.get()
        addr = self._poke_addr.get().strip()
        data = self._poke_data.get().strip()
        if not addr or not data:
            self._append_output("[错误] 请输入地址和数据\n")
            return

        fn_map = {"Heap": self._conn.poke, "Absolute": self._conn.poke_absolute, "Main": self._conn.poke_main}
        fn = fn_map[mode]

        def _task() -> None:
            resp = fn(addr, data)
            self.after(0, lambda: self._append_output(
                f"[POKE {mode}] {addr} ← {data}  (resp: {resp})\n",
            ))

        threading.Thread(target=_task, daemon=True).start()

    # ── Pointer operations ─────────────────────────────────────────

    def _build_pointer_section(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=2, column=0, padx=16, pady=8, sticky="ew")
        sec.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sec, text="指针链 (Pointer)", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w",
        )

        ctk.CTkLabel(sec, text="字节数:").grid(row=1, column=0, padx=(16, 4), pady=4, sticky="w")
        self._ptr_size = ctk.CTkEntry(sec, placeholder_text="4", width=80)
        self._ptr_size.grid(row=1, column=1, padx=4, pady=4, sticky="w")

        ctk.CTkLabel(sec, text="跳转链 (空格分隔):").grid(row=2, column=0, padx=(16, 4), pady=4, sticky="w")
        self._ptr_jumps = ctk.CTkEntry(sec, placeholder_text="0x45097552 0x10 0x20 0x30", width=400)
        self._ptr_jumps.grid(row=2, column=1, columnspan=2, padx=4, pady=4, sticky="ew")

        ctk.CTkButton(
            sec, text="读取", width=70, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_pointer_peek,
        ).grid(row=2, column=3, padx=(4, 16), pady=4)

    def _do_pointer_peek(self) -> None:
        size_str = self._ptr_size.get().strip()
        jumps_str = self._ptr_jumps.get().strip()
        if not size_str or not jumps_str:
            self._append_output("[错误] 请输入字节数和跳转链\n")
            return
        try:
            size = int(size_str)
        except ValueError:
            self._append_output("[错误] 字节数必须为整数\n")
            return
        jumps = jumps_str.split()

        def _task() -> None:
            resp = self._conn.pointer_peek(size, jumps)
            formatted = self._format_hex(resp)
            self.after(0, lambda: self._append_output(
                f"[POINTER PEEK] size={size} jumps={jumps_str}:\n{formatted}\n\n",
            ))

        threading.Thread(target=_task, daemon=True).start()

    # ── Freeze controls ────────────────────────────────────────────

    def _build_freeze_section(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=3, column=0, padx=16, pady=8, sticky="ew")

        ctk.CTkLabel(sec, text="内存冻结 (Freeze)", font=("", 16, "bold")).pack(
            padx=16, pady=(12, 8), anchor="w",
        )

        row1 = ctk.CTkFrame(sec, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(row1, text="地址:").pack(side="left", padx=(0, 4))
        self._frz_addr = ctk.CTkEntry(row1, placeholder_text="0x45097552", width=180)
        self._frz_addr.pack(side="left", padx=4)

        ctk.CTkLabel(row1, text="值 (hex):").pack(side="left", padx=(12, 4))
        self._frz_val = ctk.CTkEntry(row1, placeholder_text="0xFF", width=120)
        self._frz_val.pack(side="left", padx=4)

        ctk.CTkButton(
            row1, text="冻结", width=60, fg_color="#3b82f6",
            hover_color="#2563eb", command=self._do_freeze,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            row1, text="解冻", width=60, fg_color="#f97316",
            hover_color="#ea580c", command=self._do_unfreeze,
        ).pack(side="left", padx=4)

        row2 = ctk.CTkFrame(sec, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(4, 12))

        for text, cmd in [
            ("已冻结数量", self._do_freeze_count),
            ("全部解冻", self._do_freeze_clear),
            ("暂停冻结", self._do_freeze_pause),
            ("恢复冻结", self._do_freeze_unpause),
        ]:
            ctk.CTkButton(
                row2, text=text, width=90, height=30,
                fg_color="#4b5563", hover_color="#374151", command=cmd,
            ).pack(side="left", padx=4)

    def _do_freeze(self) -> None:
        addr = self._frz_addr.get().strip()
        val = self._frz_val.get().strip()
        if not addr or not val:
            return
        self._run_and_log(f"freeze {addr} {val}", lambda: self._conn.freeze(addr, val))

    def _do_unfreeze(self) -> None:
        addr = self._frz_addr.get().strip()
        if not addr:
            return
        self._run_and_log(f"unFreeze {addr}", lambda: self._conn.unfreeze(addr))

    def _do_freeze_count(self) -> None:
        self._run_and_log("freezeCount", self._conn.freeze_count)

    def _do_freeze_clear(self) -> None:
        self._run_and_log("freezeClear", self._conn.freeze_clear)

    def _do_freeze_pause(self) -> None:
        self._run_and_log("freezePause", self._conn.freeze_pause)

    def _do_freeze_unpause(self) -> None:
        self._run_and_log("freezeUnpause", self._conn.freeze_unpause)

    # ── Output ─────────────────────────────────────────────────────

    def _build_output(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=4, column=0, padx=16, pady=(8, 16), sticky="ew")
        sec.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(sec, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(header, text="输出", font=("", 14, "bold")).pack(side="left")
        ctk.CTkButton(
            header, text="清空", width=50, height=24,
            fg_color="#6b7280", hover_color="#4b5563",
            command=self._clear_output,
        ).pack(side="right")

        self._output = ctk.CTkTextbox(sec, height=160, font=("Consolas", 11), state="disabled")
        self._output.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _append_output(self, text: str) -> None:
        self._output.configure(state="normal")
        self._output.insert("end", text)
        self._output.see("end")
        self._output.configure(state="disabled")

    def _clear_output(self) -> None:
        self._output.configure(state="normal")
        self._output.delete("1.0", "end")
        self._output.configure(state="disabled")

    def _run_and_log(self, label: str, fn) -> None:
        def _task() -> None:
            resp = fn()
            self.after(0, lambda: self._append_output(f"[{label}] → {resp}\n"))
        threading.Thread(target=_task, daemon=True).start()

    @staticmethod
    def _format_hex(data: str) -> str:
        """Pretty-print a hex string into 16-byte rows."""
        clean = data.strip()
        if not clean or clean.startswith("["):
            return clean
        lines = textwrap.wrap(clean, 32)  # 32 hex chars = 16 bytes
        formatted = []
        for i, line in enumerate(lines):
            offset = f"{i * 16:08X}"
            pairs = " ".join(line[j:j+2] for j in range(0, len(line), 2))
            formatted.append(f"{offset}  {pairs}")
        return "\n".join(formatted)
