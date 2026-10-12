from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from requests import Session

from collector.convert import looks_like_junk_title, strip_html
from collector.http import get_json
from collector.models import Candidate, Category, CollectOptions
from collector.sources.base import ImageSource

API_URL = "https://pixabay.com/api/"
PER_PAGE = 200
MAX_WINDOW = 500


class PixabaySource(ImageSource):
    id = "pixabay"
    title = "Pixabay"
    needs_key = True

    def has_credentials(self, options: CollectOptions) -> bool:
        return bool(options.pixabay_key.strip())

    def iter_candidates(self, category: Category, session: Session, options: CollectOptions) -> Iterator[Candidate]:
        key = options.pixabay_key.strip()
        if not key:
            return
        seen: set[str] = set()
        for query in _queries(category):
            for order in ("popular", "latest"):
                yield from self._search(key, query, order, category, session, seen)

    def _search(
        self,
        key: str,
        query: str,
        order: str,
        category: Category,
        session: Session,
        seen: set[str],
    ) -> Iterator[Candidate]:
        for page in range(1, 8):
            data = _fetch(
                session,
                {
                    "key": key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": "horizontal",
                    "safesearch": "true",
                    "order": order,
                    "per_page": PER_PAGE,
                    "page": page,
                },
            )
            if not data:
                break
            hits = data.get("hits") or []
            if not hits:
                break
            for item in hits:
                candidate = self._to_candidate(item, category)
                if candidate is None or candidate.uid in seen:
                    continue
                seen.add(candidate.uid)
                yield candidate
            total = min(MAX_WINDOW, int(data.get("totalHits") or 0))
            if len(hits) < PER_PAGE or page * PER_PAGE >= total:
                break

    def _to_candidate(self, item: dict[str, Any], category: Category) -> Candidate | None:
        url = item.get("fullHDURL") or item.get("largeImageURL") or item.get("webformatURL")
        if not url:
            return None
        title = strip_html(item.get("tags") or "Pixabay photo")
        if looks_like_junk_title(title):
            return None
        return Candidate(
            uid=f"pixabay:{item.get('id')}",
            url=str(url),
            width=int(item.get("imageWidth") or 0),
            height=int(item.get("imageHeight") or 0),
            title=title,
            creator=strip_html(item.get("user") or "Pixabay"),
            license_name="Pixabay License",
            license_url="https://pixabay.com/service/license-summary/",
            source_name="Pixabay",
            landing_url=str(item.get("pageURL") or ""),
            category_id=category.id,
        )


def _queries(category: Category) -> list[str]:
    found: list[str] = []
    for query in (category.pixabay_query, *category.pixabay_queries):
        cleaned = " ".join(query.split())
        if cleaned and cleaned not in found:
            found.append(cleaned)
    return found


def _fetch(session: Session, params: dict[str, Any]) -> dict[str, Any] | None:
    for attempt in range(4):
        try:
            data = get_json(session, API_URL, params)
        except Exception:
            time.sleep(1.5 + attempt * 2)
            continue
        if isinstance(data, dict) and "hits" in data:
            return data
        time.sleep(1.5 + attempt * 2)
    return None
