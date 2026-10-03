"""
utils/automod/antispam_msg_buffer.py — Buffer en mémoire du système Anti Spam Message.

Détecte le spam par répétition de message identique envoyé par le même
utilisateur, **tous salons confondus** (un copier-coller balancé dans
plusieurs salons est le vecteur de spam le plus courant — compter par salon
raterait ce cas).

Structure : dict[(guild_id, user_id), list[(timestamp, normalized_content)]]
— même rationale que utils.automod.recidive_tracker : in-memory (pas de DB,
lecture <1µs requise à chaque message, fenêtre courte donc perte acceptable
au restart), purge automatique des entrées expirées à chaque appel, cap de
sécurité par clé pour éviter l'explosion mémoire en cas de flood massif.

C'est volontairement un module séparé de recidive_tracker.py : celui-ci
compte les RÉPÉTITIONS DE CONTENU pour la détection elle-même (ce fichier),
tandis que recidive_tracker compte les INFRACTIONS déjà détectées (tous
systèmes confondus) pour décider de l'escalade vers un mute — deux
responsabilités distinctes, deux buffers distincts.
"""
from __future__ import annotations

import time
from typing import Final

_buffer: dict[tuple[int, int], list[tuple[float, str]]] = {}

_MAX_PER_KEY: Final[int] = 50

# 2026-10-03 (Paul) : même fuite mémoire que utils.automod.recidive_tracker
# (même audit, même cause) — une clé (guild_id, user_id) n'est jamais
# retirée tant que register_and_count() n'est pas rappelée sur ce même
# utilisateur après expiration de sa fenêtre. Un utilisateur qui n'envoie
# qu'un seul message pendant que l'anti-spam message est actif laisse une
# entrée permanente. Purge périodique et amortie, même logique que
# recidive_tracker.py.
_PURGE_INTERVAL_SECONDS: Final[float] = 300.0
_STALE_KEY_CEILING_SECONDS: Final[float] = 900.0
_last_purge: float = 0.0


def _purge_stale_keys(now: float) -> None:
    global _last_purge
    if now - _last_purge < _PURGE_INTERVAL_SECONDS:
        return
    _last_purge = now
    stale_keys = [
        key for key, entries in _buffer.items()
        if not entries or now - entries[-1][0] > _STALE_KEY_CEILING_SECONDS
    ]
    for key in stale_keys:
        _buffer.pop(key, None)


def _normalize(content: str) -> str:
    """Normalise le contenu pour comparaison (espaces superflus + casse ignorés)."""
    return " ".join(content.split()).lower()


def _prune(entries: list[tuple[float, str]], now: float, window: float) -> list[tuple[float, str]]:
    cutoff = now - window
    return [(ts, c) for ts, c in entries if ts >= cutoff]


def register_and_count(guild_id: int, user_id: int, content: str, *, window_seconds: float) -> int:
    """
    Enregistre le message courant et retourne le nombre d'occurrences (lui
    inclus) du MÊME contenu normalisé envoyé par cet utilisateur, tous
    salons confondus, dans les `window_seconds` dernières secondes.

    Retourne 0 si `content` est vide après normalisation (rien à comparer —
    évite de compter des messages "vides" côté texte, ex : image seule,
    comme des doublons entre eux).
    """
    normalized = _normalize(content)
    if not normalized:
        return 0

    key = (guild_id, user_id)
    now = time.monotonic()
    _purge_stale_keys(now)
    current = _prune(_buffer.get(key, []), now, window_seconds)

    current.append((now, normalized))
    if len(current) > _MAX_PER_KEY:
        current = current[-_MAX_PER_KEY:]
    _buffer[key] = current

    return sum(1 for _, c in current if c == normalized)


def reset_key(guild_id: int, user_id: int) -> None:
    """Efface le buffer d'un utilisateur (ex : après un mute, pour repartir propre)."""
    _buffer.pop((guild_id, user_id), None)


def snapshot_size() -> int:
    """Nombre de clés actuellement en buffer (debug/monitoring)."""
    return len(_buffer)