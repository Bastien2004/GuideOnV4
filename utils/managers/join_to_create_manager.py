"""
utils/managers/join_to_create_manager.py — Configuration et suivi des salons "Join to Create".
"""

from __future__ import annotations

from sqlalchemy import delete, select

from utils.boutique.gold_manager import is_gold
from utils.db.models.join_to_create import JoinToCreateChannel, JoinToCreateConfig
from utils.db.session import get_session

LIMITE_TRIGGERS_DEFAUT = 1
LIMITE_TRIGGERS_GOLD = 3


class JoinToCreateError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


# ============================================================
# ⚙️ Système de salon déclencheurs
# ============================================================

_triggers_cache: dict[int, list[dict]] = {}


def _invalidate(guild_id: int) -> None:
    _triggers_cache.pop(guild_id, None)


async def list_triggers(guild_id: int) -> list[dict]:
    """Tous les déclencheurs configurés pour ce serveur (0 à 3)."""
    if guild_id in _triggers_cache:
        return [row.copy() for row in _triggers_cache[guild_id]]

    async with get_session() as session:
        rows = (
            await session.execute(
                select(JoinToCreateConfig)
                .where(JoinToCreateConfig.guild_id == guild_id)
                .order_by(JoinToCreateConfig.id)
            )
        ).scalars().all()
    result = [row.to_dict() for row in rows]

    _triggers_cache[guild_id] = result
    return [row.copy() for row in result]


async def get_trigger(trigger_id: int) -> dict | None:
    """Un déclencheur précis par son id (pour cibler renommage/suppression)."""
    async with get_session() as session:
        row = await session.get(JoinToCreateConfig, trigger_id)
    return row.to_dict() if row is not None else None


def get_trigger_limit(guild_id: int) -> int:
    """Nombre maximum de salons déclencheurs autorisés pour ce serveur."""
    return LIMITE_TRIGGERS_GOLD if is_gold(guild_id) else LIMITE_TRIGGERS_DEFAUT


async def can_add_trigger(guild_id: int) -> tuple[bool, int, int]:
    """(peut_ajouter, nombre_actuel, limite) — vérifie le QUOTA seul, pas la
    catégorie (cf. category_already_used, vérifiée séparément puisqu'elle a
    un message d'erreur dédié)."""
    triggers = await list_triggers(guild_id)
    limite = get_trigger_limit(guild_id)
    return len(triggers) < limite, len(triggers), limite


async def category_already_used(guild_id: int, category_id: int, *, exclude_trigger_id: int | None = None) -> bool:
    """True si un AUTRE déclencheur de ce serveur pointe déjà vers cette
    catégorie (règle métier Paul 2026-09 : 3 déclencheurs Gold+ = 3
    catégories différentes, jamais deux dans la même)."""
    triggers = await list_triggers(guild_id)
    return any(
        t["category_id"] == category_id and t["id"] != exclude_trigger_id
        for t in triggers
    )


async def create_trigger(guild_id: int, *, trigger_channel_id: int, trigger_channel_name: str, category_id: int) -> dict:
    """Crée un nouveau salon déclencheur."""
    async with get_session() as session:
        row = JoinToCreateConfig(
            guild_id=guild_id,
            trigger_channel_id=trigger_channel_id,
            trigger_channel_name=trigger_channel_name,
            category_id=category_id,
        )
        session.add(row)
        await session.flush()
        result = row.to_dict()

    _invalidate(guild_id)
    return result


async def rename_trigger(trigger_id: int, name: str) -> dict | None:
    """Renomme un déclencheur particulier."""
    async with get_session() as session:
        row = await session.get(JoinToCreateConfig, trigger_id)
        if row is None:
            return None
        row.trigger_channel_name = name
        await session.flush()
        result = row.to_dict()
        guild_id = row.guild_id

    _invalidate(guild_id)
    return result


async def delete_trigger(trigger_id: int) -> dict | None:
    """Supprime un salon déclencheur particulier."""
    async with get_session() as session:
        row = await session.get(JoinToCreateConfig, trigger_id)
        if row is None:
            return None
        result = row.to_dict()
        await session.delete(row)

    _invalidate(result["guild_id"])
    return result


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