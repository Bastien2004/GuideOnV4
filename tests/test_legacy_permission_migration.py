"""
tests/test_legacy_permission_migration.py — Couvre le backfill legacy de la
phase 3 (permission_entries -> permission_grade_members) : mapping correct
par rôle, idempotence (rejouer 2x = même état final, cf §14 du prompt),
gestion des rôles sans grade cible et des discord_id invalides.
"""
from __future__ import annotations

import pytest

from utils.db.models.permission import PermissionEntry
from utils.managers import permission_rbac_manager as rbac
from utils.managers.legacy_permission_migration import migrate_legacy_permissions


async def _add_legacy_entry(session_factory, role: str, discord_id: str):
    async with session_factory() as session:
        session.add(PermissionEntry(role=role, discord_id=discord_id))
        await session.commit()


async def _seed_rbac_structure():
    """Reproduit le seed migration 002 (phase 2) + les grades ajoutés en phase 3."""
    equipe = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    dev = await rbac.create_grade(equipe.id, "dev", "Développeur", 1)
    staff = await rbac.create_grade(equipe.id, "staff", "Staff GuideOn", 2)
    admin_eq = await rbac.create_grade(equipe.id, "admin", "Administrateur", 3)

    staff_alpha = await rbac.create_category("staff_alpha", "Staff Alpha")
    admin = await rbac.create_grade(staff_alpha.id, "admin", "Administrateur", 1)
    sm = await rbac.create_grade(staff_alpha.id, "sm", "Super Modérateur", 2)
    op = await rbac.create_grade(staff_alpha.id, "op", "Opérateur", 3)
    modo_plus = await rbac.create_grade(staff_alpha.id, "modo_plus", "Modérateur+", 4)
    modo = await rbac.create_grade(staff_alpha.id, "modo", "Modérateur", 5)

    await rbac.add_include(op.id, admin.id)
    await rbac.add_include(op.id, sm.id)
    await rbac.add_include(modo_plus.id, op.id)
    await rbac.add_include(modo.id, modo_plus.id)

    return {
        "dev": dev.id, "staff": staff.id, "admin_eq": admin_eq.id,
        "admin": admin.id, "sm": sm.id, "op": op.id,
        "modo_plus": modo_plus.id, "modo": modo.id,
    }


@pytest.mark.asyncio
async def test_migrate_all_six_roles(patched_get_session):
    await _seed_rbac_structure()

    await _add_legacy_entry(patched_get_session, "DEV", "111")
    await _add_legacy_entry(patched_get_session, "STAFF_GUIDEON", "222")
    await _add_legacy_entry(patched_get_session, "OP_ALPHA", "333")
    await _add_legacy_entry(patched_get_session, "MODO_PLUS_ALPHA", "444")
    await _add_legacy_entry(patched_get_session, "MODO_ALPHA", "555")

    summary = await migrate_legacy_permissions()

    assert summary["DEV"] == 1
    assert summary["STAFF_GUIDEON"] == 1
    assert summary["OP_ALPHA"] == 1
    assert summary["MODO_PLUS_ALPHA"] == 1
    assert summary["MODO_ALPHA"] == 1
    assert summary["ADMIN"] == 0  # aucune entrée legacy avec ce role (n'existe pas dans l'enum)

    assert await rbac.has_grade(111, "equipe_guideon.dev") is True
    assert await rbac.has_grade(222, "equipe_guideon.staff") is True
    assert await rbac.has_grade(333, "staff_alpha.op") is True
    assert await rbac.has_grade(444, "staff_alpha.modo_plus") is True
    assert await rbac.has_grade(555, "staff_alpha.modo") is True

    # Vérifie la hiérarchie reconstituée : OP_ALPHA (333) doit aussi
    # compter comme modo_plus ET modo (inclusion op ⊂ modo_plus ⊂ modo).
    assert await rbac.has_grade(333, "staff_alpha.modo_plus") is True
    assert await rbac.has_grade(333, "staff_alpha.modo") is True
    # MODO_ALPHA (555) ne doit PAS être considéré op ou modo_plus
    # (l'inclusion ne remonte pas dans l'autre sens).
    assert await rbac.has_grade(555, "staff_alpha.op") is False
    assert await rbac.has_grade(555, "staff_alpha.modo_plus") is False


@pytest.mark.asyncio
async def test_migrate_is_idempotent(patched_get_session):
    await _seed_rbac_structure()
    await _add_legacy_entry(patched_get_session, "OP_ALPHA", "333")

    first = await migrate_legacy_permissions()
    assert first["OP_ALPHA"] == 1

    second = await migrate_legacy_permissions()
    assert second["OP_ALPHA"] == 0  # déjà membre, rien de plus ajouté


@pytest.mark.asyncio
async def test_migrate_no_duplicate_members_after_rerun(patched_get_session):
    grade_ids = await _seed_rbac_structure()
    await _add_legacy_entry(patched_get_session, "OP_ALPHA", "333")

    await migrate_legacy_permissions()
    await migrate_legacy_permissions()

    members = await rbac.list_members(grade_ids["op"])
    assert members == [333]  # un seul, pas de doublon


@pytest.mark.asyncio
async def test_migrate_dry_run_does_not_write(patched_get_session):
    grade_ids = await _seed_rbac_structure()
    await _add_legacy_entry(patched_get_session, "OP_ALPHA", "333")

    summary = await migrate_legacy_permissions(dry_run=True)
    assert summary["OP_ALPHA"] == 1  # aurait migré 1 membre

    members = await rbac.list_members(grade_ids["op"])
    assert members == []  # mais rien n'a été écrit


@pytest.mark.asyncio
async def test_migrate_missing_target_grade_is_skipped_gracefully(patched_get_session):
    # Structure RBAC volontairement incomplète : pas de catégorie staff_alpha.
    equipe = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    await rbac.create_grade(equipe.id, "dev", "Développeur", 1)

    await _add_legacy_entry(patched_get_session, "OP_ALPHA", "333")

    summary = await migrate_legacy_permissions()

    assert summary["OP_ALPHA"] == 0  # grade cible introuvable -> ignoré, pas d'exception


@pytest.mark.asyncio
async def test_migrate_invalid_discord_id_is_skipped(patched_get_session):
    grade_ids = await _seed_rbac_structure()
    await _add_legacy_entry(patched_get_session, "OP_ALPHA", "not-a-number")
    await _add_legacy_entry(patched_get_session, "OP_ALPHA", "333")

    summary = await migrate_legacy_permissions()

    assert summary["OP_ALPHA"] == 1  # seule la valeur valide est comptée
    members = await rbac.list_members(grade_ids["op"])
    assert members == [333]


@pytest.mark.asyncio
async def test_migrate_multiple_members_same_role(patched_get_session):
    grade_ids = await _seed_rbac_structure()
    await _add_legacy_entry(patched_get_session, "DEV", "1")
    await _add_legacy_entry(patched_get_session, "DEV", "2")
    await _add_legacy_entry(patched_get_session, "DEV", "3")

    summary = await migrate_legacy_permissions()

    assert summary["DEV"] == 3
    assert await rbac.list_members(grade_ids["dev"]) == [1, 2, 3]
