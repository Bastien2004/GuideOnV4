"""
tests/test_permission_rbac_manager_dashboard_helpers.py — Helpers ajoutés pour
le dashboard /dev permissions (phase 4) : slugify, génération de slug unique,
list_children/list_parents, can_include (filtrage UI anti-cycle).
"""
from __future__ import annotations

import pytest

from utils.managers import permission_rbac_manager as rbac
from utils.managers.permission_rbac_manager import slugify

# ══════════════════════════════════════════════════════════════════════════
# 🔤 slugify (pas besoin de DB)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "text,expected",
    [
        ("Équipe GuideOn", "equipe_guideon"),
        ("Staff Alpha", "staff_alpha"),
        ("Partenaire n°1", "partenaire_n1"),
        ("  Espaces   multiples  ", "espaces_multiples"),
        ("ADMIN", "admin"),
        ("çà-et-là", "ca_et_la"),
        ("", "grade"),
        ("!!!", "grade"),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_slugify_truncates_to_64_chars():
    long_name = "a" * 100
    assert len(slugify(long_name)) == 64


# ══════════════════════════════════════════════════════════════════════════
# 🔑 Slugs uniques (avec DB)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_unique_category_slug_no_collision(patched_get_session):
    slug = await rbac.unique_category_slug("Staff Alpha")
    assert slug == "staff_alpha"


@pytest.mark.asyncio
async def test_unique_category_slug_collision_appends_suffix(patched_get_session):
    await rbac.create_category("staff_alpha", "Staff Alpha")
    slug = await rbac.unique_category_slug("Staff Alpha")
    assert slug == "staff_alpha_2"

    await rbac.create_category(slug, "Staff Alpha (bis)")
    slug2 = await rbac.unique_category_slug("Staff Alpha")
    assert slug2 == "staff_alpha_3"


@pytest.mark.asyncio
async def test_unique_grade_slug_scoped_per_category(patched_get_session):
    cat_a = await rbac.create_category("staff_alpha", "Staff Alpha")
    cat_b = await rbac.create_category("staff_delta", "Staff Delta")

    await rbac.create_grade(cat_a.id, "administrateur", "Administrateur")

    # Même slug "administrateur" libre dans une autre catégorie (scope = category_id)
    slug_b = await rbac.unique_grade_slug(cat_b.id, "Administrateur")
    assert slug_b == "administrateur"

    # Mais en collision dans la même catégorie
    slug_a = await rbac.unique_grade_slug(cat_a.id, "Administrateur")
    assert slug_a == "administrateur_2"


# ══════════════════════════════════════════════════════════════════════════
# 🔗 list_children / list_parents
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_children_and_parents(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    admin = await rbac.create_grade(cat.id, "admin", "Administrateur", 1)
    sm = await rbac.create_grade(cat.id, "sm", "Super Modérateur", 2)
    op = await rbac.create_grade(cat.id, "op", "Opérateur", 3)

    await rbac.add_include(op.id, admin.id)
    await rbac.add_include(op.id, sm.id)

    children = await rbac.list_children(op.id)
    assert sorted(g.slug for g in children) == ["admin", "sm"]

    assert await rbac.list_children(admin.id) == []

    parents_of_admin = await rbac.list_parents(admin.id)
    assert [g.slug for g in parents_of_admin] == ["op"]

    assert await rbac.list_parents(op.id) == []


# ══════════════════════════════════════════════════════════════════════════
# 🚫 can_include (filtrage UI)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_can_include_rejects_self(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    grade = await rbac.create_grade(cat.id, "op", "Opérateur")
    assert await rbac.can_include(grade.id, grade.id) is False


@pytest.mark.asyncio
async def test_can_include_rejects_existing(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    op = await rbac.create_grade(cat.id, "op", "Opérateur")
    admin = await rbac.create_grade(cat.id, "admin", "Administrateur")
    await rbac.add_include(op.id, admin.id)

    assert await rbac.can_include(op.id, admin.id) is False


@pytest.mark.asyncio
async def test_can_include_rejects_cycle(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    op = await rbac.create_grade(cat.id, "op", "Opérateur")
    admin = await rbac.create_grade(cat.id, "admin", "Administrateur")
    await rbac.add_include(op.id, admin.id)

    assert await rbac.can_include(admin.id, op.id) is False


@pytest.mark.asyncio
async def test_can_include_accepts_valid(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    modo_plus = await rbac.create_grade(cat.id, "modo_plus", "Modérateur+")
    op = await rbac.create_grade(cat.id, "op", "Opérateur")

    assert await rbac.can_include(modo_plus.id, op.id) is True


@pytest.mark.asyncio
async def test_list_all_grades_with_category(patched_get_session):
    cat_a = await rbac.create_category("equipe_guideon", "Équipe GuideOn", position=1)
    cat_b = await rbac.create_category("staff_alpha", "Staff Alpha", position=2)
    await rbac.create_grade(cat_a.id, "dev", "Développeur", 1)
    await rbac.create_grade(cat_b.id, "op", "Opérateur", 1)

    rows = await rbac.list_all_grades_with_category()
    assert [(g.slug, c.slug) for g, c in rows] == [("dev", "equipe_guideon"), ("op", "staff_alpha")]


@pytest.mark.asyncio
async def test_get_category_and_get_grade(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    grade = await rbac.create_grade(cat.id, "op", "Opérateur")

    fetched_cat = await rbac.get_category(cat.id)
    assert fetched_cat is not None and fetched_cat.slug == "staff_alpha"

    fetched_grade = await rbac.get_grade(grade.id)
    assert fetched_grade is not None and fetched_grade.slug == "op"

    assert await rbac.get_category(999999) is None
    assert await rbac.get_grade(999999) is None
