from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from requests import Session

from collector.convert import looks_like_junk_title, strip_html
from collector.http import get_json
from collector.models import Candidate, Category, CollectOptions
from collector.sources.base import ImageSource

API_URL = "https://commons.wikimedia.org/w/api.php"
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/tiff"}
BLOCKED_LICENSE = ("fair use", "non-free", "nonfree", "unlicensed")
_FILE_RE = re.compile(r"^File:", re.I)


class WikimediaSource(ImageSource):
    id = "wikimedia"
    title = "Wikimedia Commons"
    needs_key = False

    def iter_candidates(self, category: Category, session: Session, options: CollectOptions) -> Iterator[Candidate]:
        seen: set[str] = set()
        for wiki_cat in category.wikimedia_categories:
            for candidate in self._category_members(wiki_cat, category, session):
                if candidate.uid not in seen:
                    seen.add(candidate.uid)
                    yield candidate
        offset = 0
        for _ in range(10):
            batch, next_offset = self._search(category.wikimedia_query, offset, category, session)
            if not batch:
                break
            for candidate in batch:
                if candidate.uid not in seen:
                    seen.add(candidate.uid)
                    yield candidate
            if next_offset is None or next_offset <= offset:
                break
            offset = next_offset

    def _category_members(self, wiki_cat: str, category: Category, session: Session) -> Iterator[Candidate]:
        params: dict[str, Any] = {
            "action": "query",
            "format": "json",
            "generator": "categorymembers",
            "gcmtitle": f"Category:{wiki_cat}",
            "gcmtype": "file",
            "gcmlimit": 50,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1920,
            "origin": "*",
        }
        for _ in range(8):
            data = get_json(session, API_URL, params)
            yield from self._parse_pages(data, category)
            cont = data.get("continue") or {}
            if "gcmcontinue" not in cont:
                break
            params["gcmcontinue"] = cont["gcmcontinue"]

    def _search(self, query: str, offset: int, category: Category, session: Session) -> tuple[list[Candidate], int | None]:
        params: dict[str, Any] = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 40,
            "gsroffset": offset,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1920,
            "origin": "*",
        }
        data = get_json(session, API_URL, params)
        items = list(self._parse_pages(data, category))
        cont = data.get("continue") or {}
        next_offset = cont.get("gsroffset")
        return items, int(next_offset) if next_offset is not None else None

    def _parse_pages(self, data: dict[str, Any], category: Category) -> Iterator[Candidate]:
        pages = (data.get("query") or {}).get("pages") or {}
        ordered = sorted(pages.values(), key=lambda page: int(page.get("index") or page.get("pageid") or 0))
        for page in ordered:
            info_list = page.get("imageinfo") or []
            if not info_list:
                continue
            info = info_list[0]
            mime = str(info.get("mime") or "").lower()
            if mime not in ALLOWED_MIME:
                continue
            title = strip_html(page.get("title") or "")
            if looks_like_junk_title(title):
                continue
            meta = info.get("extmetadata") or {}
            license_name = strip_html(_meta(meta, "LicenseShortName") or _meta(meta, "License"))
            if any(bad in license_name.lower() for bad in BLOCKED_LICENSE):
                continue
            orig_w = int(info.get("width") or 0)
            orig_h = int(info.get("height") or 0)
            url = _download_url(info)
            if not url:
                continue
            page_id = str(page.get("pageid") or title)
            yield Candidate(
                uid=f"wikimedia:{page_id}",
                url=str(url),
                width=orig_w,
                height=orig_h,
                title=_FILE_RE.sub("", title),
                creator=strip_html(_meta(meta, "Artist") or _meta(meta, "Credit") or "Wikimedia Commons"),
                license_name=license_name or "Unknown",
                license_url=strip_html(_meta(meta, "LicenseUrl")),
                source_name="Wikimedia Commons",
                landing_url=str(info.get("descriptionurl") or ""),
                category_id=category.id,
            )


def _meta(meta: dict[str, Any], key: str) -> str:
    item = meta.get(key) or {}
    if isinstance(item, dict):
        return str(item.get("value") or "")
    return str(item)


def _download_url(info: dict[str, Any]) -> str | None:
    original = info.get("url")
    thumb = info.get("thumburl")
    thumb_w = int(info.get("thumbwidth") or 0)
    thumb_h = int(info.get("thumbheight") or 0)
    orig_w = int(info.get("width") or 0)
    orig_h = int(info.get("height") or 0)
    if thumb and min(thumb_w, thumb_h) >= 1000:
        return str(thumb)
    if orig_w > 0 and orig_h > 0 and thumb:
        target_short = 1200
        if orig_w >= orig_h:
            target_w = int(orig_w * target_short / orig_h)
        else:
            target_w = target_short
        target_w = max(1920, min(target_w, orig_w, 4500))
        wider = re.sub(r"/\d+px-", f"/{target_w}px-", str(thumb), count=1)
        if wider != thumb:
            return wider
    return str(original or thumb or "") or None
