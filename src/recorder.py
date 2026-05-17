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
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from src.protocol import SwitchConnection


# ── Step definitions ────────────────────────────────────────────────

@dataclass
class Step:
    """One atomic action in the recording sequence."""
    button: str            # button to click before capturing
    screenshot_name: str   # semantic filename (without extension)
    wait_ms: int = 500     # sleep after click, before capture


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

EXIT_BUTTON = "B"
NEXT_POKEMON_BUTTON = "DDOWN"

# Crop regions used to verify we're back on the list page (1280x720 coordinates).
# These regions contain stable UI elements that don't change between pokemon.
LIST_PAGE_VERIFY_REGIONS = [
    (100, 295, 280, 345),   # "X 单打对战" button area
    (590, 22, 900, 60),     # "训练家 好友 宝可梦" tab bar
]

LIST_PAGE_MATCH_THRESHOLD = 0.03  # max RMSE to consider regions matching


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


def is_list_page(current_img: Image.Image, reference_img: Image.Image) -> bool:
    """Check if current screenshot matches the list page by comparing stable UI regions."""
    for region in LIST_PAGE_VERIFY_REGIONS:
        score = region_match_score(current_img, reference_img, region)
        if score > LIST_PAGE_MATCH_THRESHOLD:
            return False
    return True


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
    ) -> None:
        self._conn = conn
        self._pokemon_count = pokemon_count
        self._wait_ms = wait_ms
        self._diff_threshold = diff_threshold
        self._max_retries = max_retries
        self._running = False
        self._paused = False
        self._cb = callbacks or RecorderCallbacks()

        if save_root is None:
            save_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "captures")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_dir = os.path.join(save_root, ts)

    @property
    def session_dir(self) -> str:
        return self._session_dir

    @property
    def running(self) -> bool:
        return self._running

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
        total_steps = len(POKEMON_DETAIL_STEPS)

        self._cb.on_log(f"开始采集 {self._pokemon_count} 只宝可梦")
        self._cb.on_log(f"保存目录: {self._session_dir}")

        # Capture the list page as reference for verification
        self._cb.on_log("正在捕捉列表页面参考图...")
        time.sleep(0.3)
        self._list_reference = self._capture()
        if self._list_reference is None:
            self._cb.on_error("无法截取参考图，请确保已连接并在宝可梦列表页面")
            self._running = False
            return
        self._cb.on_log("  列表页参考图已保存，将用于页面验证")

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

            for step_idx, step in enumerate(POKEMON_DETAIL_STEPS):
                if not self._running:
                    break
                self._wait_if_paused()

                self._cb.on_progress(poke_num, self._pokemon_count, step_idx + 1, total_steps)

                success, img = self._execute_step(step, prev_img)

                if not success:
                    self._cb.on_error(
                        f"Pokemon #{poke_num} 步骤 {step.screenshot_name} "
                        f"重试 {self._max_retries} 次仍失败，已暂停"
                    )
                    self._paused = True
                    self._wait_if_paused()
                    if not self._running:
                        break
                    img = self._capture()

                if img is not None:
                    save_path = os.path.join(poke_dir, f"{step.screenshot_name}.jpg")
                    img.save(save_path, "JPEG", quality=95)
                    self._cb.on_screenshot(img, step.screenshot_name)
                    self._cb.on_log(f"  [{step_idx+1}/{total_steps}] {step.screenshot_name} -> OK")
                    prev_img = img
                else:
                    self._cb.on_log(f"  [{step_idx+1}/{total_steps}] {step.screenshot_name} -> 截图失败")

            if not self._running:
                break

            # Exit detail page and verify we're back on the list page
            self._cb.on_log(f"  返回列表 (B)...")
            if not self._exit_to_list():
                self._cb.on_error(f"Pokemon #{poke_num}: 无法确认已返回列表页，已暂停")
                self._paused = True
                self._wait_if_paused()
                if not self._running:
                    break

            # Move to next Pokemon
            if poke_idx < self._pokemon_count - 1:
                self._cb.on_log(f"  选择下一只 (DDOWN)")
                self._click_and_wait(NEXT_POKEMON_BUTTON, self._wait_ms)

        self._running = False
        self._cb.on_log(f"\n采集完成! 文件保存在: {self._session_dir}")
        self._cb.on_complete(self._session_dir)

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

    # ── List page verification ────────────────────────────────────────

    def _exit_to_list(self) -> bool:
        """Press B and verify we returned to the list page using image comparison."""
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            self._click_and_wait(EXIT_BUTTON, 800)  # longer wait for page transition
            img = self._capture()
            if img is None:
                self._cb.on_log(f"    退出尝试 {attempt}: 截图失败")
                continue

            if self._list_reference and is_list_page(img, self._list_reference):
                if attempt > 1:
                    self._cb.on_log(f"    第 {attempt} 次尝试后确认回到列表页")
                else:
                    self._cb.on_log(f"    已确认回到列表页")
                # Update reference (list selection might have moved)
                self._list_reference = img
                return True

            self._cb.on_log(f"    退出尝试 {attempt}: 未检测到列表页面，再按 B...")
            time.sleep(0.3)

        self._cb.on_log(f"    {max_attempts} 次尝试后仍未回到列表页")
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
