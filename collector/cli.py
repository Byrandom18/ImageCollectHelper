from __future__ import annotations

import argparse
from pathlib import Path
from threading import Event

from collector.categories import CATEGORIES, by_id, custom_category
from collector.models import CollectOptions
from collector.pipeline import collect_images
from collector.storage import load_secrets


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сбор открытых фото в WebP для JigsawPuzzles")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--pad", type=int, default=2)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--categories", default="landscapes,places,animals,food")
    parser.add_argument("--query", default="")
    parser.add_argument("--no-crop", action="store_true")
    parser.add_argument("--allow-portrait", action="store_true")
    parser.add_argument("--quality", type=int, default=75)
    parser.add_argument("--max-kb", type=int, default=220)
    parser.add_argument("--max-side", type=int, default=1920)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-proxy", action="store_true", help="не использовать локальный прокси")
    parser.add_argument("--proxy", default="", help="адрес прокси, иначе определяется сам")
    args = parser.parse_args(argv)

    selected = []
    for item_id in args.categories.split(","):
        item_id = item_id.strip()
        if not item_id:
            continue
        found = by_id(item_id)
        if found is None:
            parser.error(f"неизвестная категория: {item_id}. Доступны: {', '.join(c.id for c in CATEGORIES)}")
        selected.append(found)
    if args.query.strip():
        selected.append(custom_category(args.query))
    if not selected:
        parser.error("нужна хотя бы одна категория")

    secrets = load_secrets()
    options = CollectOptions(
        categories=selected,
        custom_query=args.query,
        count=max(1, args.count),
        start_number=max(1, args.start),
        pad_width=max(2, args.pad),
        output_dir=args.out.expanduser().resolve(),
        landscape_only=not args.allow_portrait,
        crop_16_9=not args.no_crop,
        max_side=args.max_side,
        webp_quality=args.quality,
        max_file_kb=max(0, args.max_kb),
        skip_existing=not args.overwrite,
        use_local_proxy=not args.no_proxy,
        proxy_url=args.proxy,
        pexels_key=secrets.get("pexels_key", ""),
        unsplash_key=secrets.get("unsplash_key", ""),
        pixabay_key=secrets.get("pixabay_key", ""),
    )

    def progress(saved: int, total: int, message: str, _path) -> None:
        print(f"[{saved}/{total}] {message}")

    saved = collect_images(options, progress=progress, cancel=Event())
    print(f"Saved {len(saved)} files to {options.output_dir}")
    return 0 if saved else 1
