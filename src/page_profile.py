"""Page profile data model and JSON persistence."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RegionBox:
    """A rectangular region in 1280x720 coordinate space."""
    x1: int
    y1: int
    x2: int
    y2: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)

    def to_dict(self) -> dict:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, d: dict) -> RegionBox:
        return cls(x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"])


@dataclass
class PageProfile:
    """Configuration for recognizing a specific page/screen."""
    name: str
    regions: list[RegionBox] = field(default_factory=list)
    threshold: float = 0.12
    reference_image: str = ""  # relative path to saved reference screenshot

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "regions": [r.to_dict() for r in self.regions],
            "threshold": self.threshold,
            "reference_image": self.reference_image,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PageProfile:
        return cls(
            name=d["name"],
            regions=[RegionBox.from_dict(r) for r in d.get("regions", [])],
            threshold=d.get("threshold", 0.12),
            reference_image=d.get("reference_image", ""),
        )


def _get_data_root() -> Path:
    """Return the root directory for user-writable page profile data."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_bundled_defaults_dir() -> Path:
    """
    Return the directory containing the bundled default page profiles + reference
    images. In a PyInstaller bundle this lives under _MEIPASS or _internal.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller --add-data preserves the assets/default_pages structure
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate = Path(meipass) / "assets" / "default_pages"
            if candidate.exists():
                return candidate
        # Onedir mode: assets sits inside _internal/
        exe_dir = Path(sys.executable).parent
        for sub in ("_internal/assets/default_pages", "assets/default_pages"):
            candidate = exe_dir / sub
            if candidate.exists():
                return candidate
        return exe_dir / "_internal" / "assets" / "default_pages"
    return Path(__file__).resolve().parent.parent / "assets" / "default_pages"


def get_profiles_path() -> Path:
    return _get_data_root() / "page_profiles.json"


def get_refs_dir() -> Path:
    d = _get_data_root() / "page_refs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _initialize_from_defaults() -> bool:
    """
    First-run setup: copy the bundled default page_profiles.json and reference
    images into the user data directory. Returns True if defaults were applied.
    """
    defaults_dir = _get_bundled_defaults_dir()
    defaults_json = defaults_dir / "page_profiles.json"
    if not defaults_json.exists():
        return False

    user_path = get_profiles_path()
    try:
        user_path.write_text(
            defaults_json.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    except Exception:
        return False

    refs_dir = get_refs_dir()
    for img in defaults_dir.glob("*.jpg"):
        target = refs_dir / img.name
        if not target.exists():
            try:
                shutil.copy2(img, target)
            except Exception:
                pass
    for img in defaults_dir.glob("*.png"):
        target = refs_dir / img.name
        if not target.exists():
            try:
                shutil.copy2(img, target)
            except Exception:
                pass

    return True


def load_profiles() -> list[PageProfile]:
    """Load all page profiles from the JSON file. On first run, seed from bundled defaults."""
    path = get_profiles_path()
    if not path.exists():
        _initialize_from_defaults()

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [PageProfile.from_dict(p) for p in data]
    except (json.JSONDecodeError, KeyError):
        return []


def save_profiles(profiles: list[PageProfile]) -> None:
    """Save all page profiles to the JSON file."""
    path = get_profiles_path()
    data = [p.to_dict() for p in profiles]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
