"""
utils/managers/giveaway_manager.py — Système de giveaway.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select

from utils.db.models.giveaway import (
    GIVEAWAY_ID_LENGTH,
    Giveaway,
    GiveawayBlacklist,
    GiveawayParticipant,
)

from utils.db.session import get_session

log = logging.getLogger(__name__)

_lock = asyncio.Lock()

ALLOWED_UPDATE_FIELDS = {
    "channel_id", "message_id", "prize", "winners_count", "end_time",
    "ended", "winners", "requirements",
}

ALLOWED_REQUIREMENT_KEYS = {
    "role_id",            # rôle requis
    "min_invites",        # invitations minimum
    "min_server_age_days",  # ancienneté serveur en jours
    "forbidden_role_id",  # rôle interdit
}


# ======================================================
# ============== HELPERS / INTERNES ===============
# ======================================================

def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise une datetime."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _giveaway_to_dict(g: Giveaway) -> dict:
    """Convertit un objet en dict."""
    d = g.to_dict()
    d["end_time"] = _ensure_aware(d["end_time"])
    return d


def _blacklist_to_dict(bl: GiveawayBlacklist) -> dict:
    """Convertit un objet en dict."""
    d = bl.to_dict()
    d["expires_at"] = _ensure_aware(d["expires_at"])
    d["created_at"] = _ensure_aware(d["created_at"])
    return d


def _sanitize_requirements(req: Optional[dict]) -> dict:
    """Filtre les clés de requirements."""
    if not req:
        return {}
    return {k: v for k, v in req.items() if k in ALLOWED_REQUIREMENT_KEYS}


# ======================================================
# =================== GIVEAWAYS ========================
# ======================================================

async def _generate_unique_id(session) -> str:
    """Génère ID de giveaway unique."""
    for _ in range(10):
        candidate = secrets.token_hex(GIVEAWAY_ID_LENGTH // 2).upper()
        existing = await session.get(Giveaway, candidate)
        if existing is None:
            return candidate

    raise RuntimeError("Impossible de générer un giveaway_id unique")


async def create_giveaway(*, guild_id: int, channel_id: int, host_id: int, prize: str, winners_count: int, duration_seconds: int, requirements: Optional[dict] = None) -> str:
    """Crée un giveaway."""

    if winners_count < 1:
        raise ValueError("winners_count doit être >= 1")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds doit être > 0")
    if not prize or not prize.strip():
        raise ValueError("prize ne peut pas être vide")

    end_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    clean_req = _sanitize_requirements(requirements)

    async with _lock:
        async with get_session() as session:
            gid = await _generate_unique_id(session)
            g = Giveaway(
                id=gid,
                guild_id=guild_id,
                channel_id=channel_id,
                message_id=None,
                host_id=host_id,
                prize=prize.strip(),
                winners_count=winners_count,
                end_time=end_time,
                ended=False,
                winners=[],
                requirements=clean_req,
            )
            session.add(g)
            await session.flush()
    return gid


async def get_giveaway(giveaway_id: str) -> Optional[dict]:
    """Récupère un giveaway par son ID."""
    async with get_session() as session:
        g = await session.get(Giveaway, giveaway_id)
        return _giveaway_to_dict(g) if g is not None else None


async def get_giveaway_by_message(guild_id: int, message_id: int) -> Optional[dict]:
    """Récupère un giveaway à partir du message ID."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(Giveaway).where(
                    Giveaway.guild_id == guild_id,
                    Giveaway.message_id == message_id,
                )
            )
        ).scalars().all()
    if not rows:
        return None
    return _giveaway_to_dict(rows[0])


async def update_giveaway(giveaway_id: str, **updates) -> Optional[dict]:
    """Mise à jour d'un giveaway."""

    clean = {k: v for k, v in updates.items() if k in ALLOWED_UPDATE_FIELDS}
    if "requirements" in clean:
        clean["requirements"] = _sanitize_requirements(clean["requirements"])
    if not clean:
        return await get_giveaway(giveaway_id)

    async with _lock:
        async with get_session() as session:
            g = await session.get(Giveaway, giveaway_id)
            if g is None:
                return None
            for k, v in clean.items():
                setattr(g, k, v)
            await session.flush()
            return _giveaway_to_dict(g)


async def set_message_id(giveaway_id: str, message_id: int) -> bool:
    """Enregistre le message_id après envoi du panel."""
    result = await update_giveaway(giveaway_id, message_id=message_id)
    return result is not None


async def end_giveaway(giveaway_id: str, winners: list[int]) -> Optional[dict]:
    """Marque le giveaway comme terminé avec sa liste de gagnants."""
    return await update_giveaway(giveaway_id, ended=True, winners=list(winners))


async def delete_giveaway(giveaway_id: str) -> bool:
    """Supprime un giveaway."""

    async with _lock:
        async with get_session() as session:
            res = await session.execute(
                delete(Giveaway).where(Giveaway.id == giveaway_id)
            )
            deleted = res.rowcount > 0
            if deleted:
                await session.execute(
                    delete(GiveawayParticipant).where(
                        GiveawayParticipant.giveaway_id == giveaway_id
                    )
                )
    return deleted


async def get_active_giveaways(guild_id: int) -> list[dict]:
    """Récupère les giveaways en cours."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(Giveaway).where(
                    Giveaway.guild_id == guild_id,
                    Giveaway.ended.is_(False),
                    Giveaway.message_id.isnot(None),
                ).order_by(Giveaway.end_time.asc())
            )
        ).scalars().all()
    return [_giveaway_to_dict(g) for g in rows]


async def get_ended_giveaways(guild_id: int, limit: int = 10) -> list[dict]:
    """Récupère les giveaways terminés."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(Giveaway).where(
                    Giveaway.guild_id == guild_id,
                    Giveaway.ended.is_(True),
                ).order_by(Giveaway.end_time.desc()).limit(limit)
            )
        ).scalars().all()
    return [_giveaway_to_dict(g) for g in rows]


async def get_all_expired_giveaways() -> list[dict]:
    """Récupère tous les giveaways expirés."""

    now = datetime.now(timezone.utc)
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Giveaway).where(
                    Giveaway.ended.is_(False),
                    Giveaway.message_id.isnot(None),
                    Giveaway.end_time <= now,
                )
            )
        ).scalars().all()
    return [_giveaway_to_dict(g) for g in rows]


# ======================================================
# ================== PARTICIPANTS ======================
# ======================================================

async def add_participant(giveaway_id: str, user_id: int) -> bool:
    """Ajoute un participant."""
    async with _lock:
        async with get_session() as session:
            existing = await session.get(GiveawayParticipant, (giveaway_id, user_id))
            if existing is not None:
                return False
            session.add(GiveawayParticipant(giveaway_id=giveaway_id, user_id=user_id))
            await session.flush()
    return True


async def remove_participant(giveaway_id: str, user_id: int) -> bool:
    """Retire un participant."""
    async with _lock:
        async with get_session() as session:
            res = await session.execute(
                delete(GiveawayParticipant).where(
                    GiveawayParticipant.giveaway_id == giveaway_id,
                    GiveawayParticipant.user_id == user_id,
                )
            )
            return res.rowcount > 0


async def get_participants(giveaway_id: str) -> list[int]:
    """Liste des user_ids participants, dans l'ordre d'arrivée."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(GiveawayParticipant.user_id).where(
                    GiveawayParticipant.giveaway_id == giveaway_id
                ).order_by(GiveawayParticipant.created_at.asc())
            )
        ).all()
    return [r[0] for r in rows]


async def count_participants(giveaway_id: str) -> int:
    """Comptage rapide via COUNT."""
    async with get_session() as session:
        result = await session.execute(
            select(func.count()).select_from(GiveawayParticipant).where(
                GiveawayParticipant.giveaway_id == giveaway_id
            )
        )
        return result.scalar_one()


async def is_participant(giveaway_id: str, user_id: int) -> bool:
    """Vérifie si un user participe."""
    async with get_session() as session:
        row = await session.get(GiveawayParticipant, (giveaway_id, user_id))
        return row is not None


# ======================================================
# ==================== BLACKLIST =======================
# ======================================================

async def add_to_blacklist(guild_id: int, user_id: int, added_by: int, reason: Optional[str] = None, expires_at: Optional[datetime] = None,) -> dict:
    """Gestion du système de blacklist giveaway."""

    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if reason is not None:
        reason = reason.strip() or None

    async with _lock:
        async with get_session() as session:
            row = await session.get(GiveawayBlacklist, (guild_id, user_id))
            if row is None:
                row = GiveawayBlacklist(
                    guild_id=guild_id,
                    user_id=user_id,
                    added_by=added_by,
                    reason=reason,
                    expires_at=expires_at,
                )
                session.add(row)
            else:
                row.added_by = added_by
                row.reason = reason
                row.expires_at = expires_at
            await session.flush()
            return _blacklist_to_dict(row)


async def remove_from_blacklist(guild_id: int, user_id: int) -> bool:
    """Retire un utilisateur de la blacklist."""
    async with _lock:
        async with get_session() as session:
            res = await session.execute(
                delete(GiveawayBlacklist).where(
                    GiveawayBlacklist.guild_id == guild_id,
                    GiveawayBlacklist.user_id == user_id,
                )
            )
            return res.rowcount > 0


async def is_blacklisted(guild_id: int, user_id: int) -> bool:
    """Retourne True si l'utilisateur est blacklist"""
    async with get_session() as session:
        row = await session.get(GiveawayBlacklist, (guild_id, user_id))
        if row is None:
            return False
        exp = _ensure_aware(row.expires_at)
        if exp is None:
            return True
        return datetime.now(timezone.utc) < exp


async def get_blacklist(guild_id: int, include_expired: bool = False) -> list[dict]:
    """Renvoie la liste des utilisateurs blacklisté sur un serveur."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(GiveawayBlacklist).where(
                    GiveawayBlacklist.guild_id == guild_id
                ).order_by(GiveawayBlacklist.created_at.desc())
            )
        ).scalars().all()

    out: list[dict] = []
    now = datetime.now(timezone.utc)
    for r in rows:
        d = _blacklist_to_dict(r)
        if not include_expired:
            exp = d["expires_at"]
            if exp is not None and exp <= now:
                continue
        out.append(d)
    return out


async def count_blacklist(guild_id: int, include_expired: bool = False) -> int:
    """Nombre d'utilisateur blacklist."""
    rows = await get_blacklist(guild_id, include_expired=include_expired)
    return len(rows)


async def purge_expired_blacklist(guild_id: Optional[int] = None) -> int:
    """Nettoie les données de blacklist expirées."""
    
    now = datetime.now(timezone.utc)
    async with _lock:
        async with get_session() as session:
            stmt = delete(GiveawayBlacklist).where(
                GiveawayBlacklist.expires_at.isnot(None),
                GiveawayBlacklist.expires_at <= now,
            )
            if guild_id is not None:
                stmt = stmt.where(GiveawayBlacklist.guild_id == guild_id)
            res = await session.execute(stmt)
            return res.rowcount