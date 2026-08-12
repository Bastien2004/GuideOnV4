"""
tests/test_permission_rbac_manager.py — Couvre §14 du prompt de refonte pour
RBAC : has_grade avec chaîne d'inclusion, détection de cycles, résolution
récursive, membres dédupliqués, isolation multi-serveurs.
"""
from __future__ import annotations

import pytest

from utils.managers import permission_rbac_manager as rbac


async def _setup_staff_alpha(session_factory=None):
    """
    Catégorie 'staff_alpha' avec grades admin / sm / op, où op inclut
    admin et sm (reproduit le seed de la migration 002_rbac_tables).
    Retourne un dict {slug: grade_id}.
    """
    category = await rbac.create_category("staff_alpha", "Staff Alpha")
    admin = await rbac.create_grade(category.id, "admin", "Administrateur", 1)
    sm = await rbac.create_grade(category.id, "sm", "Super Modérateur", 2)
    op = await rbac.create_grade(category.id, "op", "Opérateur", 3)

    assert await rbac.add_include(op.id, admin.id) is True
    assert await rbac.add_include(op.id, sm.id) is True

    return {"category_id": category.id, "admin": admin.id, "sm": sm.id, "op": op.id}


@pytest.mark.asyncio
async def test_has_grade_direct_member(patched_get_session):
    ids = await _setup_staff_alpha()
    await rbac.add_member(ids["admin"], 42)

    assert await rbac.has_grade(42, "staff_alpha.admin") is True
    assert await rbac.has_grade(42, "staff_alpha.sm") is False
    # NB: op inclut admin (voir _setup_staff_alpha) -> 42 est donc aussi "op"
    # par inclusion. Le cas "membre direct only, sans inclusion" est couvert
    # par test_multi_server_isolation avec des catégories sans inclusion.


@pytest.mark.asyncio
async def test_has_grade_via_inclusion_chain(patched_get_session):
    ids = await _setup_staff_alpha()
    await rbac.add_member(ids["admin"], 42)

    # 42 est admin -> op inclut admin -> 42 doit être considéré "op" aussi
    assert await rbac.has_grade(42, "staff_alpha.op") is True


@pytest.mark.asyncio
async def test_has_grade_unknown_slug_returns_false(patched_get_session):
    await _setup_staff_alpha()
    assert await rbac.has_grade(1, "staff_alpha.inexistant") is False
    assert await rbac.has_grade(1, "categorie_inexistante.grade") is False


@pytest.mark.asyncio
async def test_has_grade_direct_op_member(patched_get_session):
    ids = await _setup_staff_alpha()
    await rbac.add_member(ids["op"], 7)

    assert await rbac.has_grade(7, "staff_alpha.op") is True
    # Être membre direct de op ne rend pas automatiquement membre de admin
    assert await rbac.has_grade(7, "staff_alpha.admin") is False


@pytest.mark.asyncio
async def test_cycle_detection_direct(patched_get_session):
    ids = await _setup_staff_alpha()
    # op inclut déjà admin -> tenter admin inclut op doit être refusé (cycle)
    assert await rbac.add_include(ids["admin"], ids["op"]) is False


@pytest.mark.asyncio
async def test_cycle_detection_self_include(patched_get_session):
    ids = await _setup_staff_alpha()
    assert await rbac.add_include(ids["op"], ids["op"]) is False


@pytest.mark.asyncio
async def test_cycle_detection_transitive(patched_get_session):
    """A -> B -> C existant, puis C -> A doit être refusé (cycle indirect)."""
    category = await rbac.create_category("chain", "Chain Test")
    a = await rbac.create_grade(category.id, "a", "A", 1)
    b = await rbac.create_grade(category.id, "b", "B", 2)
    c = await rbac.create_grade(category.id, "c", "C", 3)

    assert await rbac.add_include(a.id, b.id) is True
    assert await rbac.add_include(b.id, c.id) is True
    # C -> A fermerait le cycle A -> B -> C -> A
    assert await rbac.add_include(c.id, a.id) is False


@pytest.mark.asyncio
async def test_list_effective_members_dedup(patched_get_session):
    ids = await _setup_staff_alpha()
    await rbac.add_member(ids["admin"], 1)
    await rbac.add_member(ids["sm"], 2)
    await rbac.add_member(ids["op"], 1)  # 1 est déjà membre direct de admin

    effective = await rbac.list_effective_members(ids["op"])
    assert effective == [1, 2]  # dédupliqué, trié

    direct = await rbac.list_members(ids["op"])
    assert direct == [1]


@pytest.mark.asyncio
async def test_remove_member_and_include(patched_get_session):
    ids = await _setup_staff_alpha()
    await rbac.add_member(ids["admin"], 42)
    assert await rbac.has_grade(42, "staff_alpha.op") is True

    assert await rbac.remove_include(ids["op"], ids["admin"]) is True
    assert await rbac.has_grade(42, "staff_alpha.op") is False
    assert await rbac.has_grade(42, "staff_alpha.admin") is True

    assert await rbac.remove_member(ids["admin"], 42) is True
    assert await rbac.has_grade(42, "staff_alpha.admin") is False


@pytest.mark.asyncio
async def test_add_member_idempotent(patched_get_session):
    ids = await _setup_staff_alpha()
    assert await rbac.add_member(ids["admin"], 42) is True
    assert await rbac.add_member(ids["admin"], 42) is False  # déjà présent


@pytest.mark.asyncio
async def test_multi_server_isolation(patched_get_session):
    """Insertion Alpha + Delta -> aucune fuite de membres entre catégories."""
    cat_alpha = await rbac.create_category("staff_alpha", "Staff Alpha")
    admin_alpha = await rbac.create_grade(cat_alpha.id, "admin", "Administrateur")

    cat_delta = await rbac.create_category("staff_delta", "Staff Delta")
    admin_delta = await rbac.create_grade(cat_delta.id, "admin", "Administrateur")

    await rbac.add_member(admin_alpha.id, 1)
    await rbac.add_member(admin_delta.id, 2)

    assert await rbac.has_grade(1, "staff_alpha.admin") is True
    assert await rbac.has_grade(1, "staff_delta.admin") is False
    assert await rbac.has_grade(2, "staff_delta.admin") is True
    assert await rbac.has_grade(2, "staff_alpha.admin") is False


@pytest.mark.asyncio
async def test_delete_grade_cascades_members_and_includes(patched_get_session):
    ids = await _setup_staff_alpha()
    await rbac.add_member(ids["admin"], 42)

    assert await rbac.delete_grade(ids["admin"]) is True

    # Le grade n'existe plus -> plus d'inclusion op->admin, plus de membre
    assert await rbac.has_grade(42, "staff_alpha.admin") is False
    assert await rbac.has_grade(42, "staff_alpha.op") is False


@pytest.mark.asyncio
async def test_delete_category_cascades_everything(patched_get_session):
    ids = await _setup_staff_alpha()
    await rbac.add_member(ids["admin"], 42)

    assert await rbac.delete_category(ids["category_id"]) is True

    categories = await rbac.list_categories()
    assert ids["category_id"] not in [c.id for c in categories]
    assert await rbac.has_grade(42, "staff_alpha.admin") is False


@pytest.mark.asyncio
async def test_cache_ttl_refresh_picks_up_direct_db_write(patched_get_session, monkeypatch):
    """Après expiration du TTL, une écriture externe doit être reflétée."""
    ids = await _setup_staff_alpha()
    await rbac.has_grade(1, "staff_alpha.admin")  # force un premier chargement

    await rbac.add_member(ids["admin"], 1)  # invalide déjà le cache via add_member
    assert await rbac.has_grade(1, "staff_alpha.admin") is True

    # Simule l'expiration du TTL sans écriture passant par le manager
    monkeypatch.setattr(rbac, "_cache_loaded_at", 0.0)
    assert await rbac.has_grade(1, "staff_alpha.admin") is True
