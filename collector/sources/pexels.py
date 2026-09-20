from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from requests import Session

from collector.convert import looks_like_junk_title, strip_html
from collector.models import Candidate, Category, CollectOptions
from collector.sources.base import ImageSource

API_URL = "https://api.pexels.com/v1/search"


class PexelsSource(ImageSource):
    id = "pexels"
    title = "Pexels"
    needs_key = True

    def has_credentials(self, options: CollectOptions) -> bool:
        return bool(options.pexels_key.strip())

    def iter_candidates(self, category: Category, session: Session, options: CollectOptions) -> Iterator[Candidate]:
        key = options.pexels_key.strip()
        if not key:
            return
        headers = {"Authorization": key}
        for page in range(1, 8):
            params = {
                "query": category.pexels_query,
                "orientation": "landscape",
                "size": "large",
                "per_page": 40,
                "page": page,
            }
            response = session.get(API_URL, params=params, headers=headers, timeout=30)
            if response.status_code == 429:
                break
            response.raise_for_status()
            data = response.json()
            photos = data.get("photos") or []
            if not photos:
                break
            for item in photos:
                candidate = self._to_candidate(item, category)
                if candidate is not None:
                    yield candidate
            if page * 40 >= int(data.get("total_results") or 0):
                break

    def _to_candidate(self, item: dict[str, Any], category: Category) -> Candidate | None:
        src = item.get("src") or {}
        url = src.get("large2x") or src.get("large") or src.get("original")
        if not url:
            return None
        title = strip_html(item.get("alt") or "Pexels photo")
        if looks_like_junk_title(title):
            return None
        photographer = strip_html(item.get("photographer") or "Pexels")
        return Candidate(
            uid=f"pexels:{item.get('id')}",
            url=str(url),
            width=int(item.get("width") or 0),
            height=int(item.get("height") or 0),
            title=title,
            creator=photographer,
            license_name="Pexels License",
            license_url="https://www.pexels.com/license/",
            source_name="Pexels",
            landing_url=str(item.get("url") or ""),
            category_id=category.id,
        )
