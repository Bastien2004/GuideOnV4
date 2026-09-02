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

Bypass GIF (bypass_gif=True — cf. mod_automod_nolink_manager, option
configurable via /mod automod) : le picker GIF natif de Discord insère une
URL Tenor dans le contenu du message ("https://tenor.com/view/..."), que ce
détecteur confondait avec un lien classique et faisait donc supprimer.
Quand l'option est activée, un lien reconnu comme un GIF est ignoré — mais
un AUTRE lien non-GIF dans le même message reste détecté normalement.

Un lien est reconnu comme GIF via TROIS vérifications cumulées (pas juste
une liste de domaines Tenor/Giphy — trop fragile, cf. le lien Klipy remonté
par Paul le 2026-09-02 qui échappait à la 1ère version basée uniquement sur
domaine) :
  1. Extension explicite ".gif"
  2. Domaine connu (tenor.com, giphy.com, klipy.com, …)
  3. Mot "gif"/"gifs" isolé (bordure de mot) n'importe où dans l'URL — attrape
     les sites de GIF non listés explicitement (ex: klipy.com/gifs/cat-203,
     tenor.com/view/cat-gif-123) sans faux positif sur "giphy", "gifted",
     "legifrance", etc. (aucun de ces mots ne contient "gif" en tant que
     mot isolé).

    assert detect("gif : https://tenor.com/view/cat-123", bypass_gif=True) is None
    assert detect("gif : https://tenor.com/view/cat-123", bypass_gif=False) is not None
    assert detect("https://media.tenor.com/abc/cat.gif", bypass_gif=True) is None
    assert detect("https://klipy.com/gifs/cat-203", bypass_gif=True) is None
    assert detect("https://example.com/x.gif et https://evil.com", bypass_gif=True) == "https://evil.com"
    assert detect("https://example.com/gift-card", bypass_gif=True) is not None  # pas un GIF
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
# courte, puis www. — on s'arrête au premier match retenu, donc un
# "https://discord.gg/x" sera rapporté via _HTTP_URL_RE (pas de double
# comptage possible côté appelant, un seul matched_term par message).
_PATTERNS: tuple[re.Pattern, ...] = (_HTTP_URL_RE, _DISCORD_INVITE_RE, _WWW_URL_RE)

_MATCH_MAX_LEN = 150

# Domaines des GIF picker/partage les plus courants — Discord utilise Tenor
# nativement, Giphy et Klipy sont les alternatives les plus répandues côté
# navigateur/mobile. Complété par _GIF_WORD_RE ci-dessous : cette liste
# n'a PAS besoin d'être exhaustive (Paul, 2026-09-02).
_GIF_DOMAINS: tuple[str, ...] = ("tenor.com", "giphy.com", "klipy.com")

# Filet de sécurité pour tout site de GIF non listé ci-dessus (ex: Klipy,
# avant son ajout à la liste) : "gif"/"gifs" comme MOT isolé (bordure de
# mot des deux côtés) dans l'URL — attrape "klipy.com/gifs/cat-203" ou
# "tenor.com/view/cat-gif-123" sans faux positif sur "giphy", "gifted",
# "legifrance", etc. (ces mots ne contiennent pas "gif" en tant que mot
# isolé, un tiret ou un slash comptant comme bordure de mot).
_GIF_WORD_RE = re.compile(r"\bgifs?\b", re.IGNORECASE)


def _is_gif_link(url: str) -> bool:
    """True si `url` pointe vers un GIF (extension .gif, domaine connu, ou
    mot "gif"/"gifs" isolé dans l'URL — cf. docstring du module)."""
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