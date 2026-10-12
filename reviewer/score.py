from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

IMAGE_EXTS = {".webp", ".png", ".jpg", ".jpeg", ".bmp"}


@dataclass
class CellInfo:
    index: int
    col: int
    row: int
    std: float
    mean_rgb: tuple[int, int, int]
    ahash: int


@dataclass
class Analysis:
    cols: int
    rows: int
    largest: int
    max_cluster: int
    bad_cells: set[int] = field(default_factory=set)
    error: str = ""

    @property
    def total(self) -> int:
        return self.cols * self.rows

    @property
    def ok(self) -> bool:
        return not self.error and self.largest <= self.max_cluster

    @property
    def summary(self) -> str:
        if self.error:
            return self.error
        group = f"похожих ячеек: {self.largest} из {self.total}"
        if self.ok:
            return f"{group} — подходит"
        return f"{group} — много одинаковых областей"


def list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS and not path.name.startswith(".")
    ]
    files.sort(key=_sort_key)
    return files


def prepare_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image) or image
        image = image.convert("RGB")
        image.thumbnail((1400, 1400), Image.Resampling.NEAREST)
        return image.copy()


def analyze_file(path: Path, cols: int, rows: int, max_cluster: int) -> Analysis:
    try:
        return analyze_image(prepare_image(path), cols, rows, max_cluster)
    except Exception as exc:
        return Analysis(cols=cols, rows=rows, largest=0, max_cluster=max_cluster, error=f"не открывается: {exc}")


def analyze_image(image: Image.Image, cols: int, rows: int, max_cluster: int) -> Analysis:
    cols = max(2, int(cols))
    rows = max(2, int(rows))
    max_cluster = max(1, int(max_cluster))
    rgb = image.convert("RGB")
    width, height = rgb.size
    cells = [
        _cell_info(rgb, col, row, cols, rows, width, height)
        for row in range(rows)
        for col in range(cols)
    ]
    clusters = _clusters(cells)
    sizes = {root: 0 for root in clusters}
    for root in clusters:
        sizes[root] = sizes.get(root, 0) + 1
    largest = max(sizes.values()) if sizes else 1
    bad_roots = {root for root, size in sizes.items() if size > max_cluster}
    bad_cells = {cell.index for cell, root in zip(cells, clusters) if root in bad_roots}
    return Analysis(
        cols=cols,
        rows=rows,
        largest=largest,
        max_cluster=max_cluster,
        bad_cells=bad_cells,
    )


def paint_grid(image: Image.Image, analysis: Analysis) -> Image.Image:
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = base.size
    for row in range(analysis.rows):
        for col in range(analysis.cols):
            x0, y0, x1, y1 = _box(width, height, col, row, analysis.cols, analysis.rows)
            index = row * analysis.cols + col
            if index in analysis.bad_cells:
                draw.rectangle((x0, y0, x1, y1), fill=(210, 48, 48, 110))
            draw.rectangle((x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)), outline=(255, 255, 255, 150))
    return Image.alpha_composite(base, overlay).convert("RGB")


def _sort_key(path: Path) -> tuple:
    stem = path.stem
    if stem.isdigit():
        return (0, int(stem), path.name.lower())
    return (1, 0, path.name.lower())


def _box(width: int, height: int, col: int, row: int, cols: int, rows: int) -> tuple[int, int, int, int]:
    x0 = col * width // cols
    x1 = (col + 1) * width // cols
    y0 = row * height // rows
    y1 = (row + 1) * height // rows
    return x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)


def _cell_info(image: Image.Image, col: int, row: int, cols: int, rows: int, width: int, height: int) -> CellInfo:
    x0, y0, x1, y1 = _box(width, height, col, row, cols, rows)
    cell = image.crop((x0, y0, x1, y1))
    gray = list(cell.convert("L").resize((32, 32), Image.Resampling.NEAREST).getdata())
    mean = sum(gray) / len(gray)
    std = math.sqrt(sum((pixel - mean) ** 2 for pixel in gray) / len(gray))
    pixel = cell.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    mean_rgb = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
    return CellInfo(
        index=row * cols + col,
        col=col,
        row=row,
        std=std,
        mean_rgb=mean_rgb,
        ahash=_ahash(cell),
    )


def _ahash(cell: Image.Image) -> int:
    pixels = list(cell.convert("L").resize((8, 8), Image.Resampling.BOX).getdata())
    average = sum(pixels) / len(pixels)
    bits = 0
    for pixel in pixels:
        bits = (bits << 1) | (1 if pixel >= average else 0)
    return bits


def _similar(left: CellInfo, right: CellInfo) -> bool:
    color = math.dist(left.mean_rgb, right.mean_rgb)
    hamming = (left.ahash ^ right.ahash).bit_count()
    if left.std < 18 and right.std < 18 and color < 34:
        return True
    if left.std < 10 and right.std < 10 and color < 52:
        return True
    return hamming <= 6 and color < 28 and max(left.std, right.std) < 24


def _clusters(cells: list[CellInfo]) -> list[int]:
    parent = list(range(len(cells)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for i, left in enumerate(cells):
        for j in range(i + 1, len(cells)):
            if _similar(left, cells[j]):
                parent[find(j)] = find(i)
    return [find(index) for index in range(len(cells))]
