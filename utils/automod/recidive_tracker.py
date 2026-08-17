"""
utils/automod/recidive_tracker.py — Buffer en mémoire des infractions récentes.

Utilisé par le listener automod pour détecter les récidives : "cet utilisateur
a-t-il déjà déclenché ce même système dans les X dernières secondes ?".

Structure : dict[(guild_id, user_id, system_key), list[timestamp]] — trié
implicitement puisqu'on append toujours à la fin. Purge automatique des
timestamps expirés à chaque insertion et lecture.

Volontairement in-memory (pas de DB) :
  - Volume élevé : chaque message qui déclenche l'automod ajoute une entrée
  - Fenêtre courte (max 3min) : au restart, la fenêtre passée est perdue,
    mais 3min de contexte sans persistance est acceptable
  - Latence critique : lecture <1µs vs round-trip DB à chaque message

Si un jour on veut la persistance (multi-instance du bot par ex), on pourra
remplacer par Redis avec la même interface.
"""
from __future__ import annotations

import time
from typing import Final

# Clé = (guild_id, user_id, system_key), valeur = liste de timestamps monotoniques.
_buffer: dict[tuple[int, int, str], list[float]] = {}

# Cap de sécurité sur le nombre de timestamps par clé (évite l'explosion mémoire
# si un spammer envoie 10000 messages/seconde).
_MAX_PER_KEY: Final[int] = 100


def _prune(timestamps: list[float], now: float, window: float) -> list[float]:
    """Retire les timestamps plus vieux que la fenêtre."""
    cutoff = now - window
    return [ts for ts in timestamps if ts >= cutoff]


def record_infraction(guild_id: int, user_id: int, system_key: str) -> None:
    """Enregistre une infraction avec timestamp courant."""
    key = (guild_id, user_id, system_key)
    now = time.monotonic()
    current = _buffer.get(key, [])
    current.append(now)
    if len(current) > _MAX_PER_KEY:
        current = current[-_MAX_PER_KEY:]
    _buffer[key] = current


def count_recent(
    guild_id: int, user_id: int, system_key: str, *, window_seconds: float,
) -> int:
    """
    Compte les infractions du même (guild, user, system) dans les
    `window_seconds` dernières secondes. Purge au passage les entrées
    expirées de la clé.
    """
    key = (guild_id, user_id, system_key)
    current = _buffer.get(key)
    if not current:
        return 0
    now = time.monotonic()
    pruned = _prune(current, now, window_seconds)
    if pruned:
        _buffer[key] = pruned
    else:
        _buffer.pop(key, None)
    return len(pruned)


def reset_key(guild_id: int, user_id: int, system_key: str) -> None:
    """
    Efface le compteur pour cette clé (utilisé quand un mute a été appliqué,
    pour ne pas re-déclencher un second mute sur le message suivant tant que
    l'utilisateur est encore actif dans la fenêtre).
    """
    _buffer.pop((guild_id, user_id, system_key), None)


def snapshot_size() -> int:
    """Nombre de clés actuellement en buffer (debug/monitoring)."""
    return len(_buffer)