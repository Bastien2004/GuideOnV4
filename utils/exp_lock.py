"""
Verrou par utilisateur pour empêcher le double-gain d'XP en cas de messages rapides.

Pattern : un asyncio.Lock par (guild_id, user_id), créé à la volée.
"""
import asyncio
from collections import defaultdict
from typing import DefaultDict, Tuple


# Clé : (guild_id, user_id) → Lock
_locks: DefaultDict[Tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)


def get_user_lock(guild_id: int, user_id: int) -> asyncio.Lock:
    """Retourne le lock asyncio dédié à ce couple (guild, user)."""
    return _locks[(guild_id, user_id)]
