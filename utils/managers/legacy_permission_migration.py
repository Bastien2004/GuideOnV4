"""
utils/managers/legacy_permission_migration.py — Backfill permission_entries
(ancien système) -> permission_grade_members (RBAC).

Ce module N'EST PAS importé au démarrage du bot (voir bot.py — aucune
référence). C'est un outil de maintenance / vérification pour la phase 3 de
la refonte multi-serveurs (voir migrations/versions/*_rbac_modo_grades_and_
legacy_backfill.py, qui exécute le même mapping en SQL brut).

Usage recommandé :
    1. AVANT `alembic upgrade` : lancer `migrate_legacy_permissions(dry_run=True)`
       sur la DB dev pour prévisualiser ce qui sera migré.
    2. Appliquer la révision Alembic (SQL, contre la vraie DB).
    3. APRÈS : relancer `migrate_legacy_permissions()` (dry_run=False). Étant
       idempotent, il ne doit plus rien insérer — un total non nul indique
       une divergence entre ce module et le SQL de la migration, à investiguer
       avant de continuer la refonte.

Le mapping ci-dessous doit rester strictement synchronisé avec
LEGACY_ROLE_TO_GRADE dans la révision Alembic correspondante.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from utils.db.models.permission import PermissionEntry
from utils.db.models.permission_rbac import PermissionCategory, PermissionGrade
from utils.db.session import get_session
from utils.managers.permission_rbac_manager import add_member

log = logging.getLogger(__name__)

# role (PermissionEntry.role, valeur str) -> slug complet du grade RBAC cible.
# "ADMIN" n'existe pas dans l'enum PermissionRole actuel (utils.db.models.
# permission) — gardé pour rester synchronisé avec le document de refonte ;
# sans effet tant qu'aucune ligne permission_entries n'a ce role.
LEGACY_ROLE_TO_GRADE: dict[str, str] = {
    "DEV": "equipe_guideon.dev",
    "STAFF_GUIDEON": "equipe_guideon.staff",
    "ADMIN": "equipe_guideon.admin",
    "OP_ALPHA": "staff_alpha.op",
    "MODO_PLUS_ALPHA": "staff_alpha.modo_plus",
    "MODO_ALPHA": "staff_alpha.modo",
}


async def _resolve_grade_id(full_slug: str) -> int | None:
    """Résout un slug complet "{category}.{grade}" en grade_id, ou None."""
    category_slug, _, grade_slug = full_slug.partition(".")
    if not grade_slug:
        raise ValueError(f"Slug de grade invalide (attendu 'categorie.grade') : {full_slug!r}")

    async with get_session() as session:
        result = await session.execute(
            select(PermissionGrade.id)
            .join(PermissionCategory, PermissionCategory.id == PermissionGrade.category_id)
            .where(PermissionCategory.slug == category_slug, PermissionGrade.slug == grade_slug)
        )
        return result.scalar_one_or_none()


async def migrate_legacy_permissions(dry_run: bool = False) -> dict[str, int]:
    """
    Parcourt tous les rôles de LEGACY_ROLE_TO_GRADE, lit les discord_id
    associés dans permission_entries, et les ajoute comme membres directs
    du grade RBAC cible (via permission_rbac_manager.add_member — idempotent).

    Retourne {role: nombre_de_membres_ajoutés}. Un rôle dont le grade cible
    n'existe pas en DB (catégorie/grade manquant) est ignoré avec un warning
    plutôt que de lever une exception — la migration continue pour les
    autres rôles.

    dry_run=True : ne fait aucune écriture, retourne le nombre de membres
    qui SERAIENT ajoutés (utile pour prévisualiser avant `alembic upgrade`).
    """
    summary: dict[str, int] = {}

    for role, full_slug in LEGACY_ROLE_TO_GRADE.items():
        grade_id = await _resolve_grade_id(full_slug)
        if grade_id is None:
            log.warning(
                "migrate_legacy_permissions : grade cible introuvable pour role=%s (%s) — ignoré",
                role, full_slug,
            )
            summary[role] = 0
            continue

        async with get_session() as session:
            rows = (
                await session.execute(
                    select(PermissionEntry.discord_id).where(PermissionEntry.role == role)
                )
            ).scalars().all()

        count = 0
        for raw_discord_id in rows:
            try:
                discord_id = int(raw_discord_id)
            except (TypeError, ValueError):
                log.warning(
                    "migrate_legacy_permissions : discord_id invalide %r pour role=%s — ignoré",
                    raw_discord_id, role,
                )
                continue

            if dry_run:
                count += 1
                continue

            added = await add_member(grade_id, discord_id)
            if added:
                count += 1

        summary[role] = count

    return summary
