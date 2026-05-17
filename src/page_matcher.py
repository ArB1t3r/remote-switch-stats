"""Page matcher engine — identifies which page is currently displayed."""

from __future__ import annotations

import math
import time
from typing import Optional

from PIL import Image

from src.page_profile import PageProfile, RegionBox, load_profiles, get_refs_dir
from src.protocol import SwitchConnection
from src.recorder import decode_pixel_peek


def _region_rmse(img_a: Image.Image, img_b: Image.Image, region: tuple[int, int, int, int]) -> float:
    """Compute RMSE between two images within the given region. Returns 0.0~1.0."""
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


class PageMatcher:
    """Matches screenshots against saved page profiles."""

    def __init__(self, profiles: Optional[list[PageProfile]] = None) -> None:
        self._profiles = profiles if profiles is not None else load_profiles()
        self._ref_cache: dict[str, Image.Image] = {}

    @property
    def profiles(self) -> list[PageProfile]:
        return self._profiles

    def reload(self) -> None:
        """Reload profiles from disk."""
        self._profiles = load_profiles()
        self._ref_cache.clear()

    def _get_reference(self, profile: PageProfile) -> Optional[Image.Image]:
        """Load the reference image for a profile (with caching)."""
        if not profile.reference_image:
            return None

        if profile.name in self._ref_cache:
            return self._ref_cache[profile.name]

        ref_path = get_refs_dir() / profile.reference_image
        if not ref_path.exists():
            return None

        try:
            img = Image.open(ref_path)
            self._ref_cache[profile.name] = img
            return img
        except Exception:
            return None

    def match_score(self, img: Image.Image, profile: PageProfile) -> float:
        """
        Return the max RMSE across all regions for a profile.
        Lower = better match. Returns 1.0 if no reference or no regions.
        """
        ref = self._get_reference(profile)
        if ref is None or not profile.regions:
            return 1.0

        max_score = 0.0
        for region in profile.regions:
            score = _region_rmse(img, ref, region.as_tuple())
            max_score = max(max_score, score)
        return max_score

    def is_page(self, img: Image.Image, name: str) -> bool:
        """Check if the current image matches the named page profile."""
        for profile in self._profiles:
            if profile.name == name:
                score = self.match_score(img, profile)
                return score <= profile.threshold
        return False

    def identify(self, img: Image.Image) -> Optional[str]:
        """Identify which page the image matches. Returns None if no match."""
        best_name: Optional[str] = None
        best_score = 1.0

        for profile in self._profiles:
            score = self.match_score(img, profile)
            if score <= profile.threshold and score < best_score:
                best_score = score
                best_name = profile.name

        return best_name

    def wait_for_page(
        self,
        conn: SwitchConnection,
        name: str,
        timeout_s: float = 10.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """Poll screenshots until the named page appears or timeout."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            raw = conn.pixel_peek()
            img = decode_pixel_peek(raw)
            if img and self.is_page(img, name):
                return True
            time.sleep(poll_interval)
        return False
