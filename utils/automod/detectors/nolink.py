"""
utils/automod/detectors/nolink.py — Détection de liens dans un message.

Fonction pure (aucune dépendance à discord.py ou à la DB) : prend le contenu
d'un message, retourne le PREMIER lien détecté (tronqué) ou None.

Le filtrage "ce salon est whitelisté donc on n'appelle même pas detect()"
est fait côté listener (cogs/events/mod_automod_listener.py) — ce module ne
connaît ni les salons ni la guild, il ne fait qu'analyser du texte brut.
C'est justement pourquoi cette logique est extraite dans un module dédié :
testable en isolation, comme utils.automod.detectors.banword.

Trois catégories reconnues (cf. spec V4 — "http/https/discord invites/etc") :
  1. URLs avec schéma explicite   : http://... ou https://...
  2. Invites Discord sans schéma  : discord.gg/xxx, discord.com/invite/xxx,
                                     discordapp.com/invite/xxx
  3. URLs "www." sans schéma      : www.exemple.com/...

Volontairement PAS de détection de domaine nu sans "www." ni schéma
(ex: "exemple.com" tout seul, "v1.2.3", "salut.là") : trop de faux positifs
sur du texte normal contenant un point. Si un jour on veut être plus strict,
ajouter une 4e regex avec une whitelist de TLD connus plutôt qu'un `.+`
générique.

Tests (exemples — à coller tels quels dans un fichier pytest si besoin) :

    assert detect("Regarde ça : https://example.com/page") == "https://example.com/page"
    assert detect("Rejoins-nous sur discord.gg/abc123") == "discord.gg/abc123"
    assert detect("Va sur DISCORD.COM/INVITE/xyz") is not None
    assert detect("Va sur www.exemple.fr/page?x=1") is not None
    assert detect("Salut, comment ça va ?") is None
    assert detect("La version 1.2.3 du launcher est sortie") is None
    assert detect("") is None
    assert detect(None) is None  # garde-fou, pas un crash
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

# Ordre volontaire : schéma explicite d'abord (le plus fiable), puis invite
# courte, puis www. — search() s'arrête au premier pattern qui matche, donc
# un "https://discord.gg/x" sera rapporté via _HTTP_URL_RE (pas de double
# comptage possible côté appelant, un seul matched_term par message).
_PATTERNS: tuple[re.Pattern, ...] = (_HTTP_URL_RE, _DISCORD_INVITE_RE, _WWW_URL_RE)

_MATCH_MAX_LEN = 150


def detect(message_content: str | None) -> str | None:
    """Retourne le premier lien détecté (tronqué à 150 caractères), ou None."""
    if not message_content:
        return None

    for pattern in _PATTERNS:
        match = pattern.search(message_content)
        if match:
            found = match.group(0)[:_MATCH_MAX_LEN]
            log.debug(
                "[AUTOMOD nolink detect] pattern=%s match=%r",
                pattern.pattern[:30], found,
            )
            return found

    return None