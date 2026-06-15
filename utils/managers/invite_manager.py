"""
utils/managers/invite_manager.py — Système d'invite tracking.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from sqlalchemy import delete, select

from utils.db.models.invite import (
    DEFAULT_REWARD_THRESHOLD,
    InviteConfig,
    InviteLink,
    InviteStat,
)
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

VALID_TYPES = ("regular", "fake", "bonus", "left")

DEFAULT_CONFIG: dict = {
    "enabled": False,
    "reward_role_id": None,
    "reward_threshold": DEFAULT_REWARD_THRESHOLD,
}

_config_cache: dict[int, tuple[dict, float]] = {}
_lock = asyncio.Lock()


def _default_config() -> dict:
    return DEFAULT_CONFIG.copy()


def _empty_stats() -> dict:
    return {"regular": 0, "fake": 0, "bonus": 0, "left": 0, "total": 0}


# ======================================================
# ===================== CONFIG =========================
# ======================================================

async def load_invite_config(guild_id: int) -> dict:
    """Charge la config invite d'un serveur."""
    now = time.monotonic()
    cached = _config_cache.get(guild_id)
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0].copy()

    async with get_session() as session:
        row = await session.get(InviteConfig, guild_id)
        cfg = row.to_dict() if row is not None else _default_config()

    _config_cache[guild_id] = (cfg, now)
    return cfg.copy()


async def save_invite_config(guild_id: int, partial: dict) -> dict:
    """Sauvegarde la config invite d'un serveur."""
    allowed = set(DEFAULT_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    async with _lock:
        async with get_session() as session:
            row = await session.get(InviteConfig, guild_id)
            if row is None:
                merged = {**_default_config(), **clean}
                row = InviteConfig(guild_id=guild_id, **merged)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()

        _config_cache[guild_id] = (result, time.monotonic())

    return result.copy()


async def reset_invite_config(guild_id: int) -> dict:
    """Remet la config aux valeurs par défaut."""
    return await save_invite_config(guild_id, _default_config())


async def delete_invite_config(guild_id: int) -> bool:
    """Supprime la config d'un serveur."""
    async with _lock:
        async with get_session() as session:
            res = await session.execute(
                delete(InviteConfig).where(InviteConfig.guild_id == guild_id)
            )
            deleted = res.rowcount > 0
        _config_cache.pop(guild_id, None)
    return deleted


async def all_active_configs() -> list[dict]:
    """Configs dont enabled=True, avec guild_id inclus (pour les listeners)."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(InviteConfig).where(InviteConfig.enabled.is_(True))
            )
        ).scalars().all()

    out = []
    for r in rows:
        d = r.to_dict()
        d["guild_id"] = r.guild_id
        out.append(d)
    return out


# ======================================================
# ====================== STATS =========================
# ======================================================

async def get_user_stats(guild_id: int, user_id: int) -> dict:
    """Compteurs d'un membre."""
    async with get_session() as session:
        row = await session.get(InviteStat, (guild_id, user_id))
        return row.to_dict() if row is not None else _empty_stats()


async def _get_or_create_stat(session, guild_id: int, user_id: int) -> InviteStat:
    """Récupère la ligne stat."""
    row = await session.get(InviteStat, (guild_id, user_id))
    if row is None:
        row = InviteStat(guild_id=guild_id, user_id=user_id)
        session.add(row)
        await session.flush()
    return row


async def add_invite(guild_id: int, user_id: int, invite_type: str = "regular", amount: int = 1) -> dict:
    """Ajoute un nombre d'invitation au compteur d'un joueur."""
    if invite_type not in VALID_TYPES:
        raise ValueError(f"Type d'invite invalide : {invite_type!r}")
    if amount <= 0:
        return await get_user_stats(guild_id, user_id)

    async with _lock:
        async with get_session() as session:
            row = await _get_or_create_stat(session, guild_id, user_id)
            current = getattr(row, invite_type)
            setattr(row, invite_type, max(0, current + amount))
            await session.flush()
            result = row.to_dict()
    return result


async def remove_invite(guild_id: int, user_id: int, invite_type: str = "regular", amount: int = 1) -> dict:
    """Retire un nombre d'invitation au compteur d'un joueur."""
    if invite_type not in VALID_TYPES:
        raise ValueError(f"Type d'invite invalide : {invite_type!r}")
    if amount <= 0:
        return await get_user_stats(guild_id, user_id)

    async with _lock:
        async with get_session() as session:
            row = await _get_or_create_stat(session, guild_id, user_id)
            current = getattr(row, invite_type)
            setattr(row, invite_type, max(0, current - amount))
            await session.flush()
            result = row.to_dict()
    return result


async def reset_user_stats(guild_id: int, user_id: int) -> dict:
    """Réinitialise tout les compteurs d'invitation des membres du serveur."""
    async with _lock:
        async with get_session() as session:
            row = await session.get(InviteStat, (guild_id, user_id))
            if row is not None:
                row.regular = row.fake = row.bonus = row.left = 0
                await session.flush()
    return _empty_stats()


async def get_leaderboard(guild_id: int, limit: int = 10, offset: int = 0) -> list[tuple[int, dict]]:
    """Renvoie la classement des membres du serveur, trié par nombre d'invitation total."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(InviteStat).where(InviteStat.guild_id == guild_id)
            )
        ).scalars().all()

    ranked = sorted(rows, key=lambda r: r.total, reverse=True)
    sliced = ranked[offset : offset + limit] if limit else ranked[offset:]
    return [(r.user_id, r.to_dict()) for r in sliced]


async def count_ranked(guild_id: int) -> int:
    """Renvoie le nombre de membre ayant fait une invitation (gestion pagination)."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(InviteStat.user_id).where(InviteStat.guild_id == guild_id)
            )
        ).all()
    return len(rows)


# ======================================================
# ====================== LINKS =========================
# ======================================================

async def record_join(guild_id: int, member_id: int, inviter_id: Optional[int], invite_code: Optional[str], is_fake: bool) -> dict:
    """Gere l'arrivée d'un membre."""
    async with _lock:
        async with get_session() as session:
            link = await session.get(InviteLink, (guild_id, member_id))
            if link is None:
                link = InviteLink(guild_id=guild_id, member_id=member_id)
                session.add(link)
            link.inviter_id = inviter_id
            link.invite_code = invite_code
            link.is_fake = is_fake
            link.counted_left = False

            result = _empty_stats()
            if inviter_id is not None:
                stat = await _get_or_create_stat(session, guild_id, inviter_id)
                if is_fake:
                    stat.fake += 1
                else:
                    stat.regular += 1
                await session.flush()
                result = stat.to_dict()
            else:
                await session.flush()
    return result


async def mark_left(guild_id: int, member_id: int) -> Optional[tuple[int, dict]]:
    """Gère le départ d'un membre."""
    async with _lock:
        async with get_session() as session:
            link = await session.get(InviteLink, (guild_id, member_id))
            if link is None or link.inviter_id is None or link.counted_left:
                return None

            inviter_id = link.inviter_id
            link.counted_left = True

            stat = await _get_or_create_stat(session, guild_id, inviter_id)
            stat.left += 1
            await session.flush()
            result = stat.to_dict()
    return (inviter_id, result)


async def get_link(guild_id: int, member_id: int) -> Optional[dict]:
    """Renvoie le lien d'invitation d'un membre."""
    async with get_session() as session:
        row = await session.get(InviteLink, (guild_id, member_id))
        return row.to_dict() if row is not None else None