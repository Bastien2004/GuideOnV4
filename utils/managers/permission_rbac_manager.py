"""
utils/managers/permission_rbac_manager.py — Résolution RBAC (grades, inclusions).

Remplace utils.managers.permission_manager pour toute nouvelle permission.
L'ancien système (PermissionRole / PermissionEntry) reste en place jusqu'à
la phase de nettoyage finale de la refonte multi-serveurs — ne pas le
supprimer avant la migration legacy (phase 3) validée en prod.

Cache :
- Structure (catégories, grades, inclusions) : TTL 60s, change rarement.
- Membres directs : rechargés avec la même structure (voir refresh_cache).
  Un ajout/retrait de membre invalide le cache immédiatement (comme
  permission_manager), donc jamais plus de 60s de staleness sur les lectures
  passives, et 0s après une écriture faite depuis ce process.

API principale :
    has_grade(discord_id, grade_slug) -> bool
    list_categories() -> list[PermissionCategory]
    list_grades(category_id) -> list[PermissionGrade]
    list_members(grade_id) -> list[int]                  (directs uniquement)
    list_effective_members(grade_id) -> list[int]        (directs + inclus, dédupliqué)
    add_member(grade_id, discord_id) -> bool
    remove_member(grade_id, discord_id) -> bool
    add_include(parent_grade_id, child_grade_id) -> bool  (False si cycle détecté)
    remove_include(parent_grade_id, child_grade_id) -> bool
    create_category(slug, display_name, ng_server_id=None, position=0) -> PermissionCategory
    delete_category(category_id) -> bool
    create_grade(category_id, slug, display_name, position=0) -> PermissionGrade
    delete_grade(grade_id) -> bool

`grade_slug` dans has_grade() est le slug complet "{category.slug}.{grade.slug}"
(ex: "staff_alpha.op").
"""
from __future__ import annotations

import asyncio
import logging
import time
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import delete, select

from utils.db.models.permission_rbac import (
    PermissionCategory,
    PermissionGrade,
    PermissionGradeInclude,
    PermissionGradeMember,
)
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60


@dataclass
class _GradeCache:
    # grade_id -> full slug "{category_slug}.{grade_slug}"
    full_slug_by_id: dict[int, str] = field(default_factory=dict)
    # full slug -> grade_id
    id_by_full_slug: dict[str, int] = field(default_factory=dict)
    # parent_grade_id -> set(child_grade_id)   (inclusion directe uniquement)
    includes: dict[int, set[int]] = field(default_factory=dict)
    # grade_id -> set(discord_id)   (membres directs uniquement)
    members: dict[int, set[int]] = field(default_factory=dict)


_cache = _GradeCache()
_cache_loaded_at: float = 0.0
_cache_ready: bool = False
_refresh_lock = asyncio.Lock()


# ══════════════════════════════════════════════════════════════════════════
# 🔄 REFRESH (async)
# ══════════════════════════════════════════════════════════════════════════

async def refresh_cache() -> None:
    """Recharge tout le cache (grades, inclusions, membres) depuis la DB."""
    global _cache, _cache_loaded_at, _cache_ready

    async with _refresh_lock:
        try:
            async with get_session() as session:
                categories = (
                    (await session.execute(select(PermissionCategory))).scalars().all()
                )
                grades = (await session.execute(select(PermissionGrade))).scalars().all()
                includes = (
                    (await session.execute(select(PermissionGradeInclude))).scalars().all()
                )
                members = (
                    (await session.execute(select(PermissionGradeMember))).scalars().all()
                )
        except Exception:
            log.exception("Refresh cache RBAC échoué — on garde l'ancien cache")
            return

        cat_slug_by_id = {c.id: c.slug for c in categories}

        new_cache = _GradeCache()
        for g in grades:
            cat_slug = cat_slug_by_id.get(g.category_id)
            if cat_slug is None:
                # Grade orphelin (catégorie supprimée sans cascade) — on ignore.
                continue
            full_slug = f"{cat_slug}.{g.slug}"
            new_cache.full_slug_by_id[g.id] = full_slug
            new_cache.id_by_full_slug[full_slug] = g.id

        for inc in includes:
            new_cache.includes.setdefault(inc.parent_grade_id, set()).add(inc.child_grade_id)

        for m in members:
            new_cache.members.setdefault(m.grade_id, set()).add(m.discord_id)

        _cache = new_cache
        _cache_loaded_at = time.monotonic()
        _cache_ready = True


async def _ensure_fresh() -> None:
    """Rafraîchit le cache s'il n'a jamais été chargé ou si le TTL est expiré."""
    if not _cache_ready or (time.monotonic() - _cache_loaded_at) > CACHE_TTL_SECONDS:
        await refresh_cache()


def cache_is_ready() -> bool:
    return _cache_ready


# ══════════════════════════════════════════════════════════════════════════
# 🔍 RÉSOLUTION (has_grade)
# ══════════════════════════════════════════════════════════════════════════

def _resolve_effective_member_ids(grade_id: int, cache: _GradeCache) -> set[int]:
    """
    Membres directs de grade_id + membres de tous les grades inclus
    (récursivement). Protégé contre les cycles par un `visited`.
    """
    result: set[int] = set()
    visited: set[int] = set()
    stack = [grade_id]
    while stack:
        gid = stack.pop()
        if gid in visited:
            continue
        visited.add(gid)
        result |= cache.members.get(gid, set())
        stack.extend(cache.includes.get(gid, set()))
    return result


async def has_grade(discord_id: int, grade_slug: str) -> bool:
    """
    True si discord_id possède le grade `grade_slug` (slug complet
    "{category}.{grade}"), directement ou via une chaîne d'inclusion.
    """
    await _ensure_fresh()
    grade_id = _cache.id_by_full_slug.get(grade_slug)
    if grade_id is None:
        log.warning("has_grade appelé avec un slug de grade inconnu : %r", grade_slug)
        return False
    return discord_id in _resolve_effective_member_ids(grade_id, _cache)


# ══════════════════════════════════════════════════════════════════════════
# 📚 LECTURES ASYNC (dashboard /dev permissions)
# ══════════════════════════════════════════════════════════════════════════

async def list_categories() -> list[PermissionCategory]:
    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    select(PermissionCategory).order_by(PermissionCategory.position)
                )
            )
            .scalars()
            .all()
        )
    return list(rows)


async def list_grades(category_id: int) -> list[PermissionGrade]:
    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    select(PermissionGrade)
                    .where(PermissionGrade.category_id == category_id)
                    .order_by(PermissionGrade.position, PermissionGrade.id)
                )
            )
            .scalars()
            .all()
        )
    return list(rows)


async def list_members(grade_id: int) -> list[int]:
    """Membres directs uniquement (pas les inclusions)."""
    await _ensure_fresh()
    return sorted(_cache.members.get(grade_id, set()))


async def list_effective_members(grade_id: int) -> list[int]:
    """Membres directs + membres de tous les grades inclus, dédupliqué."""
    await _ensure_fresh()
    return sorted(_resolve_effective_member_ids(grade_id, _cache))


# ══════════════════════════════════════════════════════════════════════════
# ✍️ ÉCRITURES ASYNC (invalident le cache)
# ══════════════════════════════════════════════════════════════════════════

async def add_member(grade_id: int, discord_id: int) -> bool:
    """Ajoute discord_id comme membre direct de grade_id. Idempotent."""
    added = False
    async with get_session() as session:
        exists = await session.get(PermissionGradeMember, (grade_id, discord_id))
        if exists is None:
            session.add(PermissionGradeMember(grade_id=grade_id, discord_id=discord_id))
            added = True
    if added:
        await refresh_cache()
        log.info("RBAC : ajout membre %s au grade %s", discord_id, grade_id)
    return added


async def remove_member(grade_id: int, discord_id: int) -> bool:
    """Retire discord_id des membres directs de grade_id."""
    async with get_session() as session:
        result = await session.execute(
            delete(PermissionGradeMember).where(
                PermissionGradeMember.grade_id == grade_id,
                PermissionGradeMember.discord_id == discord_id,
            )
        )
        removed = result.rowcount > 0
    if removed:
        await refresh_cache()
        log.info("RBAC : retrait membre %s du grade %s", discord_id, grade_id)
    return removed


def _would_create_cycle(parent_grade_id: int, child_grade_id: int, cache: _GradeCache) -> bool:
    """
    Avant d'ajouter l'arête parent -> child : parcours en descente depuis
    child en suivant les inclusions existantes. Si parent_grade_id est
    atteint, ajouter l'arête créerait un cycle.
    """
    visited: set[int] = set()
    stack = [child_grade_id]
    while stack:
        gid = stack.pop()
        if gid == parent_grade_id:
            return True
        if gid in visited:
            continue
        visited.add(gid)
        stack.extend(cache.includes.get(gid, set()))
    return False


async def add_include(parent_grade_id: int, child_grade_id: int) -> bool:
    """
    Ajoute une inclusion parent -> child. Retourne False si :
    - parent == child (auto-inclusion)
    - un cycle serait créé
    - l'inclusion existe déjà (idempotent, pas une erreur mais rien à faire)
    """
    if parent_grade_id == child_grade_id:
        return False

    await _ensure_fresh()
    if _would_create_cycle(parent_grade_id, child_grade_id, _cache):
        log.warning(
            "RBAC : inclusion refusée (cycle) parent=%s child=%s",
            parent_grade_id, child_grade_id,
        )
        return False

    added = False
    async with get_session() as session:
        exists = await session.get(
            PermissionGradeInclude, (parent_grade_id, child_grade_id)
        )
        if exists is None:
            session.add(
                PermissionGradeInclude(
                    parent_grade_id=parent_grade_id, child_grade_id=child_grade_id
                )
            )
            added = True
    if added:
        await refresh_cache()
        log.info(
            "RBAC : inclusion ajoutée parent=%s child=%s", parent_grade_id, child_grade_id
        )
    return added


async def remove_include(parent_grade_id: int, child_grade_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            delete(PermissionGradeInclude).where(
                PermissionGradeInclude.parent_grade_id == parent_grade_id,
                PermissionGradeInclude.child_grade_id == child_grade_id,
            )
        )
        removed = result.rowcount > 0
    if removed:
        await refresh_cache()
        log.info(
            "RBAC : inclusion retirée parent=%s child=%s", parent_grade_id, child_grade_id
        )
    return removed


async def create_category(
    slug: str, display_name: str, ng_server_id: int | None = None, position: int = 0
) -> PermissionCategory:
    async with get_session() as session:
        category = PermissionCategory(
            slug=slug,
            display_name=display_name,
            ng_server_id=ng_server_id,
            position=position,
        )
        session.add(category)
        await session.flush()
        await session.refresh(category)
        category_id = category.id
        category_slug = category.slug
        category_display_name = category.display_name
        category_ng_server_id = category.ng_server_id
        category_position = category.position
    await refresh_cache()
    log.info("RBAC : catégorie créée slug=%s id=%s", slug, category_id)
    return PermissionCategory(
        id=category_id,
        slug=category_slug,
        display_name=category_display_name,
        ng_server_id=category_ng_server_id,
        position=category_position,
    )


async def delete_category(category_id: int) -> bool:
    """
    Supprime une catégorie et, en cascade applicative, ses grades / membres /
    inclusions associés (pas de ON DELETE CASCADE en DB par design — voir
    §14 du prompt de refonte : suppressions toujours explicites et loggées).
    """
    async with get_session() as session:
        grade_ids = (
            (
                await session.execute(
                    select(PermissionGrade.id).where(
                        PermissionGrade.category_id == category_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if grade_ids:
            await session.execute(
                delete(PermissionGradeMember).where(
                    PermissionGradeMember.grade_id.in_(grade_ids)
                )
            )
            await session.execute(
                delete(PermissionGradeInclude).where(
                    PermissionGradeInclude.parent_grade_id.in_(grade_ids)
                    | PermissionGradeInclude.child_grade_id.in_(grade_ids)
                )
            )
            await session.execute(
                delete(PermissionGrade).where(PermissionGrade.id.in_(grade_ids))
            )
        result = await session.execute(
            delete(PermissionCategory).where(PermissionCategory.id == category_id)
        )
        deleted = result.rowcount > 0
    if deleted:
        await refresh_cache()
        log.info("RBAC : catégorie supprimée id=%s", category_id)
    return deleted


async def create_grade(
    category_id: int, slug: str, display_name: str, position: int = 0
) -> PermissionGrade:
    async with get_session() as session:
        grade = PermissionGrade(
            category_id=category_id, slug=slug, display_name=display_name, position=position
        )
        session.add(grade)
        await session.flush()
        await session.refresh(grade)
        grade_id = grade.id
        grade_category_id = grade.category_id
        grade_slug = grade.slug
        grade_display_name = grade.display_name
        grade_position = grade.position
    await refresh_cache()
    log.info("RBAC : grade créé category_id=%s slug=%s id=%s", category_id, slug, grade_id)
    return PermissionGrade(
        id=grade_id,
        category_id=grade_category_id,
        slug=grade_slug,
        display_name=grade_display_name,
        position=grade_position,
    )


async def move_grade(grade_id: int, direction: int) -> bool:
    """
    Déplace un grade d'un cran vers le haut (direction=-1) ou vers le bas
    (direction=+1) dans sa catégorie.

    À chaque appel, TOUTES les positions de la catégorie sont renumérotées
    proprement en 10, 20, 30... — ça évite les positions à zéro (défaut à
    la création) qui rendent l'ordre imprévisible, et garantit qu'un futur
    swap trouve un adjacent au pas fixe.

    Retourne True si le grade a bougé, False s'il était déjà en bout de
    liste (ou si le grade n'existe pas / direction invalide).
    """
    if direction not in (-1, 1):
        return False

    async with get_session() as session:
        grade = await session.get(PermissionGrade, grade_id)
        if grade is None:
            return False

        # Charge tous les grades de la catégorie, ordre stable.
        grades = list(
            (
                await session.execute(
                    select(PermissionGrade)
                    .where(PermissionGrade.category_id == grade.category_id)
                    .order_by(PermissionGrade.position, PermissionGrade.id)
                )
            )
            .scalars()
            .all()
        )

        idx = next((i for i, g in enumerate(grades) if g.id == grade_id), None)
        if idx is None:
            return False

        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(grades):
            return False  # Déjà tout en haut / tout en bas.

        # Swap dans la liste locale.
        grades[idx], grades[new_idx] = grades[new_idx], grades[idx]

        # Renumérote proprement pour éviter les collisions futures.
        for i, g in enumerate(grades):
            g.position = (i + 1) * 10

    await refresh_cache()
    return True


async def delete_grade(grade_id: int) -> bool:
    """Supprime un grade et, en cascade applicative, ses membres / inclusions."""
    async with get_session() as session:
        await session.execute(
            delete(PermissionGradeMember).where(PermissionGradeMember.grade_id == grade_id)
        )
        await session.execute(
            delete(PermissionGradeInclude).where(
                (PermissionGradeInclude.parent_grade_id == grade_id)
                | (PermissionGradeInclude.child_grade_id == grade_id)
            )
        )
        result = await session.execute(
            delete(PermissionGrade).where(PermissionGrade.id == grade_id)
        )
        deleted = result.rowcount > 0
    if deleted:
        await refresh_cache()
        log.info("RBAC : grade supprimé id=%s", grade_id)
    return deleted


# ══════════════════════════════════════════════════════════════════════════
# 📖 LECTURES ASYNC PAR ID (dashboard /dev permissions)
# ══════════════════════════════════════════════════════════════════════════

async def get_category(category_id: int) -> PermissionCategory | None:
    async with get_session() as session:
        return await session.get(PermissionCategory, category_id)


async def get_grade(grade_id: int) -> PermissionGrade | None:
    async with get_session() as session:
        return await session.get(PermissionGrade, grade_id)


async def list_children(grade_id: int) -> list[PermissionGrade]:
    """Grades inclus directement par grade_id (pas de récursion)."""
    await _ensure_fresh()
    child_ids = _cache.includes.get(grade_id, set())
    if not child_ids:
        return []
    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    select(PermissionGrade)
                    .where(PermissionGrade.id.in_(child_ids))
                    .order_by(PermissionGrade.position)
                )
            )
            .scalars()
            .all()
        )
    return list(rows)


async def list_parents(grade_id: int) -> list[PermissionGrade]:
    """Grades qui incluent directement grade_id (section "Grade inclus par")."""
    await _ensure_fresh()
    parent_ids = {pid for pid, children in _cache.includes.items() if grade_id in children}
    if not parent_ids:
        return []
    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    select(PermissionGrade)
                    .where(PermissionGrade.id.in_(parent_ids))
                    .order_by(PermissionGrade.position)
                )
            )
            .scalars()
            .all()
        )
    return list(rows)


async def list_all_grades_with_category() -> list[tuple[PermissionGrade, PermissionCategory]]:
    """Tous les grades toutes catégories confondues, pour peupler un menu de sélection."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(PermissionGrade, PermissionCategory)
                .join(PermissionCategory, PermissionCategory.id == PermissionGrade.category_id)
                .order_by(PermissionCategory.position, PermissionGrade.position)
            )
        ).all()
    return [(g, c) for g, c in rows]


async def can_include(parent_grade_id: int, child_grade_id: int) -> bool:
    """
    True si l'inclusion parent_grade_id -> child_grade_id est valide :
    pas une auto-inclusion, pas déjà existante, ne crée pas de cycle.
    Utilisé par l'UI pour filtrer le menu déroulant "Ajouter une inclusion"
    (§10 du prompt : "sauf soi-même et descendants").
    """
    if parent_grade_id == child_grade_id:
        return False
    await _ensure_fresh()
    if child_grade_id in _cache.includes.get(parent_grade_id, set()):
        return False  # déjà incluse
    return not _would_create_cycle(parent_grade_id, child_grade_id, _cache)


# ══════════════════════════════════════════════════════════════════════════
# 🔤 SLUGS (génération auto pour le dashboard, §10 du prompt)
# ══════════════════════════════════════════════════════════════════════════

def slugify(text: str) -> str:
    """
    "Équipe GuideOn n°1" -> "equipe_guideon_n1". Lowercase, ASCII, snake_case.
    Tronqué à 64 caractères (limite String(64) des colonnes slug).

    Les accents sont retirés via une décomposition Unicode NFKD (ex: 'é' ->
    'e' + accent combinant, l'accent est ensuite filtré par le test
    `ch.isascii()` ci-dessous) plutôt qu'une table de correspondance manuelle
    — plus robuste, couvre tous les caractères accentués sans entretien.
    """
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    out_chars: list[str] = []
    prev_was_sep = False
    for ch in text.lower():
        if ch.isalnum() and ch.isascii():
            out_chars.append(ch)
            prev_was_sep = False
        elif not prev_was_sep:
            out_chars.append("_")
            prev_was_sep = True
    slug = "".join(out_chars).strip("_")
    return slug[:64] or "grade"


async def unique_category_slug(base_display_name: str) -> str:
    """Slug unique pour une nouvelle catégorie, dérivé de base_display_name."""
    base = slugify(base_display_name)
    async with get_session() as session:
        existing = set(
            (await session.execute(select(PermissionCategory.slug))).scalars().all()
        )
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"[:64]


async def unique_grade_slug(category_id: int, base_display_name: str) -> str:
    """Slug unique pour un nouveau grade au sein d'une catégorie."""
    base = slugify(base_display_name)
    async with get_session() as session:
        existing = set(
            (
                await session.execute(
                    select(PermissionGrade.slug).where(
                        PermissionGrade.category_id == category_id
                    )
                )
            )
            .scalars()
            .all()
        )
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"[:64]