"""
utils/managers/mod_channel_lock_exemption_manager.py — CRUD des exemptions de lock.

Pas de cache TTL ici : lu/écrit uniquement au moment d'un /mod lock ou
/mod unlock (jamais sur le chemin d'un message reçu), donc pas besoin
d'optimiser la lecture comme pour les managers automod.
"""
from __future__ import annotations

from sqlalchemy import delete, select

from utils.db.models.mod_channel_lock_exemption import ModChannelLockExemption
from utils.db.session import get_session


async def list_exempt_roles(channel_id: int) -> list[int]:
    """Rôles actuellement exemptés (par /mod lock) sur ce salon."""
    async with get_session() as session:
        rows = (await session.execute(
            select(ModChannelLockExemption.role_id).where(
                ModChannelLockExemption.channel_id == channel_id
            )
        )).scalars().all()
    return list(rows)


async def record_exemption(guild_id: int, channel_id: int, role_id: int) -> None:
    """Enregistre qu'un overwrite d'exemption a été posé par /mod lock. Idempotent."""
    async with get_session() as session:
        existing = await session.scalar(
            select(ModChannelLockExemption.id).where(
                ModChannelLockExemption.channel_id == channel_id,
                ModChannelLockExemption.role_id == role_id,
            )
        )
        if existing is not None:
            return
        session.add(ModChannelLockExemption(
            guild_id=guild_id, channel_id=channel_id, role_id=role_id,
        ))


async def clear_exemptions(channel_id: int) -> list[int]:
    """
    Supprime toutes les exemptions enregistrées pour ce salon et retourne
    les role_id concernés (à /mod unlock de retirer l'overwrite Discord
    correspondant pour chacun).
    """
    role_ids = await list_exempt_roles(channel_id)
    if not role_ids:
        return []
    async with get_session() as session:
        await session.execute(
            delete(ModChannelLockExemption).where(
                ModChannelLockExemption.channel_id == channel_id
            )
        )
    return role_ids