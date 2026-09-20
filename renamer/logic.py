from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTS = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".bmp"}
SKIP_NAMES = {"credits.txt", "thumbs.db", "desktop.ini", "image_credits.txt"}
_NUM_STEM = re.compile(r"^\d+$")


@dataclass(frozen=True)
class RenameItem:
    source: Path
    dest: Path

    @property
    def changed(self) -> bool:
        return self.source.name != self.dest.name


def numeric_index(path: Path) -> int | None:
    if not _NUM_STEM.fullmatch(path.stem):
        return None
    return int(path.stem)


def list_numbered_files(folder: Path, images_only: bool = True) -> list[Path]:
    files: list[tuple[int, Path]] = []
    if not folder.is_dir():
        return []
    for path in folder.iterdir():
        if not path.is_file():
            continue
        if path.name.lower() in SKIP_NAMES:
            continue
        if path.suffix.lower() == ".meta":
            continue
        index = numeric_index(path)
        if index is None:
            continue
        if images_only and path.suffix.lower() not in IMAGE_EXTS:
            continue
        files.append((index, path))
    files.sort(key=lambda item: (item[0], item[1].name.lower()))
    return [path for _index, path in files]


def build_plan(folder: Path, start: int = 1, pad_width: int = 2, images_only: bool = True) -> list[RenameItem]:
    start = max(1, int(start))
    pad_width = max(1, int(pad_width))
    plan: list[RenameItem] = []
    number = start
    for source in list_numbered_files(folder, images_only=images_only):
        dest = folder / f"{number:0{pad_width}d}{source.suffix}"
        plan.append(RenameItem(source=source, dest=dest))
        number += 1
    return plan


def apply_plan(plan: list[RenameItem]) -> list[RenameItem]:
    changed = [item for item in plan if item.changed]
    if not changed:
        return []

    sources = {item.source.resolve() for item in plan}
    for item in changed:
        if item.dest.exists() and item.dest.resolve() not in sources:
            raise FileExistsError(f"уже есть файл {item.dest.name}, переименование остановлено")

    staged: list[tuple[Path, Path, Path | None, Path | None]] = []
    for index, item in enumerate(changed):
        temp = item.source.with_name(f".__renum_{index}_{item.source.name}")
        meta_src = _meta_for(item.source)
        item.source.rename(temp)
        meta_temp = None
        meta_dest = _meta_for(item.dest)
        if meta_src.is_file():
            meta_temp = item.source.parent / (temp.name + ".meta")
            meta_src.rename(meta_temp)
        staged.append((temp, item.dest, meta_temp, meta_dest))

    for temp, dest, meta_temp, meta_dest in staged:
        if dest.exists():
            raise FileExistsError(f"не удалось записать {dest.name}: файл уже существует")
        temp.rename(dest)
        if meta_temp is not None:
            if meta_dest.exists():
                meta_dest.unlink()
            meta_temp.rename(meta_dest)
    return changed


def _meta_for(path: Path) -> Path:
    return Path(str(path) + ".meta")
