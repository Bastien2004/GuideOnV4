"""
utils/automod/detectors/nolink.py — Détection de liens dans un message.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_HTTP_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)

_DISCORD_INVITE_RE = re.compile(
    r"\b(?:discord\.gg|discord(?:app)?\.com/invite)/[^\s<>\"]+",
    re.IGNORECASE,
)

_WWW_URL_RE = re.compile(
    r"\bwww\.[^\s<>\"]+\.[a-zA-Z]{2,}(?:/[^\s<>\"]*)?",
    re.IGNORECASE,
)

_PATTERNS: tuple[re.Pattern, ...] = (_HTTP_URL_RE, _DISCORD_INVITE_RE, _WWW_URL_RE)

_MATCH_MAX_LEN = 150
_GIF_DOMAINS: tuple[str, ...] = ("tenor.com", "giphy.com")


def _is_gif_link(url: str) -> bool:
    """True si `url` pointe vers un GIF : domaine Tenor/Giphy connu, ou URL
    se terminant par `.gif` (avant une éventuelle query string/fragment)."""
    lowered = url.lower()
    if lowered.endswith(".gif") or ".gif?" in lowered or ".gif#" in lowered:
        return True
    return any(domain in lowered for domain in _GIF_DOMAINS)


def detect(message_content: str | None, *, bypass_gif: bool = False) -> str | None:
    """
    Retourne le premier lien détecté (tronqué à 150 caractères), ou None.

    `bypass_gif` (option configurable dans /mod automod → No Link) : ignore
    un lien reconnu comme un GIF (Tenor/Giphy/.gif) — utile car le picker
    GIF natif de Discord insère une URL Tenor dans le contenu du message.
    Un AUTRE lien non-GIF présent dans le même message reste détecté
    normalement (on ne fait que sauter les matches identifiés GIF, pas
    tout le pattern).
    """
    if not message_content:
        return None

    for pattern in _PATTERNS:
        for match in pattern.finditer(message_content):
            found = match.group(0)[:_MATCH_MAX_LEN]
            if bypass_gif and _is_gif_link(found):
                log.debug(
                    "[AUTOMOD nolink detect] lien GIF ignoré (bypass_gif actif) match=%r",
                    found,
                )
                continue
            log.debug(
                "[AUTOMOD nolink detect] pattern=%s match=%r",
                pattern.pattern[:30], found,
            )
            return found

    return None