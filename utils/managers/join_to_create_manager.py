"""
utils/managers/join_to_create_manager.py — Config + suivi des salons "Join to Create".

Deux responsabilités distinctes :
  - Config par serveur (salon déclencheur + catégorie destination), cache
    simple par guild_id — même pattern que mod_log_manager/mod_sanction_manager.
  - Traçabilité des salons générés (join_to_create_channels) : permet au
    listener de ne supprimer QUE les salons qu'il a lui-même créés quand ils
    se vident, jamais un salon posé manuellement par un admin dans la même
    catégorie.
"""
from __future__ import annotations

from sqlalchemy import delete, select

from utils.db.models.join_to_create import JoinToCreateChannel, JoinToCreateConfig
from utils.db.session import get_session


class JoinToCreateError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


# ============================================================
# ⚙️ Config (par serveur, cache simple invalidé à l'écriture)
# ============================================================

DEFAULT_CONFIG: dict = {
    "trigger_channel_id": None, "trigger_channel_name": None, "category_id": None,
}

_config_cache: dict[int, dict] = {}


async def load_config(guild_id: int) -> dict:
    if guild_id in _config_cache:
        return _config_cache[guild_id].copy()

    async with get_session() as session:
        row = await session.get(JoinToCreateConfig, guild_id)
        cfg = row.to_dict() if row is not None else {**DEFAULT_CONFIG, "guild_id": guild_id}

    _config_cache[guild_id] = cfg
    return cfg.copy()


async def save_config(guild_id: int, partial: dict) -> dict:
    allowed = set(DEFAULT_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    async with get_session() as session:
        row = await session.get(JoinToCreateConfig, guild_id)
        if row is None:
            merged = {**DEFAULT_CONFIG, **clean}
            row = JoinToCreateConfig(guild_id=guild_id, **merged)
            session.add(row)
        else:
            for key, value in clean.items():
                setattr(row, key, value)
        await session.flush()
        result = row.to_dict()

    _config_cache[guild_id] = result
    return result.copy()


async def set_category(guild_id: int, category_id: int) -> dict:
    return await save_config(guild_id, {"category_id": category_id})


async def set_trigger_channel(guild_id: int, channel_id: int, name: str) -> dict:
    return await save_config(guild_id, {"trigger_channel_id": channel_id, "trigger_channel_name": name})


async def clear_trigger_channel(guild_id: int) -> dict:
    return await save_config(guild_id, {"trigger_channel_id": None, "trigger_channel_name": None})


# ============================================================
# 🗂️ Suivi des salons générés
# ============================================================

async def register_channel(guild_id: int, channel_id: int, owner_id: int) -> None:
    """Enregistre un salon vocal généré par le système (traçabilité pour la suppression auto)."""
    async with get_session() as session:
        session.add(JoinToCreateChannel(guild_id=guild_id, channel_id=channel_id, owner_id=owner_id))


async def is_generated_channel(channel_id: int) -> bool:
    """True si ce salon a été créé par le système Join to Create (et pas manuellement)."""
    async with get_session() as session:
        row_id = await session.scalar(
            select(JoinToCreateChannel.id).where(JoinToCreateChannel.channel_id == channel_id)
        )
    return row_id is not None


async def unregister_channel(channel_id: int) -> None:
    """Retire le suivi d'un salon généré (après suppression, ou si le déplacement a échoué)."""
    async with get_session() as session:
        await session.execute(
            delete(JoinToCreateChannel).where(JoinToCreateChannel.channel_id == channel_id)
        )