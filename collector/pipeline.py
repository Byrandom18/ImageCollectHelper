from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from threading import Event

from collector.convert import SkipImage, average_hash, hamming, process_bytes, save_webp
from collector.http import get_bytes, make_session
from collector.models import Candidate, CollectOptions, SavedImage
from collector.paths import numbered_name
from collector.sources import all_sources
from collector.storage import load_seen_ids, save_seen_ids

ProgressCb = Callable[[int, int, str, Path | None], None]


def collect_images(
    options: CollectOptions,
    progress: ProgressCb | None = None,
    cancel: Event | None = None,
) -> list[SavedImage]:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    seen = load_seen_ids() if options.avoid_repeats else set()
    hashes: list[int] = []
    saved: list[SavedImage] = []
    session, proxy = make_session(options.use_local_proxy, options.proxy_url)
    next_number = max(1, options.start_number)

    def log(message: str, path: Path | None = None) -> None:
        if not progress:
            return
        try:
            progress(len(saved), options.count, message, path)
        except Exception:
            try:
                progress(len(saved), options.count, message.encode("ascii", "replace").decode("ascii"), path)
            except Exception:
                pass

    log(f"Поиск в {options.output_dir}")
    if options.use_local_proxy:
        log(f"Прокси: {proxy.display}")
    else:
        log("Прокси выключен")
    sources = [
        source
        for source in all_sources()
        if source.is_enabled(options) and source.has_credentials(options)
    ]
    if not sources:
        raise RuntimeError("Нет включённых источников. Включите Wikimedia/Openverse или укажите ключи API.")
    if not options.categories:
        raise RuntimeError("Не выбраны категории.")

    for candidate in _iter_mixed_candidates(options, sources, session, log):
        if cancel is not None and cancel.is_set():
            log("Остановлено")
            break
        if len(saved) >= options.count:
            break
        if candidate.uid in seen:
            continue
        if candidate.width and candidate.height:
            if options.landscape_only and candidate.width < candidate.height:
                continue
        try:
            next_number = _next_free_number(options, next_number)
            target = options.output_dir / numbered_name(next_number, options.pad_width)
            log(f"Скачиваю {candidate.title[:80]}…")
            data = get_bytes(session, candidate.url)
            image = process_bytes(data, options)
            digest = average_hash(image)
            if any(hamming(digest, old) <= 6 for old in hashes):
                log("Похожий кадр, пропуск")
                continue
            size, quality, wh = save_webp(image, target, options)
            hashes.append(digest)
            seen.add(candidate.uid)
            item = SavedImage(path=target, number=next_number, candidate=candidate)
            saved.append(item)
            next_number += 1
            kb = max(1, round(size / 1024))
            log(
                f"Сохранено {target.name}  {kb} КБ  q{quality}  {wh[0]}x{wh[1]}  ({len(saved)}/{options.count})",
                target,
            )
        except SkipImage as exc:
            log(f"Пропуск: {exc}")
        except Exception as exc:
            log(f"Ошибка: {exc}")

    if options.avoid_repeats:
        save_seen_ids(seen)
    if options.write_credits and saved:
        credits_file = _credits_path(options.output_dir)
        _write_credits(credits_file, saved)
        log(f"Авторы записаны в {credits_file}")
    log(f"Готово: {len(saved)} из {options.count}")
    return saved


def _iter_mixed_candidates(options, sources, session, log) -> Iterator[Candidate]:
    iterators: list[Iterator[Candidate]] = []
    categories = list(options.categories)
    if options.shuffle:
        random.shuffle(categories)
    for category in categories:
        for source in sources:
            iterators.append(_guarded(source.iter_candidates(category, session, options), source.title, log))
    if options.shuffle:
        random.shuffle(iterators)
    yield from _round_robin(iterators)


def _guarded(iterator: Iterator[Candidate], source_title: str, log) -> Iterator[Candidate]:
    try:
        for item in iterator:
            yield item
    except Exception as exc:
        log(f"{source_title}: {exc}")


def _round_robin(iterators: list[Iterator[Candidate]]) -> Iterator[Candidate]:
    active = list(iterators)
    while active:
        still: list[Iterator[Candidate]] = []
        for iterator in active:
            try:
                yield next(iterator)
                still.append(iterator)
            except StopIteration:
                continue
        if not still:
            break
        active = still


def _next_free_number(options: CollectOptions, number: int) -> int:
    current = number
    if not options.skip_existing:
        return current
    while True:
        path = options.output_dir / numbered_name(current, options.pad_width)
        if not path.exists():
            return current
        current += 1


def _credits_path(folder: Path) -> Path:
    parts = folder.parts
    for index, part in enumerate(parts):
        if part.lower() == "streamingassets":
            assets = Path(*parts[:index])
            content = assets / "Content"
            content.mkdir(parents=True, exist_ok=True)
            return content / "image_credits.txt"
    return folder / "credits.txt"


def _write_credits(path: Path, saved: list[SavedImage]) -> None:
    lines = [
        f"Собрано {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "Открытые источники. Сохраняйте указание автора, если этого требует лицензия.",
        "",
    ]
    for item in saved:
        cand = item.candidate
        lines.append(
            f"{item.path.name}\t{cand.title}\t{cand.creator}\t{cand.license_name}\t"
            f"{cand.license_url}\t{cand.landing_url}\t{cand.source_name}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    block = "\n".join(lines) + "\n"
    path.write_text((existing + ("\n" if existing else "") + block).strip() + "\n", encoding="utf-8")
