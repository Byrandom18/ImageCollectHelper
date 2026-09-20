from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Category:
    id: str
    title: str
    hint: str
    openverse_query: str
    wikimedia_query: str
    wikimedia_categories: tuple[str, ...]
    pexels_query: str
    unsplash_query: str
    pixabay_query: str


@dataclass
class Candidate:
    uid: str
    url: str
    width: int
    height: int
    title: str
    creator: str
    license_name: str
    license_url: str
    source_name: str
    landing_url: str
    category_id: str


@dataclass
class CollectOptions:
    categories: list[Category]
    custom_query: str
    count: int
    start_number: int
    pad_width: int
    output_dir: Path
    landscape_only: bool = True
    crop_16_9: bool = True
    max_side: int = 1920
    webp_quality: int = 75
    min_webp_quality: int = 52
    max_file_kb: int = 220
    skip_existing: bool = True
    avoid_repeats: bool = True
    write_credits: bool = True
    shuffle: bool = True
    enabled_sources: list[str] = field(default_factory=lambda: ["wikimedia", "openverse"])
    pexels_key: str = ""
    unsplash_key: str = ""
    pixabay_key: str = ""
    use_local_proxy: bool = True
    proxy_url: str = ""


@dataclass
class SavedImage:
    path: Path
    number: int
    candidate: Candidate
