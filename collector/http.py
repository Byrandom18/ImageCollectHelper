from __future__ import annotations

import time
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

from collector.proxy import ProxyConfig, apply_proxy_env, resolve_proxy

USER_AGENT = (
    "ImageCollectHelper/1.0 "
    "(local jigsaw-puzzle content tool; open-licensed image collector)"
)
MAX_DOWNLOAD_BYTES = 28 * 1024 * 1024


def make_session(use_proxy: bool = True, proxy_url: str = "") -> tuple[requests.Session, ProxyConfig]:
    config = resolve_proxy(use_proxy, proxy_url)
    apply_proxy_env(config)
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        }
    )
    if config.url:
        session.trust_env = False
        session.proxies.update({"http": config.url, "https": config.url})
        session.verify = config.verify
        if not config.verify:
            urllib3.disable_warnings(InsecureRequestWarning)
    return session, config


def get_json(session: requests.Session, url: str, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    response = session.get(url, params=params, timeout=timeout, headers={"Accept": "application/json"})
    if response.status_code == 429:
        wait = float(response.headers.get("Retry-After", "2"))
        time.sleep(min(max(wait, 1.0), 20.0))
        response = session.get(url, params=params, timeout=timeout, headers={"Accept": "application/json"})
    response.raise_for_status()
    return response.json()


def get_bytes(session: requests.Session, url: str, timeout: int = 45) -> bytes:
    with session.get(url, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise RuntimeError("файл больше 28 МБ, пропуск")
            chunks.append(chunk)
        return b"".join(chunks)
