from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from reviewer.score import Analysis, analyze_image, prepare_image

# От крупных кусков к мелким. Картинка получает самую мелкую сетку,
# на которой похожих ячеек ещё не больше порога.
GRID_LADDER: tuple[tuple[int, int], ...] = (
    (3, 2),
    (4, 3),
    (5, 4),
    (6, 4),
    (8, 5),
    (8, 6),
    (10, 6),
    (10, 8),
)


@dataclass(frozen=True)
class Recommendation:
    cols: int
    rows: int
    rank: int
    largest: int
    total: int
    fits: bool
    error: str = ""

    @property
    def label(self) -> str:
        return f"{self.cols}×{self.rows}"

    @property
    def folder(self) -> str:
        return f"{self.cols}x{self.rows}"

    @property
    def summary(self) -> str:
        if self.error:
            return self.error
        if self.fits:
            return f"сетка {self.label}"
        return f"даже {self.label} много похожих"


def recommend_image(image: Image.Image, max_cluster: int) -> Recommendation:
    chosen: Recommendation | None = None
    for rank, (cols, rows) in enumerate(GRID_LADDER):
        analysis = analyze_image(image, cols, rows, max_cluster)
        if not analysis.ok:
            if chosen is None:
                return _from_analysis(analysis, rank, fits=False)
            return chosen
        chosen = _from_analysis(analysis, rank, fits=True)
    if chosen is None:
        cols, rows = GRID_LADDER[0]
        return Recommendation(cols, rows, 0, 0, cols * rows, False, "пустая сетка")
    return chosen


def recommend_file(path: Path, max_cluster: int) -> Recommendation:
    try:
        return recommend_image(prepare_image(path), max_cluster)
    except Exception as exc:
        cols, rows = GRID_LADDER[0]
        return Recommendation(cols, rows, 0, 0, cols * rows, False, f"не открывается: {exc}")


def _from_analysis(analysis: Analysis, rank: int, fits: bool) -> Recommendation:
    return Recommendation(
        cols=analysis.cols,
        rows=analysis.rows,
        rank=rank,
        largest=analysis.largest,
        total=analysis.total,
        fits=fits,
        error=analysis.error,
    )
