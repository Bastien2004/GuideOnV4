"""
tests/test_permissions_rbac_view_helpers.py — Couvre la logique pure (non-UI)
du dashboard /dev permissions (phase 4) : construction des options
d'inclusion (filtrage anti-cycle), résolution de slug complet, découpage en
lignes de boutons.
"""
from __future__ import annotations

import pytest
from discord.ui import Button

from utils.managers import permission_rbac_manager as rbac
from views.dev.permissions_rbac_view import (
    _build_add_include_options,
    _full_slug,
    _rows_of_buttons,
)


@pytest.mark.asyncio
async def test_full_slug(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    grade = await rbac.create_grade(cat.id, "op", "Opérateur")

    assert await _full_slug(grade) == "staff_alpha.op"


@pytest.mark.asyncio
async def test_build_add_include_options_excludes_self_and_cycles(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    admin = await rbac.create_grade(cat.id, "admin", "Administrateur")
    sm = await rbac.create_grade(cat.id, "sm", "Super Modérateur")
    op = await rbac.create_grade(cat.id, "op", "Opérateur")
    await rbac.add_include(op.id, admin.id)

    options = await _build_add_include_options(op.id)
    values = {opt.value for opt in options}

    assert str(op.id) not in values      # pas soi-même
    assert str(admin.id) not in values   # déjà inclus
    assert str(sm.id) in values          # candidat valide

    # admin -> op créerait un cycle (op inclut déjà admin)
    options_from_admin = await _build_add_include_options(admin.id)
    assert str(op.id) not in {opt.value for opt in options_from_admin}


@pytest.mark.asyncio
async def test_build_add_include_options_empty_when_nothing_eligible(patched_get_session):
    cat = await rbac.create_category("staff_alpha", "Staff Alpha")
    only_grade = await rbac.create_grade(cat.id, "op", "Opérateur")

    options = await _build_add_include_options(only_grade.id)
    assert options == []


def test_rows_of_buttons_chunks_by_five():
    buttons = [Button(label=str(i)) for i in range(12)]
    rows = _rows_of_buttons(buttons)
    assert len(rows) == 3
    assert [len(row.children) for row in rows] == [5, 5, 2]


def test_rows_of_buttons_empty():
    assert _rows_of_buttons([]) == []
