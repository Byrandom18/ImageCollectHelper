from collector.sources.openverse import OpenverseSource
from collector.sources.pexels import PexelsSource
from collector.sources.pixabay import PixabaySource
from collector.sources.unsplash import UnsplashSource
from collector.sources.wikimedia import WikimediaSource
from collector.sources.base import ImageSource

__all__ = [
    "ImageSource",
    "OpenverseSource",
    "PexelsSource",
    "PixabaySource",
    "UnsplashSource",
    "WikimediaSource",
    "all_sources",
]


def all_sources() -> list[ImageSource]:
    return [
        WikimediaSource(),
        OpenverseSource(),
        PexelsSource(),
        UnsplashSource(),
        PixabaySource(),
    ]
