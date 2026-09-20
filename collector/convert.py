from __future__ import annotations

import html
import io
import re
from pathlib import Path

from PIL import Image, ImageOps

from collector.models import CollectOptions

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

SKIP_TITLE_TOKENS = {
    "map",
    "diagram",
    "logo",
    "icon",
    "flag",
    "svg",
    "chart",
    "screenshot",
    "clipart",
    "banner",
    "sign",
}
SKIP_TITLE_PHRASES = ("coat of arms", "qr code")


class SkipImage(Exception):
    pass


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _TAG_RE.sub(" ", str(text))
    cleaned = html.unescape(cleaned)
    return _SPACE_RE.sub(" ", cleaned).strip()


def looks_like_junk_title(title: str) -> bool:
    lowered = title.lower()
    if any(phrase in lowered for phrase in SKIP_TITLE_PHRASES):
        return True
    tokens = set(re.split(r"[\s_\-.,/()]+", lowered))
    return bool(tokens & SKIP_TITLE_TOKENS)


def average_hash(image: Image.Image, size: int = 8) -> int:
    small = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    avg = sum(pixels) / max(1, len(pixels))
    bits = 0
    for pixel in pixels:
        bits = (bits << 1) | (1 if pixel >= avg else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def to_rgb(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image) or image
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def crop_to_aspect(image: Image.Image, aspect: float = 16 / 9) -> Image.Image:
    width, height = image.size
    if width < 2 or height < 2:
        raise SkipImage("слишком маленькое изображение")
    current = width / height
    if abs(current - aspect) < 0.02:
        return image
    if current > aspect:
        new_width = max(1, int(round(height * aspect)))
        left = max(0, (width - new_width) // 2)
        return image.crop((left, 0, left + new_width, height))
    new_height = max(1, int(round(width / aspect)))
    top = max(0, (height - new_height) // 2)
    return image.crop((0, top, width, top + new_height))


def downscale(image: Image.Image, max_side: int) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def process_bytes(data: bytes, options: CollectOptions) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise SkipImage(f"не удалось открыть файл: {exc}") from exc

    image = to_rgb(image)
    width, height = image.size
    if width < 2 or height < 2:
        raise SkipImage(f"битый файл ({width}x{height})")
    if options.landscape_only and width < height:
        raise SkipImage("портретная ориентация")
    if options.crop_16_9:
        image = crop_to_aspect(image, 16 / 9)
    image = downscale(image, options.max_side)
    return image


def encode_webp(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(
        buffer,
        format="WEBP",
        quality=max(40, min(95, int(quality))),
        method=6,
        exact=False,
    )
    return buffer.getvalue()


def _fit_quality(image: Image.Image, max_quality: int, min_quality: int, budget: int) -> tuple[bytes, int]:
    max_quality = max(min_quality, max_quality)
    high = encode_webp(image, max_quality)
    if budget <= 0 or len(high) <= budget:
        return high, max_quality
    low = encode_webp(image, min_quality)
    if len(low) > budget:
        return low, min_quality
    best_data, best_q = low, min_quality
    lo, hi = min_quality + 1, max_quality - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        data = encode_webp(image, mid)
        if len(data) <= budget:
            best_data, best_q = data, mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best_data, best_q


def _size_ladder(image: Image.Image, max_side: int) -> list[Image.Image]:
    longest = max(image.size)
    cap = min(longest, max_side)
    steps: list[Image.Image] = []
    seen: set[tuple[int, int]] = set()
    for side in (cap, 1760, 1600, 1440, 1280):
        if side > cap or side < 1280:
            continue
        candidate = downscale(image, side)
        if candidate.size in seen:
            continue
        if candidate.size[0] < 1280 or candidate.size[1] < 720:
            continue
        seen.add(candidate.size)
        steps.append(candidate)
    return steps or [image]


def save_webp(image: Image.Image, path: Path, options: CollectOptions) -> tuple[int, int, tuple[int, int]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    budget = max(0, int(options.max_file_kb)) * 1024
    max_q = max(40, min(95, int(options.webp_quality)))
    min_q = max(40, min(max_q, int(options.min_webp_quality)))
    best_data: bytes | None = None
    best_q = max_q
    best_size = image.size
    for variant in _size_ladder(image, options.max_side):
        data, quality = _fit_quality(variant, max_q, min_q, budget)
        if best_data is None or (budget > 0 and len(data) < len(best_data)):
            best_data, best_q, best_size = data, quality, variant.size
        if budget <= 0:
            break
        if len(data) <= budget:
            best_data, best_q, best_size = data, quality, variant.size
            break
    assert best_data is not None
    path.write_bytes(best_data)
    return len(best_data), best_q, best_size
