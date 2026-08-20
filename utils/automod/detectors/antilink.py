"""
utils/automod/detectors/antilink.py — Détection de fichiers à extension bloquée.

Fonction pure (aucune dépendance à discord.py ou à la DB) : scanne d'abord
les noms de pièces jointes (vecteur principal — un exécutable envoyé en
pièce jointe), puis les tokens du texte du message (vecteur secondaire — un
lien direct vers un fichier, ex "regarde ce fichier http://host/virus.exe").
Retourne le PREMIER nom/texte matché (tronqué), ou None.

Le matching se fait sur la fin RÉELLE du token (après avoir retiré query
string / fragment / ponctuation de fin) — pas un simple ".exe in token" —
pour éviter les faux positifs du type "fichier.exe.txt" (la vraie extension
finale est .txt, donc PAS bloqué) tout en détectant "fichier.txt.exe" (la
vraie extension finale est .exe, donc bloqué).

`blocked_extensions` doit déjà être normalisé (minuscule, préfixé d'un ".")
— c'est la responsabilité de mod_automod_antilink_manager (_normalize), ce
détecteur ne fait aucune hypothèse dessus au-delà d'un endswith().

Tests (exemples — à coller tels quels dans un fichier pytest si besoin) :

    ext = [".exe", ".zip", ".rar", ".bat", ".cmd", ".js", ".vbs", ".scr", ".msi"]

    assert detect("regarde ce fichier virus.exe", [], ext) == "virus.exe"
    assert detect("http://host.com/dl/setup.exe?ref=1", [], ext) == "http://host.com/dl/setup.exe"
    assert detect("télécharge (setup.exe)", [], ext) == "setup.exe"
    assert detect("archive.rar.txt", [], ext) is None            # vraie ext = .txt
    assert detect("note.txt.exe", [], ext) == "note.txt.exe"     # vraie ext = .exe
    assert detect("mon-fichier.exe.txt", [], ext) is None        # vraie ext = .txt
    assert detect("Salut, comment ça va ?", [], ext) is None
    assert detect("", [], ext) is None
    assert detect(None, [], ext) is None
    assert detect(None, ["payload.exe"], ext) == "payload.exe"
    assert detect("photo de vacances", ["photo.png"], ext) is None
    assert detect("", [], []) is None                            # aucune extension configurée
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_MATCH_MAX_LEN = 150
_TRAILING_PUNCT = ".,;:!?)]}\"'>"


def _strip_query_fragment(token: str) -> str:
    """Retire query string (?...) et fragment (#...) d'un token type URL."""
    for sep in ("?", "#"):
        idx = token.find(sep)
        if idx != -1:
            token = token[:idx]
    return token


def _strip_trailing_punct(token: str) -> str:
    return token.rstrip(_TRAILING_PUNCT)


def _matches_blocked_extension(token: str, blocked_extensions: list[str]) -> bool:
    lowered = token.lower()
    return any(lowered.endswith(ext) for ext in blocked_extensions if ext)


def detect(
    message_content: str | None,
    attachment_filenames: list[str] | None,
    blocked_extensions: list[str],
) -> str | None:
    """
    Retourne le premier nom de fichier / lien matchant une extension bloquée
    (tronqué à 150 caractères), ou None. `blocked_extensions` vide → toujours
    None (rien à détecter, évite un scan inutile).
    """
    if not blocked_extensions:
        return None

    # 1. Pièces jointes — vecteur principal, vérifié en premier.
    for filename in attachment_filenames or []:
        if not filename:
            continue
        cleaned = _strip_trailing_punct(filename.strip())
        if cleaned and _matches_blocked_extension(cleaned, blocked_extensions):
            log.debug("[AUTOMOD antilink detect] attachment=%r", cleaned)
            return cleaned[:_MATCH_MAX_LEN]

    # 2. Contenu texte — tokens séparés par espace (liens, noms en clair).
    if message_content:
        for raw_token in message_content.split():
            token = _strip_trailing_punct(_strip_query_fragment(raw_token))
            if token and _matches_blocked_extension(token, blocked_extensions):
                log.debug("[AUTOMOD antilink detect] token=%r", token)
                return token[:_MATCH_MAX_LEN]

    return None