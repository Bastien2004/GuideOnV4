"""
utils/automod/detectors/nolink.py — Détection de liens dans un message.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

_HTTP_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)

_DISCORD_INVITE_RE = re.compile(r"\b(?:discord\.gg|discord(?:app)?\.com/invite)/[^\s<>\"]+", re.IGNORECASE)

_WWW_URL_RE = re.compile(r"\bwww\.[^\s<>\"]+\.[a-zA-Z]{2,}(?:/[^\s<>\"]*)?", re.IGNORECASE)

_PATTERNS: tuple[re.Pattern, ...] = (_HTTP_URL_RE, _DISCORD_INVITE_RE, _WWW_URL_RE)

_MATCH_MAX_LEN = 150

_GIF_DOMAINS: tuple[str, ...] = ("tenor.com", "giphy.com", "klipy.com")

_GIF_WORD_RE = re.compile(r"\bgifs?\b", re.IGNORECASE)


# ============================================================
# 🛠️ Fonctions utilitaires
# ============================================================

def _is_gif_link(url: str) -> bool:
    """Vérifie qu'un lien est un GIF."""
    lowered = url.lower()
    if lowered.endswith(".gif") or ".gif?" in lowered or ".gif#" in lowered:
        return True
    if any(domain in lowered for domain in _GIF_DOMAINS):
        return True
    return bool(_GIF_WORD_RE.search(url))


def detect(message_content: str | None, *, bypass_gif: bool = False) -> str | None:
    """Ignore les gifs si bypass activé."""
    if not message_content:
        return None

    for pattern in _PATTERNS:
        for match in pattern.finditer(message_content):
            found = match.group(0)[:_MATCH_MAX_LEN]
            if bypass_gif and _is_gif_link(found):
                log.debug("[AUTOMOD NOLINK] Lien GIF ignoré (bypass_gif actif) match=%r", found)
                continue

            log.debug("[AUTOMOD NOLINK] pattern=%s match=%r", pattern.pattern[:30], found)
            return found
    return None