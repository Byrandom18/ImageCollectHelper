from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from requests import Session

from collector.convert import looks_like_junk_title, strip_html
from collector.http import get_json
from collector.models import Candidate, Category, CollectOptions
from collector.sources.base import ImageSource

API_URL = "https://api.openverse.org/v1/images/"


class OpenverseSource(ImageSource):
    id = "openverse"
    title = "Openverse"
    needs_key = False

    def iter_candidates(self, category: Category, session: Session, options: CollectOptions) -> Iterator[Candidate]:
        for page in range(1, 9):
            params: dict[str, Any] = {
                "q": category.openverse_query,
                "page": page,
                "page_size": 20,
                "license_type": "commercial",
                "category": "photograph",
                "aspect_ratio": "wide",
                "mature": "false",
            }
            try:
                data = get_json(session, API_URL, params)
            except Exception:
                break
            results = data.get("results") or []
            if not results:
                break
            for item in results:
                candidate = self._to_candidate(item, category)
                if candidate is not None:
                    yield candidate
            time.sleep(1.05)
            page_count = int(data.get("page_count") or page)
            if page >= page_count:
                break

    def _to_candidate(self, item: dict[str, Any], category: Category) -> Candidate | None:
        url = item.get("url")
        if not url:
            return None
        title = strip_html(item.get("title") or "")
        if looks_like_junk_title(title):
            return None
        if item.get("mature"):
            return None
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        license_name = str(item.get("license") or "").upper()
        version = str(item.get("license_version") or "")
        if version:
            license_name = f"CC {license_name} {version}".strip()
        return Candidate(
            uid=f"openverse:{item.get('id')}",
            url=str(url),
            width=width,
            height=height,
            title=title or "Untitled",
            creator=strip_html(item.get("creator") or item.get("source") or "Openverse"),
            license_name=license_name or "CC",
            license_url=str(item.get("license_url") or ""),
            source_name=f"Openverse/{item.get('source') or 'unknown'}",
            landing_url=str(item.get("foreign_landing_url") or ""),
            category_id=category.id,
        )
