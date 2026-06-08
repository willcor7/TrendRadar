# coding=utf-8
"""
Module de repli CDN

Fournit une capacité de repli multi-sources pour les requêtes distantes telles
que la vérification de version. Par défaut, utilise le lien brut GitHub et bascule
automatiquement vers une source CDN de secours en cas d'échec.
Mémorise l'index de la source disponible au sein d'une même session, et les
requêtes suivantes démarrent leurs tentatives à partir de cette source.
"""

import re
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_GITHUB_RAW_PATTERN = re.compile(
    r"^https://raw\.githubusercontent\.com/sansan0/TrendRadar/(?:refs/heads/)?master/(.+)$"
)

_ALL_SOURCES = [
    "https://raw.githubusercontent.com/sansan0/TrendRadar/refs/heads/master/",
    "https://fastly.jsdelivr.net/gh/sansan0/TrendRadar@master/",
    "https://cdn.jsdelivr.net/gh/sansan0/TrendRadar@master/",
    "https://gcore.jsdelivr.net/gh/sansan0/TrendRadar@master/",
]

_SOURCE_LABELS = {
    _ALL_SOURCES[0]: "GitHub",
    _ALL_SOURCES[1]: "fastly.jsdelivr.net",
    _ALL_SOURCES[2]: "cdn.jsdelivr.net",
    _ALL_SOURCES[3]: "gcore.jsdelivr.net",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/plain, */*",
    "Cache-Control": "no-cache",
}

_TIMEOUT = 5

_state = {"last_ok": 0}


def _extract_path(url: str) -> Optional[str]:
    m = _GITHUB_RAW_PATTERN.match(url)
    return m.group(1) if m else None


def _do_request(url: str, proxies: Optional[dict]) -> str:
    resp = requests.get(url, headers=_HEADERS, proxies=proxies, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.text.strip()


def fetch_with_fallback(
    url: str,
    proxy_url: Optional[str] = None,
) -> Optional[str]:
    """Effectue les tentatives en rotation à partir de la dernière source ayant réussi ; les liens non GitHub sont requêtés directement."""
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    path = _extract_path(url)
    if path is None:
        try:
            return _do_request(url, proxies)
        except Exception as e:
            logger.warning("[vérification de version] échec de récupération : %s", e)
            return None

    n = len(_ALL_SOURCES)
    start = _state["last_ok"]

    for offset in range(n):
        idx = (start + offset) % n
        source = _ALL_SOURCES[idx]
        try:
            content = _do_request(source + path, proxies)
            if idx != start:
                label = _SOURCE_LABELS.get(source, source)
                logger.info("[vérification de version] basculement vers : %s", label)
            _state["last_ok"] = idx
            return content
        except Exception:
            label = _SOURCE_LABELS.get(source, source)
            logger.debug("[vérification de version] %s indisponible, tentative de la source suivante", label)

    logger.warning("[vérification de version] toutes les sources sont indisponibles")
    return None
