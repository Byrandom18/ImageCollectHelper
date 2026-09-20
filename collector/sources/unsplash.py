from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from requests import Session

from collector.convert import looks_like_junk_title, strip_html
from collector.models import Candidate, Category, CollectOptions
from collector.sources.base import ImageSource

API_URL = "https://api.unsplash.com/search/photos"


class UnsplashSource(ImageSource):
    id = "unsplash"
    title = "Unsplash"
    needs_key = True

    def has_credentials(self, options: CollectOptions) -> bool:
        return bool(options.unsplash_key.strip())

    def iter_candidates(self, category: Category, session: Session, options: CollectOptions) -> Iterator[Candidate]:
        key = options.unsplash_key.strip()
        if not key:
            return
        headers = {"Accept-Version": "v1", "Authorization": f"Client-ID {key}"}
        for page in range(1, 8):
            params = {
                "query": category.unsplash_query,
                "orientation": "landscape",
                "per_page": 30,
                "page": page,
                "content_filter": "high",
            }
            response = session.get(API_URL, params=params, headers=headers, timeout=30)
            if response.status_code in (401, 403, 429):
                break
            response.raise_for_status()
            data = response.json()
            results = data.get("results") or []
            if not results:
                break
            for item in results:
                candidate = self._to_candidate(item, category)
                if candidate is not None:
                    yield candidate
            total_pages = int(data.get("total_pages") or page)
            if page >= total_pages:
                break

    def _to_candidate(self, item: dict[str, Any], category: Category) -> Candidate | None:
        urls = item.get("urls") or {}
        raw = urls.get("raw")
        url = f"{raw}&w=1920&q=84&fm=jpg" if raw else urls.get("full") or urls.get("regular")
        if not url:
            return None
        title = strip_html(item.get("description") or item.get("alt_description") or "Unsplash photo")
        if looks_like_junk_title(title):
            return None
        user = item.get("user") or {}
        creator = strip_html(user.get("name") or "Unsplash")
        links = item.get("links") or {}
        return Candidate(
            uid=f"unsplash:{item.get('id')}",
            url=str(url),
            width=int(item.get("width") or 0),
            height=int(item.get("height") or 0),
            title=title,
            creator=creator,
            license_name="Unsplash License",
            license_url="https://unsplash.com/license",
            source_name="Unsplash",
            landing_url=str(links.get("html") or ""),
            category_id=category.id,
        )
