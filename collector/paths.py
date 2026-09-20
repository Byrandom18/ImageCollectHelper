from __future__ import annotations

from pathlib import Path

UNITY_ROOT = Path(r"C:\Unity\JigsawPuzzles")

DESTINATIONS = (
    ("campaign", "Кампания", UNITY_ROOT / "Assets" / "StreamingAssets" / "campaign"),
    ("dailies", "Ежедневные", UNITY_ROOT / "Assets" / "StreamingAssets" / "dailies"),
    ("tabs", "Картинки вкладок", UNITY_ROOT / "Assets" / "StreamingAssets" / "campaign" / "tabs"),
    ("custom", "Своя папка", Path.home() / "Pictures" / "JigsawCollect"),
)


def destination_path(dest_id: str, custom: str | None = None) -> Path:
    for item_id, _title, path in DESTINATIONS:
        if item_id == dest_id:
            if item_id == "custom" and custom:
                return Path(custom)
            return path
    return Path(custom) if custom else DESTINATIONS[-1][2]


def numbered_name(number: int, pad_width: int) -> str:
    width = max(2, int(pad_width))
    return f"{number:0{width}d}.webp"
