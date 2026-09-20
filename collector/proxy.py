from __future__ import annotations

import os
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

_ENV_KEYS = ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy", "ALL_PROXY", "all_proxy")
_LOCAL_PORTS = (10809, 7890, 10808, 1080, 8889, 8888, 20171, 2080, 7897, 8118, 6152, 1087)


@dataclass(frozen=True)
class ProxyConfig:
    url: str
    verify: bool
    source: str

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    @property
    def display(self) -> str:
        if not self.url:
            return "нет"
        return f"{redact_proxy(self.url)} ({self.source})"


def redact_proxy(url: str) -> str:
    return re.sub(r"(://)([^/@]+@)", r"\1***@", url)


def _normalize(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    return url


def _is_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _env_proxy() -> str:
    for key in _ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return _normalize(value)
    return ""


def _windows_system_proxy() -> str:
    try:
        import winreg
    except ImportError:
        return ""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not int(enabled):
                return ""
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
    except OSError:
        return ""
    server = str(server or "").strip()
    if not server:
        return ""
    if "=" in server:
        parts = {}
        for item in server.split(";"):
            if "=" in item:
                scheme, addr = item.split("=", 1)
                parts[scheme.strip().lower()] = addr.strip()
        server = parts.get("https") or parts.get("http") or next(iter(parts.values()), "")
    return _normalize(server)


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def _listening_local_proxy() -> str:
    for port in _LOCAL_PORTS:
        if _port_open("127.0.0.1", port):
            return f"http://127.0.0.1:{port}"
    return ""


def resolve_proxy(enabled: bool = True, override: str = "") -> ProxyConfig:
    if not enabled:
        return ProxyConfig("", True, "выключен")
    url = _normalize(override) or _env_proxy()
    source = "поле в программе" if override.strip() else ("окружение" if url else "")
    if not url:
        url = _windows_system_proxy()
        source = "системный прокси Windows"
    if not url:
        url = _listening_local_proxy()
        source = "локальный порт"
    if not url:
        return ProxyConfig("", True, "не найден")
    verify = not _is_local(url)
    return ProxyConfig(url, verify, source)


def apply_proxy_env(config: ProxyConfig) -> None:
    if not config.url:
        return
    os.environ["HTTP_PROXY"] = config.url
    os.environ["HTTPS_PROXY"] = config.url
    os.environ["http_proxy"] = config.url
    os.environ["https_proxy"] = config.url
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
    os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
