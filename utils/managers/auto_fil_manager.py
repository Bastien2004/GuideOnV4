"""
utils/managers/auto_fil_manager.py — Configuration du système "Auto-fil"
(/config auto_fil, Paul, 2026-10-15).

Palier Gold+ : même valeurs et même patron que Join to Create
(utils/managers/join_to_create_manager.py) — LIMITE_DEFAUT=1,
LIMITE_GOLD=3, cache mémoire par guild invalidé à chaque écriture.

La vérification/pose du slowmode (10s si le salon n'en a pas déjà un) est
un effet Discord pur (channel.edit) — elle vit dans la vue
(views/auto_fil/auto_fil_config_view.py), pas ici : ce module ne touche
que la DB, comme tous les autres managers de ce dépôt.
"""
from __future__ import annotations

from sqlalchemy import select

from utils.boutique.gold_manager import is_gold
from utils.db.models.auto_fil import AutoFilConfig
from utils.db.session import get_session

LIMITE_DEFAUT = 1
LIMITE_GOLD = 3

_configs_cache: dict[int, list[dict]] = {}


def _invalidate(guild_id: int) -> None:
    _configs_cache.pop(guild_id, None)


async def list_configs(guild_id: int) -> list[dict]:
    """Tous les salons auto-fil configurés pour ce serveur (0 à 3)."""
    if guild_id in _configs_cache:
        return [row.copy() for row in _configs_cache[guild_id]]

    async with get_session() as session:
        rows = (
            await session.execute(
                select(AutoFilConfig)
                .where(AutoFilConfig.guild_id == guild_id)
                .order_by(AutoFilConfig.id)
            )
        ).scalars().all()
    result = [row.to_dict() for row in rows]

    _configs_cache[guild_id] = result
    return [row.copy() for row in result]


async def is_auto_fil_channel(channel_id: int) -> bool:
    """True si ce salon précis a l'auto-fil actif — interrogé par le
    listener (cogs/events/auto_fil_listener.py) à CHAQUE message d'un
    salon textuel, donc volontairement une requête ciblée (pas
    list_configs) pour rester légère même hors cache."""
    async with get_session() as session:
        row_id = await session.scalar(
            select(AutoFilConfig.id).where(AutoFilConfig.channel_id == channel_id)
        )
    return row_id is not None


def get_limit(guild_id: int) -> int:
    """Nombre maximum de salons auto-fil autorisés pour ce serveur."""
    return LIMITE_GOLD if is_gold(guild_id) else LIMITE_DEFAUT


async def can_add_config(guild_id: int) -> tuple[bool, int, int]:
    """(peut_ajouter, nombre_actuel, limite)."""
    configs = await list_configs(guild_id)
    limite = get_limit(guild_id)
    return len(configs) < limite, len(configs), limite


async def channel_already_used(guild_id: int, channel_id: int) -> bool:
    """True si ce salon est déjà configuré pour ce serveur (évite un doublon
    — la contrainte UNIQUE en DB le garantirait aussi, mais on veut un
    message d'erreur clair plutôt qu'une exception SQL brute)."""
    configs = await list_configs(guild_id)
    return any(c["channel_id"] == channel_id for c in configs)


async def create_config(guild_id: int, channel_id: int) -> dict:
    """Active l'auto-fil sur un nouveau salon."""
    async with get_session() as session:
        row = AutoFilConfig(guild_id=guild_id, channel_id=channel_id)
        session.add(row)
        await session.flush()
        result = row.to_dict()

    _invalidate(guild_id)
    return result


async def delete_config(config_id: int) -> dict | None:
    """Désactive l'auto-fil sur un salon particulier."""
    async with get_session() as session:
        row = await session.get(AutoFilConfig, config_id)
        if row is None:
            return None
        result = row.to_dict()
        await session.delete(row)

    _invalidate(result["guild_id"])
    return result
