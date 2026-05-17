"""
Pokemon Stats Recorder — automated screenshot collection engine.

Navigates through each Pokemon's detail pages in a fixed sequence,
capturing named screenshots at each step.  Uses screen-diff verification
to confirm that every button press actually changed the screen before
proceeding (with automatic retries).
"""

import io
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from src.protocol import SwitchConnection
from src.page_profile import load_profiles


# ── Step definitions ────────────────────────────────────────────────

@dataclass
class Step:
    """One atomic action in the recording sequence."""
    button: str            # button to click before capturing (or "" for verify-only steps)
    screenshot_name: str   # semantic filename (without extension)
    wait_ms: int = 500     # sleep after click, before capture
    action: str = "press"  # "press" = click+capture, "verify" = page check only
    verify_page: str = ""  # page profile name to verify (for action="verify")

    @property
    def is_verify(self) -> bool:
        return self.action == "verify"

    def display_label(self) -> str:
        if self.is_verify:
            return f"[验证] {self.verify_page}"
        return self.screenshot_name


POKEMON_DETAIL_STEPS: list[Step] = [
    Step("A",      "01_moves_1"),
    Step("DUP",    "02_moves_2"),
    Step("DRIGHT", "03_held_item_1"),
    Step("DUP",    "04_held_item_2"),
    Step("DRIGHT", "05_teammate_1"),
    Step("DUP",    "06_teammate_2"),
    Step("DRIGHT", "07_stats_1"),
    Step("DUP",    "08_stats_2"),
    Step("DRIGHT", "09_evs_1"),
    Step("DUP",    "10_evs_2"),
    Step("DRIGHT", "11_ability"),
]

# ── Image utilities ─────────────────────────────────────────────────

def decode_pixel_peek(data: bytes) -> Optional[Image.Image]:
    """Decode raw pixelPeek response into a PIL Image."""
    if not data:
        return None
    try:
        return Image.open(io.BytesIO(data))
    except Exception:
        pass
    try:
        hex_str = data.strip().decode("ascii", errors="ignore")
        return Image.open(io.BytesIO(bytes.fromhex(hex_str)))
    except Exception:
        return None


def region_match_score(img_a: Image.Image, img_b: Image.Image, region: tuple[int, int, int, int]) -> float:
    """Compare a specific region (x1, y1, x2, y2) between two images. Returns RMSE 0.0~1.0."""
    crop_a = img_a.crop(region).convert("RGB")
    crop_b = img_b.crop(region).convert("RGB")

    if crop_a.size != crop_b.size:
        crop_b = crop_b.resize(crop_a.size)

    pa = list(crop_a.getdata())
    pb = list(crop_b.getdata())

    if not pa:
        return 1.0

    mse = sum(
        (ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2
        for (ra, ga, ba), (rb, gb, bb) in zip(pa, pb)
    ) / (len(pa) * 3)

    return math.sqrt(mse) / 255.0


def image_diff_score(img_a: Image.Image, img_b: Image.Image) -> float:
    """
    Compute normalised RMSE between two images (0.0 = identical, 1.0 = max).
    Images are resized to the same dimensions for comparison.
    """
    size = (160, 90)  # thumbnail for fast comparison
    a = img_a.resize(size).convert("RGB")
    b = img_b.resize(size).convert("RGB")

    pa = list(a.getdata())
    pb = list(b.getdata())

    mse = sum(
        (ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2
        for (ra, ga, ba), (rb, gb, bb) in zip(pa, pb)
    ) / (len(pa) * 3)

    rmse = math.sqrt(mse) / 255.0
    return rmse


# ── Callback types ──────────────────────────────────────────────────

@dataclass
class RecorderProgress:
    """Snapshot of recording progress at a moment in time."""
    pokemon_done: int = 0       # Pokemon fully completed (all steps OK)
    pokemon_total: int = 0
    current_pokemon: int = 0    # 1-indexed (0 = not started)
    current_step: int = 0       # 1-indexed within current Pokemon
    total_steps_per_pokemon: int = 0
    screenshots_taken: int = 0


@dataclass
class RecorderCallbacks:
    on_log: Callable[[str], None] = field(default=lambda msg: None)
    on_progress: Callable[[int, int, int, int], None] = field(
        default=lambda poke_idx, poke_total, step_idx, step_total: None,
    )
    on_screenshot: Callable[[Image.Image, str], None] = field(
        default=lambda img, name: None,
    )
    on_error: Callable[[str], None] = field(default=lambda msg: None)
    on_complete: Callable[[str], None] = field(default=lambda save_dir: None)
    on_verify_failed: Callable[[str, "RecorderProgress"], None] = field(
        default=lambda page_name, progress: None,
    )
    on_state_changed: Callable[[bool], None] = field(default=lambda is_running: None)


# ── Recorder engine ─────────────────────────────────────────────────

class PokemonRecorder:
    """Orchestrates the full multi-Pokemon recording session."""

    DEFAULT_WAIT_MS = 500
    DEFAULT_DIFF_THRESHOLD = 0.02  # 2% RMSE — very conservative
    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        conn: SwitchConnection,
        pokemon_count: int = 6,
        wait_ms: int = DEFAULT_WAIT_MS,
        diff_threshold: float = DEFAULT_DIFF_THRESHOLD,
        max_retries: int = DEFAULT_MAX_RETRIES,
        save_root: Optional[str] = None,
        callbacks: Optional[RecorderCallbacks] = None,
        steps: Optional[list[Step]] = None,
    ) -> None:
        self._conn = conn
        self._pokemon_count = pokemon_count
        self._wait_ms = wait_ms
        self._diff_threshold = diff_threshold
        self._max_retries = max_retries
        self._running = False
        self._paused = False
        self._cb = callbacks or RecorderCallbacks()
        self._page_matcher: Optional[object] = None

        self._steps = steps if steps is not None else list(POKEMON_DETAIL_STEPS)

        # Load page profiles for verification
        try:
            from src.page_matcher import PageMatcher
            profiles = load_profiles()
            if profiles:
                self._page_matcher = PageMatcher(profiles)
        except Exception:
            pass

        if save_root is None:
            if getattr(sys, "frozen", False):
                save_root = os.path.join(os.path.dirname(sys.executable), "captures")
            else:
                save_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "captures")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_dir = os.path.join(save_root, ts)

    @property
    def session_dir(self) -> str:
        return self._session_dir

    @property
    def running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def stop(self) -> None:
        self._running = False

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # ── Main loop ───────────────────────────────────────────────────

    def run(self) -> None:
        """
        Execute the full recording session (blocking).
        Call from a worker thread.
        """
        self._running = True
        self._screenshots_taken = 0
        self._pokemon_done = 0
        total_steps = len(self._steps)

        self._cb.on_state_changed(True)
        self._cb.on_log(f"开始采集 {self._pokemon_count} 只宝可梦 ({total_steps} 步/只)")
        self._cb.on_log(f"保存目录: {self._session_dir}")

        for poke_idx in range(self._pokemon_count):
            if not self._running:
                break

            poke_num = poke_idx + 1
            poke_dir = os.path.join(self._session_dir, f"pokemon_{poke_num:02d}")
            Path(poke_dir).mkdir(parents=True, exist_ok=True)

            self._cb.on_log(f"\n{'='*40}")
            self._cb.on_log(f"Pokemon #{poke_num}/{self._pokemon_count}")
            self._cb.on_log(f"{'='*40}")

            prev_img: Optional[Image.Image] = None
            pokemon_success = True

            for step_idx, step in enumerate(self._steps):
                if not self._running:
                    pokemon_success = False
                    break
                self._wait_if_paused()

                self._cb.on_progress(poke_num, self._pokemon_count, step_idx + 1, total_steps)

                # Verify step: check current screen matches saved page profile
                if step.is_verify:
                    verified = self._execute_verify_step(step)
                    if not verified:
                        self._cb.on_log(
                            f"  [{step_idx+1}/{total_steps}] [验证] {step.verify_page} -> 失败"
                        )
                        self._notify_verify_failed(step.verify_page, poke_num, step_idx + 1, total_steps)
                        self._paused = True
                        self._wait_if_paused()
                        if not self._running:
                            pokemon_success = False
                            break
                    else:
                        self._cb.on_log(f"  [{step_idx+1}/{total_steps}] [验证] {step.verify_page} -> OK")
                    continue

                # Press-only step (no capture)
                if not step.screenshot_name:
                    self._click_and_wait(step.button, step.wait_ms or self._wait_ms)
                    self._cb.on_log(f"  [{step_idx+1}/{total_steps}] 按 {step.button} (无截图)")
                    continue

                success, img = self._execute_step(step, prev_img)

                if not success:
                    self._cb.on_error(
                        f"Pokemon #{poke_num} 步骤 {step.screenshot_name} "
                        f"重试 {self._max_retries} 次仍失败，已暂停"
                    )
                    pokemon_success = False
                    self._paused = True
                    self._wait_if_paused()
                    if not self._running:
                        break
                    img = self._capture()

                if img is not None:
                    save_path = os.path.join(poke_dir, f"{step.screenshot_name}.jpg")
                    img.save(save_path, "JPEG", quality=95)
                    self._screenshots_taken += 1
                    self._cb.on_screenshot(img, step.screenshot_name)
                    self._cb.on_log(f"  [{step_idx+1}/{total_steps}] {step.screenshot_name} -> OK")
                    prev_img = img
                else:
                    self._cb.on_log(f"  [{step_idx+1}/{total_steps}] {step.screenshot_name} -> 截图失败")

            if not self._running:
                break

            if pokemon_success:
                self._pokemon_done += 1

        self._running = False
        self._cb.on_log(
            f"\n采集结束: 完成 {self._pokemon_done}/{self._pokemon_count} 只宝可梦, "
            f"共 {self._screenshots_taken} 张截图"
        )
        self._cb.on_log(f"文件保存在: {self._session_dir}")
        self._cb.on_state_changed(False)
        self._cb.on_complete(self._session_dir)

    def _notify_verify_failed(
        self, page_name: str, poke_num: int, step_idx: int, total_steps: int,
    ) -> None:
        """Build progress snapshot and call the on_verify_failed callback."""
        progress = RecorderProgress(
            pokemon_done=self._pokemon_done,
            pokemon_total=self._pokemon_count,
            current_pokemon=poke_num,
            current_step=step_idx,
            total_steps_per_pokemon=total_steps,
            screenshots_taken=self._screenshots_taken,
        )
        self._cb.on_verify_failed(page_name, progress)

    # ── Step execution with verification ────────────────────────────

    def _execute_step(
        self, step: Step, prev_img: Optional[Image.Image],
    ) -> tuple[bool, Optional[Image.Image]]:
        """
        Click button, wait, capture, verify screen changed.
        Returns (success, captured_image).
        """
        for attempt in range(1, self._max_retries + 1):
            if not self._running:
                return False, None

            self._click_and_wait(step.button, step.wait_ms or self._wait_ms)
            img = self._capture()

            if img is None:
                self._cb.on_log(f"    尝试 {attempt}: 截图失败, 重试...")
                continue

            if prev_img is None:
                return True, img

            diff = image_diff_score(prev_img, img)
            if diff >= self._diff_threshold:
                return True, img

            self._cb.on_log(
                f"    尝试 {attempt}: 画面未变化 (diff={diff:.4f} < {self._diff_threshold}), 重试..."
            )
            time.sleep(0.3)

        return False, self._capture()

    # ── Verify step execution ────────────────────────────────────────

    def _execute_verify_step(self, step: Step) -> bool:
        """Execute a verify-type step: check if current screen matches the named page."""
        if not self._page_matcher or not step.verify_page:
            self._cb.on_log(f"    [验证] 跳过: 无页面配置 '{step.verify_page}'")
            return True  # no matcher = pass through

        from src.page_matcher import PageMatcher
        matcher: PageMatcher = self._page_matcher  # type: ignore

        for attempt in range(1, 4):
            img = self._capture()
            if img is None:
                self._cb.on_log(f"    [验证] 尝试 {attempt}: 截图失败")
                time.sleep(0.5)
                continue

            if matcher.is_page(img, step.verify_page):
                return True

            profile = next((p for p in matcher.profiles if p.name == step.verify_page), None)
            if profile:
                score = matcher.match_score(img, profile)
                self._cb.on_log(f"    [验证] 尝试 {attempt}: 得分={score:.4f} — 未匹配 '{step.verify_page}'")

            time.sleep(0.5)

        return False

    # ── Helpers ─────────────────────────────────────────────────────

    def _click_and_wait(self, button: str, wait_ms: int) -> None:
        self._conn.click(button)
        time.sleep(wait_ms / 1000.0)

    def _capture(self) -> Optional[Image.Image]:
        raw = self._conn.pixel_peek()
        return decode_pixel_peek(raw)

    def _wait_if_paused(self) -> None:
        while self._paused and self._running:
            time.sleep(0.2)
