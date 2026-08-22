"""
utils/managers/ng_staff_manager.py — Gestion des données du staff, multi-
serveurs (refonte multi-serveurs, phase 6, ex-alpha_staff_manager.py).

⚠️ Ce manager gère la table `ng_staff`, créée EN PARALLÈLE de `alpha_staff`
(voir migrations/versions/*_ng_staff.py et utils.db.models.ng_staff pour le
détail). `alpha_staff` reste la source de vérité utilisée par les commandes
existantes (rank.py, derank.py, stafflist.py, etc.) jusqu'à leur migration
en phase 7. Ne PAS câbler ce manager dans une commande de prod avant cette
phase — pour l'instant il n'est utilisé qu'en dev/tests et par
`resync_server_from_alpha_staff` (backfill à la demande).

API publique :
    await list_staff(server)                                          -> list[dict]
    await get_staff_member(server, discord_id)                        -> dict | None
    await upsert_staff_member(server, discord_id, pseudo, grade, ...) -> bool (True si créé)
    await add_staff_member(server, discord_id, pseudo, grade, ...)    -> bool (False si déjà présent)
    await remove_staff_member(server, discord_id)                     -> bool (False si absent)
    await update_staff_member(server, discord_id, **fields)           -> bool (False si absent)
    await staff_exists(server, discord_id)                            -> bool
    await resync_server_from_alpha_staff(server="alpha")              -> dict (compteurs)
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.staff_grades import GRADES_ORDER
from utils.db.models.ng_staff import NGStaffMember
from utils.db.session import get_session
from utils.managers.ng_statut_manager import list_member_statuts_bulk

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_UNSET = object()

# Cache par serveur : {server: (members, loaded_at_monotonic)}
_cache: dict[str, tuple[list[dict], float]] = {}
_lock = asyncio.Lock()


# ════════════════════════════════════════════════════════════
# 🔄 Cache interne
# ════════════════════════════════════════════════════════════

def _is_valid(server: str) -> bool:
    entry = _cache.get(server)
    return entry is not None and (time.monotonic() - entry[1]) < CACHE_TTL_SECONDS


def _invalidate(server: str) -> None:
    _cache.pop(server, None)


def invalidate_cache(server: str) -> None:
    """Invalidation publique — utilisée par ng_statut_manager quand un statut
    est accordé/retiré/modifié/supprimé, puisque les dicts membres mis en
    cache ici embarquent une copie de "statuts" (voir _load_from_db) qui
    doit être rafraîchie, pas seulement le cache des définitions de
    ng_statut_manager (Paul, 2026-08-22)."""
    _invalidate(server)


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


async def _load_from_db(server: str) -> list[dict]:
    async with get_session() as session:
        rows = (
            await session.execute(select(NGStaffMember).where(NGStaffMember.server == server))
        ).scalars().all()
    members = [r.to_dict() for r in rows]

    # 🎖️ Enrichissement "statuts" (système dynamique par serveur, remplace
    # les booléens is_journaliste/is_affilie/is_builder) : une seule requête
    # bulk ici plutôt qu'un appel par membre (Paul, 2026-08-22).
    statuts_by_member = await list_member_statuts_bulk(server)
    for m in members:
        m["statuts"] = statuts_by_member.get(m["discord_id"], [])

    return _sort(members)


async def _get_cache(server: str) -> list[dict]:
    if _is_valid(server):
        return list(_cache[server][0])
    async with _lock:
        if _is_valid(server):
            return list(_cache[server][0])
        members = await _load_from_db(server)
        _cache[server] = (members, time.monotonic())
    return list(members)


# ════════════════════════════════════════════════════════════
# 📖 Lectures
# ════════════════════════════════════════════════════════════

async def list_staff(server: str) -> list[dict]:
    return await _get_cache(server)


async def get_staff_member(server: str, discord_id: int) -> dict | None:
    members = await _get_cache(server)
    for m in members:
        if m["discord_id"] == discord_id:
            return dict(m)
    return None


async def staff_exists(server: str, discord_id: int) -> bool:
    return await get_staff_member(server, discord_id) is not None


# ════════════════════════════════════════════════════════════
# ✍️ Écritures
# ════════════════════════════════════════════════════════════

async def upsert_staff_member(
    server: str,
    discord_id: int,
    pseudo_jeu: str,
    grade: str | None,
    skin_head_emoji: str = "",
    is_journaliste: bool | None = None,
    is_affilie: bool | None = None,
    is_builder: bool | None = None,
    pseudo_jeu_builder: str | None = _UNSET,
) -> bool:
    """Ajoute ou met à jour un membre. Retourne True si créé."""
    async with _lock:
        async with get_session() as session:
            row = await session.get(NGStaffMember, (server, discord_id))
            if row is None:
                session.add(NGStaffMember(
                    server=server,
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
        _invalidate(server)

    log.info(
        "[NG STAFF] %s : %s %s (%s) — %s",
        server, "ajouté" if created else "mis à jour", pseudo_jeu, discord_id, grade,
    )
    return created


async def add_staff_member(
    server: str,
    discord_id: int,
    pseudo_jeu: str,
    grade: str | None,
    skin_head_emoji: str = "",
    is_journaliste: bool = False,
    is_affilie: bool = False,
    is_builder: bool = False,
    pseudo_jeu_builder: str | None = None,
) -> bool:
    """Ajoute un membre. Retourne False si (server, discord_id) est déjà présent."""
    async with _lock:
        async with get_session() as session:
            existing = await session.get(NGStaffMember, (server, discord_id))
            if existing is not None:
                return False
            session.add(NGStaffMember(
                server=server,
                discord_id=discord_id,
                pseudo_jeu=pseudo_jeu,
                grade=grade,
                skin_head_emoji=skin_head_emoji,
                is_journaliste=is_journaliste,
                is_affilie=is_affilie,
                is_builder=is_builder,
                pseudo_jeu_builder=pseudo_jeu_builder,
            ))
        _invalidate(server)
    log.info("[NG STAFF] %s : ajouté %s (%s) — %s", server, pseudo_jeu, discord_id, grade)
    return True


async def remove_staff_member(server: str, discord_id: int) -> bool:
    """Retire un membre. Retourne False s'il est absent."""
    async with _lock:
        async with get_session() as session:
            result = await session.execute(
                delete(NGStaffMember).where(
                    NGStaffMember.server == server, NGStaffMember.discord_id == discord_id
                )
            )
            deleted = result.rowcount > 0
        if deleted:
            _invalidate(server)
    if deleted:
        log.info("[NG STAFF] %s : retiré discord_id=%s", server, discord_id)
    return deleted


async def update_staff_member(server: str, discord_id: int, **fields: object) -> bool:
    """Met à jour les champs d'un membre."""
    allowed = {
        "pseudo_jeu", "grade", "skin_head_emoji",
        "is_journaliste", "is_affilie", "is_builder", "pseudo_jeu_builder",
        "blames",
    }

    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return False

    async with _lock:
        async with get_session() as session:
            row = await session.get(NGStaffMember, (server, discord_id))
            if row is None:
                return False
            for k, v in clean.items():
                setattr(row, k, v)
        _invalidate(server)

    log.info("[NG STAFF] %s : modifié discord_id=%s champs=%s", server, discord_id, list(clean))
    return True