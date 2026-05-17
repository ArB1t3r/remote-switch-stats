"""Page profile data model and JSON persistence."""

from __future__ import annotations

import json
import os
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
    """Return the root directory for page profile data (next to exe or project root)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def get_profiles_path() -> Path:
    return _get_data_root() / "page_profiles.json"


def get_refs_dir() -> Path:
    d = _get_data_root() / "page_refs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_profiles() -> list[PageProfile]:
    """Load all page profiles from the JSON file."""
    path = get_profiles_path()
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
