"""Setup & Connection tab — scan LAN, manual connect, sys-botbase config."""

import threading
import customtkinter as ctk

from src.protocol import SwitchConnection, SYSBOT_PORT, CONFIGURE_KEYS
from src.scanner import get_local_ip, derive_subnet, scan_subnet


class SetupView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        conn: SwitchConnection,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._conn = conn
        self._cancel_scan = threading.Event()

        self.grid_columnconfigure(0, weight=1)

        self._build_connect_section()
        self._build_scan_section()
        self._build_info_section()
        self._build_configure_section()

    # ── Manual connection ──────────────────────────────────────────

    def _build_connect_section(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        sec.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sec, text="手动连接", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=3, padx=16, pady=(12, 8), sticky="w",
        )

        ctk.CTkLabel(sec, text="Switch IP:").grid(row=1, column=0, padx=(16, 4), pady=8, sticky="w")
        self._ip_entry = ctk.CTkEntry(sec, placeholder_text="192.168.1.xxx", width=200)
        self._ip_entry.grid(row=1, column=1, padx=4, pady=8, sticky="ew")

        btn_frame = ctk.CTkFrame(sec, fg_color="transparent")
        btn_frame.grid(row=1, column=2, padx=(4, 16), pady=8)

        self._connect_btn = ctk.CTkButton(
            btn_frame, text="连接", width=80, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_connect,
        )
        self._connect_btn.pack(side="left", padx=2)

        self._disconnect_btn = ctk.CTkButton(
            btn_frame, text="断开", width=80, fg_color="#ef4444",
            hover_color="#dc2626", command=self._do_disconnect,
        )
        self._disconnect_btn.pack(side="left", padx=2)

        self._connect_msg = ctk.CTkLabel(sec, text="", text_color="#9ca3af", font=("", 12))
        self._connect_msg.grid(row=2, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="w")

    def _do_connect(self) -> None:
        ip = self._ip_entry.get().strip()
        if not ip:
            self._connect_msg.configure(text="请输入 Switch IP 地址", text_color="#ef4444")
            return
        self._connect_msg.configure(text="正在连接…", text_color="#eab308")

        def _task() -> None:
            msg = self._conn.connect(ip)
            self.after(0, lambda: self._connect_msg.configure(
                text=msg,
                text_color="#22c55e" if self._conn.connected else "#ef4444",
            ))
            if self._conn.connected:
                self.after(100, self._fetch_info)

        threading.Thread(target=_task, daemon=True).start()

    def _do_disconnect(self) -> None:
        self._conn.disconnect()
        self._connect_msg.configure(text="已断开连接", text_color="#9ca3af")
        self._info_text.configure(state="normal")
        self._info_text.delete("1.0", "end")
        self._info_text.configure(state="disabled")

    # ── Network scan ───────────────────────────────────────────────

    def _build_scan_section(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        sec.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sec, text="局域网扫描", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=3, padx=16, pady=(12, 8), sticky="w",
        )

        ctk.CTkLabel(sec, text="子网:").grid(row=1, column=0, padx=(16, 4), pady=8, sticky="w")
        local_ip = get_local_ip()
        subnet_hint = derive_subnet(local_ip) if local_ip else "192.168.1"
        self._subnet_entry = ctk.CTkEntry(sec, placeholder_text=subnet_hint, width=160)
        self._subnet_entry.insert(0, subnet_hint)
        self._subnet_entry.grid(row=1, column=1, padx=4, pady=8, sticky="w")

        btn_frame = ctk.CTkFrame(sec, fg_color="transparent")
        btn_frame.grid(row=1, column=2, padx=(4, 16), pady=8)

        self._scan_btn = ctk.CTkButton(
            btn_frame, text="开始扫描", width=100, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_scan,
        )
        self._scan_btn.pack(side="left", padx=2)

        self._stop_scan_btn = ctk.CTkButton(
            btn_frame, text="停止", width=60, fg_color="#ef4444",
            hover_color="#dc2626", command=self._stop_scan, state="disabled",
        )
        self._stop_scan_btn.pack(side="left", padx=2)

        self._scan_progress = ctk.CTkProgressBar(sec, width=400)
        self._scan_progress.set(0)
        self._scan_progress.grid(row=2, column=0, columnspan=3, padx=16, pady=4, sticky="ew")

        self._scan_label = ctk.CTkLabel(sec, text="", font=("", 12), text_color="#9ca3af")
        self._scan_label.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 4), sticky="w")

        self._found_frame = ctk.CTkScrollableFrame(sec, height=80)
        self._found_frame.grid(row=4, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="ew")

    def _do_scan(self) -> None:
        self._cancel_scan.clear()
        subnet = self._subnet_entry.get().strip()
        if not subnet:
            return
        for w in self._found_frame.winfo_children():
            w.destroy()
        self._scan_progress.set(0)
        self._scan_label.configure(text="扫描中…")
        self._scan_btn.configure(state="disabled")
        self._stop_scan_btn.configure(state="normal")

        def _on_progress(done: int, total: int) -> None:
            self.after(0, lambda: self._scan_progress.set(done / total))
            self.after(0, lambda: self._scan_label.configure(text=f"已扫描 {done}/{total}"))

        def _on_found(ip: str) -> None:
            self.after(0, lambda: self._add_found_device(ip))

        def _task() -> None:
            results = scan_subnet(
                subnet,
                on_progress=_on_progress,
                on_found=_on_found,
                cancel_event=self._cancel_scan,
            )
            self.after(0, lambda: self._scan_btn.configure(state="normal"))
            self.after(0, lambda: self._stop_scan_btn.configure(state="disabled"))
            count = len(results)
            self.after(0, lambda: self._scan_label.configure(
                text=f"扫描完成，发现 {count} 台设备" if not self._cancel_scan.is_set()
                else f"扫描已取消，发现 {count} 台设备",
            ))

        threading.Thread(target=_task, daemon=True).start()

    def _stop_scan(self) -> None:
        self._cancel_scan.set()

    def _add_found_device(self, ip: str) -> None:
        row = ctk.CTkFrame(self._found_frame, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=2)
        ctk.CTkLabel(row, text=f"\U0001f3ae  {ip}:6000", font=("", 13)).pack(side="left", padx=8)
        ctk.CTkButton(
            row, text="连接", width=60, height=26,
            fg_color="#22c55e", hover_color="#16a34a",
            command=lambda: self._connect_to(ip),
        ).pack(side="right", padx=8)

    def _connect_to(self, ip: str) -> None:
        self._ip_entry.delete(0, "end")
        self._ip_entry.insert(0, ip)
        self._do_connect()

    # ── Switch info ────────────────────────────────────────────────

    def _build_info_section(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=2, column=0, padx=16, pady=8, sticky="ew")
        sec.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(sec, fg_color="transparent")
        header.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")
        ctk.CTkLabel(header, text="Switch 信息", font=("", 16, "bold")).pack(side="left")
        ctk.CTkButton(
            header, text="刷新", width=60, height=26,
            fg_color="#6366f1", hover_color="#4f46e5",
            command=lambda: threading.Thread(target=self._fetch_info, daemon=True).start(),
        ).pack(side="right")

        self._info_text = ctk.CTkTextbox(sec, height=120, state="disabled", font=("Consolas", 12))
        self._info_text.grid(row=1, column=0, padx=16, pady=(4, 12), sticky="ew")

    def _fetch_info(self) -> None:
        if not self._conn.connected:
            return
        lines = []
        for label, fn in [
            ("sys-botbase 版本", self._conn.get_version),
            ("Title ID", self._conn.get_title_id),
            ("Title Version", self._conn.get_title_version),
            ("Build ID", self._conn.get_build_id),
            ("System Language", self._conn.get_system_language),
            ("Heap Base", self._conn.get_heap_base),
            ("Main NSO Base", self._conn.get_main_nso_base),
            ("电池状态", self._conn.get_charge),
        ]:
            resp = fn()
            lines.append(f"{label}: {resp}")

        text = "\n".join(lines)
        self.after(0, lambda: self._show_info(text))

    def _show_info(self, text: str) -> None:
        self._info_text.configure(state="normal")
        self._info_text.delete("1.0", "end")
        self._info_text.insert("1.0", text)
        self._info_text.configure(state="disabled")

    # ── Configure ──────────────────────────────────────────────────

    def _build_configure_section(self) -> None:
        sec = ctk.CTkFrame(self, corner_radius=12)
        sec.grid(row=3, column=0, padx=16, pady=(8, 16), sticky="ew")
        sec.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sec, text="配置参数", font=("", 16, "bold")).grid(
            row=0, column=0, columnspan=3, padx=16, pady=(12, 8), sticky="w",
        )

        self._cfg_key = ctk.CTkComboBox(sec, values=CONFIGURE_KEYS, width=220)
        self._cfg_key.grid(row=1, column=0, padx=(16, 4), pady=8)
        self._cfg_key.set(CONFIGURE_KEYS[0])

        self._cfg_val = ctk.CTkEntry(sec, placeholder_text="值", width=120)
        self._cfg_val.grid(row=1, column=1, padx=4, pady=8, sticky="w")

        ctk.CTkButton(
            sec, text="设置", width=60, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_configure,
        ).grid(row=1, column=2, padx=(4, 16), pady=8)

        self._cfg_msg = ctk.CTkLabel(sec, text="", font=("", 12), text_color="#9ca3af")
        self._cfg_msg.grid(row=2, column=0, columnspan=3, padx=16, pady=(0, 12), sticky="w")

    def _do_configure(self) -> None:
        key = self._cfg_key.get()
        val = self._cfg_val.get().strip()
        if not val:
            self._cfg_msg.configure(text="请输入参数值", text_color="#ef4444")
            return

        def _task() -> None:
            resp = self._conn.configure(key, val)
            self.after(0, lambda: self._cfg_msg.configure(
                text=f"configure {key} {val} → {resp}",
                text_color="#22c55e" if self._conn.connected else "#ef4444",
            ))

        threading.Thread(target=_task, daemon=True).start()
