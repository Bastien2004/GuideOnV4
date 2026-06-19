"""
utils/managers/alpha_staff_manager.py — Gestion des données du staff Alpha.

API publique :
    await list_staff()                                          -> list[dict]
    await get_staff_member(discord_id)                          -> dict | None
    await upsert_staff_member(discord_id, pseudo, grade, ...)   -> bool (True si créé)
    await add_staff_member(discord_id, pseudo, grade, ...)      -> bool (False si déjà présent)
    await remove_staff_member(discord_id)                       -> bool (False si absent)
    await update_staff_member(discord_id, **fields)             -> bool (False si absent)
    await staff_exists(discord_id)                              -> bool
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.alpha_staff import AlphaStaffMember, GRADES_ORDER
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_UNSET = object()

_cache: list[dict] | None = None
_cache_at: float = 0.0
_lock = asyncio.Lock()


# ════════════════════════════════════════════════════════════
# 🔄 Cache interne
# ════════════════════════════════════════════════════════════

def _is_valid() -> bool:
    return _cache is not None and (time.monotonic() - _cache_at) < CACHE_TTL_SECONDS


def _invalidate() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


def _sort(members: list[dict]) -> list[dict]:
    def key(m: dict) -> tuple:
        grade = m["grade"]
        if grade is None:
            return (len(GRADES_ORDER), m["pseudo_jeu"].lower())
        
        try:
            return (GRADES_ORDER.index(grade), m["pseudo_jeu"].lower())
        
        except ValueError:
            return (len(GRADES_ORDER) + 1, m["pseudo_jeu"].lower())
        
    return sorted(members, key=key)


async def _load_from_db() -> list[dict]:
    async with get_session() as session:
        rows = (await session.execute(select(AlphaStaffMember))).scalars().all()
    return _sort([r.to_dict() for r in rows])


async def _get_cache() -> list[dict]:
    global _cache, _cache_at
    if _is_valid():
        return list(_cache)
    async with _lock:
        if _is_valid():
            return list(_cache)
        _cache = await _load_from_db()
        _cache_at = time.monotonic()
    return list(_cache)


# ════════════════════════════════════════════════════════════
# 📖 Lectures
# ════════════════════════════════════════════════════════════

async def list_staff() -> list[dict]:
    return await _get_cache()


async def get_staff_member(discord_id: int) -> dict | None:
    members = await _get_cache()
    for m in members:
        if m["discord_id"] == discord_id:
            return dict(m)
    return None


async def staff_exists(discord_id: int) -> bool:
    return await get_staff_member(discord_id) is not None


# ════════════════════════════════════════════════════════════
# ✍️ Écritures
# ════════════════════════════════════════════════════════════

async def upsert_staff_member(discord_id: int, pseudo_jeu: str, grade: str | None, skin_head_emoji: str = "", is_journaliste: bool | None = None, is_affilie: bool | None = None, is_builder: bool | None = None, pseudo_jeu_builder: str | None = _UNSET) -> bool:
    """Ajoute ou met à jour un membre."""

    async with _lock:
        async with get_session() as session:
            row = await session.scalar(
                select(AlphaStaffMember).where(AlphaStaffMember.discord_id == discord_id)
            )
            if row is None:
                session.add(AlphaStaffMember(
                    discord_id=discord_id,
                    pseudo_jeu=pseudo_jeu,
                    grade=grade,
                    skin_head_emoji=skin_head_emoji,
                    is_journaliste=is_journaliste if is_journaliste is not None else False,
                    is_affilie=is_affilie if is_affilie is not None else False,
                    is_builder=is_builder if is_builder is not None else False,
                    pseudo_jeu_builder=None if pseudo_jeu_builder is _UNSET else pseudo_jeu_builder,
                ))
                created = True

            else:
                row.pseudo_jeu = pseudo_jeu
                row.grade = grade
                if skin_head_emoji:
                    row.skin_head_emoji = skin_head_emoji
                if is_journaliste is not None:
                    row.is_journaliste = is_journaliste
                if is_affilie is not None:
                    row.is_affilie = is_affilie
                if is_builder is not None:
                    row.is_builder = is_builder
                if pseudo_jeu_builder is not _UNSET:
                    row.pseudo_jeu_builder = pseudo_jeu_builder
                created = False
        _invalidate()

    log.info("[STAFFLIST ALPHA] Staff Alpha %s : %s (%s) — %s", "ajouté" if created else "mis à jour", pseudo_jeu, discord_id, grade)

    return created


async def add_staff_member(discord_id: int, pseudo_jeu: str, grade: str | None, skin_head_emoji: str = "", is_journaliste: bool = False, is_affilie: bool = False, is_builder: bool = False, pseudo_jeu_builder: str | None = None) -> bool:
    """Ajoute un membre. Retourne False si discord_id est déjà présent."""

    async with _lock:
        async with get_session() as session:
            exists = await session.scalar(
                select(AlphaStaffMember.id).where(AlphaStaffMember.discord_id == discord_id)
            )

            if exists is not None:
                return False
            
            session.add(AlphaStaffMember(
                discord_id=discord_id,
                pseudo_jeu=pseudo_jeu,
                grade=grade,
                skin_head_emoji=skin_head_emoji,
                is_journaliste=is_journaliste,
                is_affilie=is_affilie,
                is_builder=is_builder,
                pseudo_jeu_builder=pseudo_jeu_builder,
            ))
        _invalidate()
    log.info("[STAFFLIST ALPHA] Staff Alpha ajouté : %s (%s) — %s", pseudo_jeu, discord_id, grade)
    return True


async def remove_staff_member(discord_id: int) -> bool:
    """Retire un membre. Retourne False s'il est absent."""
    async with _lock:
        async with get_session() as session:
            result = await session.execute(
                delete(AlphaStaffMember).where(AlphaStaffMember.discord_id == discord_id)
            )
            deleted = result.rowcount > 0
        if deleted:
            _invalidate()
    if deleted:
        log.info("[STAFFLIST ALPHA] Staff Alpha retiré : discord_id=%s", discord_id)
    return deleted


async def update_staff_member(discord_id: int, **fields: object) -> bool:
    """Met à jour les champs d'un membre. Champs acceptés : pseudo_jeu, grade, skin_head_emoji, is_journaliste, is_affilie, is_builder, pseudo_jeu_builder."""

    allowed = {
        "pseudo_jeu", "grade", "skin_head_emoji",
        "is_journaliste", "is_affilie", "is_builder", "pseudo_jeu_builder",
    }

    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return False

    async with _lock:
        async with get_session() as session:
            row = await session.scalar(
                select(AlphaStaffMember).where(AlphaStaffMember.discord_id == discord_id)
            )
            if row is None:
                return False
            for k, v in clean.items():
                setattr(row, k, v)
        _invalidate()

    log.info("[STAFFLIST ALPHA] Staff Alpha modifié : discord_id=%s champs=%s", discord_id, list(clean))
    return True