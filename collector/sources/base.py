from __future__ import annotations

from collections.abc import Iterator

from requests import Session

from collector.models import Candidate, Category, CollectOptions


class ImageSource:
    id: str = ""
    title: str = ""
    needs_key: bool = False

    def is_enabled(self, options: CollectOptions) -> bool:
        return self.id in options.enabled_sources

    def has_credentials(self, options: CollectOptions) -> bool:
        return True

    def iter_candidates(self, category: Category, session: Session, options: CollectOptions) -> Iterator[Candidate]:
        yield from ()
