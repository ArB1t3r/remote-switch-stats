"""Page Configuration tab — capture reference screenshots, draw regions, save profiles."""

import threading
import tkinter as tk
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

from src.protocol import SwitchConnection
from src.page_profile import (
    PageProfile, RegionBox, load_profiles, save_profiles, get_refs_dir,
)
from src.page_matcher import PageMatcher, _region_rmse
from src.recorder import decode_pixel_peek


CANVAS_W = 640
CANVAS_H = 360
SWITCH_W = 1280
SWITCH_H = 720
SCALE = CANVAS_W / SWITCH_W  # 0.5


class PageConfigView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        conn: SwitchConnection,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._conn = conn
        self._profiles: list[PageProfile] = load_profiles()
        self._current_img: Optional[Image.Image] = None
        self._photo_ref: Optional[ImageTk.PhotoImage] = None
        self._drawing = False
        self._draw_start: tuple[int, int] = (0, 0)
        self._temp_rect: Optional[int] = None
        self._regions: list[RegionBox] = []
        self._rect_ids: list[int] = []
        self._selected_profile_idx: Optional[int] = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

    # ── Sidebar: saved profiles list ─────────────────────────────────

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=12)
        sidebar.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="ns")
        sidebar.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(sidebar, text="已保存页面", font=("", 14, "bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w",
        )

        self._profile_list = ctk.CTkScrollableFrame(sidebar, width=180)
        self._profile_list.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")

        btn_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=8, pady=(4, 12))

        ctk.CTkButton(
            btn_frame, text="删除选中", width=80, height=28,
            fg_color="#ef4444", hover_color="#dc2626",
            command=self._delete_selected,
        ).pack(side="left", padx=2)

        self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        for w in self._profile_list.winfo_children():
            w.destroy()

        for idx, profile in enumerate(self._profiles):
            btn = ctk.CTkButton(
                self._profile_list,
                text=f"{profile.name} ({len(profile.regions)} 区域)",
                height=30, anchor="w",
                fg_color="#334155" if idx != self._selected_profile_idx else "#4f46e5",
                hover_color="#475569",
                command=lambda i=idx: self._select_profile(i),
            )
            btn.pack(fill="x", padx=4, pady=2)

    def _select_profile(self, idx: int) -> None:
        self._selected_profile_idx = idx
        profile = self._profiles[idx]
        self._name_entry.delete(0, "end")
        self._name_entry.insert(0, profile.name)
        self._threshold_slider.set(profile.threshold)
        self._threshold_label.configure(text=f"{profile.threshold:.2f}")
        self._regions = list(profile.regions)

        # Load reference image
        if profile.reference_image:
            ref_path = get_refs_dir() / profile.reference_image
            if ref_path.exists():
                self._current_img = Image.open(ref_path)
                self._display_image()

        self._redraw_regions()
        self._refresh_profile_list()

    def _delete_selected(self) -> None:
        if self._selected_profile_idx is None:
            return
        del self._profiles[self._selected_profile_idx]
        save_profiles(self._profiles)
        self._selected_profile_idx = None
        self._regions = []
        self._refresh_profile_list()
        self._redraw_regions()

    # ── Main area: canvas + controls ─────────────────────────────────

    def _build_main_area(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self._build_toolbar(main)
        self._build_canvas(main)
        self._build_controls(main)

    def _build_toolbar(self, parent: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(parent, corner_radius=10)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkButton(
            bar, text="截取画面", width=100, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_capture,
        ).pack(side="left", padx=8, pady=8)

        ctk.CTkButton(
            bar, text="测试匹配", width=100, fg_color="#22c55e",
            hover_color="#16a34a", command=self._do_test,
        ).pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            bar, text="清除区域", width=80, fg_color="#6b7280",
            hover_color="#4b5563", command=self._clear_regions,
        ).pack(side="left", padx=4, pady=8)

        self._status_label = ctk.CTkLabel(
            bar, text="截取画面后在画布上框选比对区域", font=("", 11),
            text_color="#9ca3af",
        )
        self._status_label.pack(side="left", padx=12, pady=8)

    def _build_canvas(self, parent: ctk.CTkFrame) -> None:
        canvas_frame = ctk.CTkFrame(parent, corner_radius=10)
        canvas_frame.grid(row=1, column=0, sticky="nsew", pady=4)

        self._canvas = tk.Canvas(
            canvas_frame, width=CANVAS_W, height=CANVAS_H,
            bg="#0f0f1a", highlightthickness=0,
        )
        self._canvas.pack(padx=8, pady=8)
        self._canvas.create_text(
            CANVAS_W // 2, CANVAS_H // 2,
            text="点击「截取画面」获取 Switch 屏幕\n然后拖拽鼠标框选比对区域",
            fill="#6b7280", font=("", 13), justify="center",
        )

        self._canvas.bind("<Button-1>", self._on_mouse_down)
        self._canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self._canvas.bind("<Button-3>", self._on_right_click)

    def _build_controls(self, parent: ctk.CTkFrame) -> None:
        ctrl = ctk.CTkFrame(parent, corner_radius=10)
        ctrl.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        row1 = ctk.CTkFrame(ctrl, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(row1, text="页面名称:").pack(side="left", padx=(0, 4))
        self._name_entry = ctk.CTkEntry(row1, width=180, placeholder_text="例: 宝可梦列表")
        self._name_entry.pack(side="left", padx=4)

        ctk.CTkLabel(row1, text="容错率:").pack(side="left", padx=(16, 4))
        self._threshold_slider = ctk.CTkSlider(
            row1, from_=0.01, to=0.30, width=150,
            command=self._on_threshold_change,
        )
        self._threshold_slider.set(0.12)
        self._threshold_slider.pack(side="left", padx=4)

        self._threshold_label = ctk.CTkLabel(row1, text="0.12", width=40, font=("Consolas", 12))
        self._threshold_label.pack(side="left", padx=4)

        ctk.CTkButton(
            row1, text="保存配置", width=100, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._do_save,
        ).pack(side="right", padx=4)

        # Region info
        self._region_info = ctk.CTkLabel(
            ctrl, text="区域: 0 个 | 右键删除最近区域",
            font=("", 11), text_color="#9ca3af",
        )
        self._region_info.pack(padx=12, pady=(4, 10), anchor="w")

    # ── Canvas interactions ──────────────────────────────────────────

    def _on_mouse_down(self, event: tk.Event) -> None:
        if self._current_img is None:
            return
        self._drawing = True
        self._draw_start = (event.x, event.y)
        self._temp_rect = self._canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#f97316", width=2, dash=(4, 4),
        )

    def _on_mouse_drag(self, event: tk.Event) -> None:
        if not self._drawing or self._temp_rect is None:
            return
        self._canvas.coords(
            self._temp_rect,
            self._draw_start[0], self._draw_start[1], event.x, event.y,
        )

    def _on_mouse_up(self, event: tk.Event) -> None:
        if not self._drawing:
            return
        self._drawing = False
        if self._temp_rect:
            self._canvas.delete(self._temp_rect)
            self._temp_rect = None

        x1_c, y1_c = self._draw_start
        x2_c, y2_c = event.x, event.y

        # Ensure proper order
        x1_c, x2_c = min(x1_c, x2_c), max(x1_c, x2_c)
        y1_c, y2_c = min(y1_c, y2_c), max(y1_c, y2_c)

        # Minimum size check
        if (x2_c - x1_c) < 10 or (y2_c - y1_c) < 10:
            return

        # Convert canvas coords to 1280x720
        x1 = int(x1_c / SCALE)
        y1 = int(y1_c / SCALE)
        x2 = int(x2_c / SCALE)
        y2 = int(y2_c / SCALE)

        x1 = max(0, min(SWITCH_W, x1))
        y1 = max(0, min(SWITCH_H, y1))
        x2 = max(0, min(SWITCH_W, x2))
        y2 = max(0, min(SWITCH_H, y2))

        region = RegionBox(x1, y1, x2, y2)
        self._regions.append(region)
        self._redraw_regions()

    def _on_right_click(self, event: tk.Event) -> None:
        if self._regions:
            self._regions.pop()
            self._redraw_regions()

    def _redraw_regions(self) -> None:
        for rid in self._rect_ids:
            self._canvas.delete(rid)
        self._rect_ids.clear()

        for i, region in enumerate(self._regions):
            x1 = int(region.x1 * SCALE)
            y1 = int(region.y1 * SCALE)
            x2 = int(region.x2 * SCALE)
            y2 = int(region.y2 * SCALE)

            rid = self._canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="#f97316", width=2,
            )
            self._rect_ids.append(rid)

            label_id = self._canvas.create_text(
                x1 + 4, y1 + 2, anchor="nw",
                text=f"R{i+1}", fill="#f97316", font=("", 9, "bold"),
            )
            self._rect_ids.append(label_id)

        self._region_info.configure(
            text=f"区域: {len(self._regions)} 个 | 右键删除最近区域"
        )

    def _clear_regions(self) -> None:
        self._regions.clear()
        self._redraw_regions()

    # ── Actions ──────────────────────────────────────────────────────

    def _do_capture(self) -> None:
        self._status_label.configure(text="正在截取...")

        def _task() -> None:
            raw = self._conn.pixel_peek()
            img = decode_pixel_peek(raw)
            if img:
                self._current_img = img
                self.after(0, self._display_image)
                self.after(0, lambda: self._status_label.configure(
                    text=f"截取成功 ({img.width}x{img.height}) — 拖拽框选区域",
                ))
            else:
                self.after(0, lambda: self._status_label.configure(
                    text="截取失败 — 请确保已连接", text_color="#ef4444",
                ))

        threading.Thread(target=_task, daemon=True).start()

    def _display_image(self) -> None:
        if self._current_img is None:
            return
        resized = self._current_img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(resized)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo_ref)
        self._redraw_regions()

    def _do_test(self) -> None:
        if self._current_img is None or not self._regions:
            self._status_label.configure(text="需要先截图并框选至少一个区域")
            return

        self._status_label.configure(text="正在测试...")

        def _task() -> None:
            raw = self._conn.pixel_peek()
            test_img = decode_pixel_peek(raw)
            if test_img is None:
                self.after(0, lambda: self._status_label.configure(text="测试失败 — 截图错误"))
                return

            scores = []
            for region in self._regions:
                score = _region_rmse(test_img, self._current_img, region.as_tuple())
                scores.append(score)

            threshold = self._threshold_slider.get()
            max_score = max(scores)
            passed = max_score <= threshold
            scores_str = " | ".join(f"R{i+1}={s:.4f}" for i, s in enumerate(scores))

            result = f"{'PASS' if passed else 'FAIL'} | {scores_str} (阈值={threshold:.2f})"
            color = "#22c55e" if passed else "#ef4444"
            self.after(0, lambda: self._status_label.configure(text=result, text_color=color))

        threading.Thread(target=_task, daemon=True).start()

    def _do_save(self) -> None:
        name = self._name_entry.get().strip()
        if not name:
            self._status_label.configure(text="请输入页面名称", text_color="#ef4444")
            return
        if self._current_img is None:
            self._status_label.configure(text="请先截取参考画面", text_color="#ef4444")
            return
        if not self._regions:
            self._status_label.configure(text="请框选至少一个比对区域", text_color="#ef4444")
            return

        # Save reference image
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ref_filename = f"{name}_{ts}.jpg"
        ref_path = get_refs_dir() / ref_filename
        self._current_img.save(str(ref_path), "JPEG", quality=95)

        threshold = self._threshold_slider.get()

        # Update or create profile
        existing_idx = None
        for i, p in enumerate(self._profiles):
            if p.name == name:
                existing_idx = i
                break

        profile = PageProfile(
            name=name,
            regions=list(self._regions),
            threshold=round(threshold, 3),
            reference_image=ref_filename,
        )

        if existing_idx is not None:
            self._profiles[existing_idx] = profile
        else:
            self._profiles.append(profile)

        save_profiles(self._profiles)
        self._selected_profile_idx = len(self._profiles) - 1 if existing_idx is None else existing_idx
        self._refresh_profile_list()
        self._status_label.configure(
            text=f"已保存: {name} ({len(self._regions)} 区域, 阈值={threshold:.2f})",
            text_color="#22c55e",
        )

    def _on_threshold_change(self, value: float) -> None:
        self._threshold_label.configure(text=f"{value:.2f}")
