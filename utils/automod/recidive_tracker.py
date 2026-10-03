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

# 2026-10-03 (Paul) : fuite mémoire trouvée en audit — une clé n'était
# retirée de _buffer QUE si count_recent() était rappelée sur ce même
# triplet (guild, user, system) et la trouvait vide. Un utilisateur qui ne
# déclenche l'automod qu'UNE fois laisse donc une entrée permanente en
# mémoire pour toujours (count_recent n'est jamais rappelée tant qu'il ne
# récidive pas). Sur un bot présent sur beaucoup de serveurs actifs dans la
# durée, _buffer grossit sans fin. Purge périodique et amortie (pas un
# balayage à chaque appel : juste un passage en plus toutes les
# _PURGE_INTERVAL_SECONDS) qui retire les clés inactives depuis plus de
# _STALE_KEY_CEILING_SECONDS — une marge large et volontairement bien
# au-delà de toute fenêtre de récidive réaliste (documentée ci-dessus comme
# "max 3min"), pour ne jamais purger une clé encore pertinente pour UNE
# guild dont la fenêtre configurée serait inhabituellement longue.
_PURGE_INTERVAL_SECONDS: Final[float] = 300.0
_STALE_KEY_CEILING_SECONDS: Final[float] = 900.0
_last_purge: float = 0.0


def _purge_stale_keys(now: float) -> None:
    """Retire du buffer toute clé dont le timestamp le plus récent dépasse
    _STALE_KEY_CEILING_SECONDS. Amorti par _PURGE_INTERVAL_SECONDS : ne fait
    réellement le balayage complet du dict que de temps en temps, pas à
    chaque infraction."""
    global _last_purge
    if now - _last_purge < _PURGE_INTERVAL_SECONDS:
        return
    _last_purge = now
    stale_keys = [
        key for key, timestamps in _buffer.items()
        if not timestamps or now - timestamps[-1] > _STALE_KEY_CEILING_SECONDS
    ]
    for key in stale_keys:
        _buffer.pop(key, None)


def _prune(timestamps: list[float], now: float, window: float) -> list[float]:
    """Retire les timestamps plus vieux que la fenêtre."""
    cutoff = now - window
    return [ts for ts in timestamps if ts >= cutoff]


def record_infraction(guild_id: int, user_id: int, system_key: str) -> None:
    """Enregistre une infraction avec timestamp courant."""
    key = (guild_id, user_id, system_key)
    now = time.monotonic()
    _purge_stale_keys(now)
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