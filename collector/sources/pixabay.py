from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from requests import Session

from collector.convert import looks_like_junk_title, strip_html
from collector.http import get_json
from collector.models import Candidate, Category, CollectOptions
from collector.sources.base import ImageSource

API_URL = "https://pixabay.com/api/"


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
        for page in range(1, 8):
            params = {
                "key": key,
                "q": category.pixabay_query,
                "image_type": "photo",
                "orientation": "horizontal",
                "safesearch": "true",
                "per_page": 40,
                "page": page,
            }
            data = get_json(session, API_URL, params)
            hits = data.get("hits") or []
            if not hits:
                break
            for item in hits:
                candidate = self._to_candidate(item, category)
                if candidate is not None:
                    yield candidate
            if page * 40 >= int(data.get("totalHits") or 0):
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
