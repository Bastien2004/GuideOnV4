"""
tests/test_perm_legacy_rbac_rewire.py — Couvre §14 pour la phase 15
(nettoyage legacy) : utils/perm_alpha.py, perm_dev.py, perm_staff.py
lisent désormais le RBAC (has_grade) au lieu de l'ancienne table
permission_entries (get_ids), gelée depuis la phase 4. Vérifie le bug
corrigé (un membre ajouté uniquement via le RBAC, jamais présent dans
permission_entries, doit être reconnu) ainsi que la hiérarchie
d'inclusion RBAC déjà posée en phase 3 (staff_alpha : modo ⊇ modo_plus ⊇
op) qui remplace la chaîne de OR Python précédente.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.managers import permission_rbac_manager as rbac
from utils.perm_alpha import check_modo, check_modo_plus, check_op_alpha, is_modo, is_modo_plus, is_op_alpha
from utils.perm_dev import check_dev, is_dev
from utils.perm_staff import check_staff, is_staff


def _fake_interaction(user_id: int, *, response_done: bool = False) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response.is_done.return_value = response_done
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


async def _seed_staff_alpha(patched_get_session) -> dict[str, int]:
    """Reproduit exactement la hiérarchie posée par la migration
    d8d9b015e428 (phase 3) : modo_plus inclut op ; modo inclut modo_plus."""
    category = await rbac.create_category("staff_alpha", "Staff Alpha")
    op = await rbac.create_grade(category.id, "op", "Opérateur")
    modo_plus = await rbac.create_grade(category.id, "modo_plus", "Modérateur+")
    modo = await rbac.create_grade(category.id, "modo", "Modérateur")
    await rbac.add_include(modo_plus.id, op.id)
    await rbac.add_include(modo.id, modo_plus.id)
    return {"op": op.id, "modo_plus": modo_plus.id, "modo": modo.id}


# ══════════════════════════════════════════════════════════════════════════
# 🔧 perm_alpha.py
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_is_op_alpha_recognizes_rbac_member_never_in_legacy_table(patched_get_session):
    """Le cas exact du bug : un membre ajouté SEULEMENT via /dev permissions
    (RBAC), jamais présent dans l'ancienne permission_entries, doit être
    reconnu OP Alpha maintenant que le check lit le RBAC."""
    grades = await _seed_staff_alpha(patched_get_session)
    await rbac.add_member(grades["op"], 42)

    interaction = _fake_interaction(42)
    assert await is_op_alpha(interaction) is True


@pytest.mark.asyncio
async def test_op_member_recognized_as_modo_plus_and_modo_via_inclusion(patched_get_session):
    """Un membre 'op' n'a jamais été ajouté directement à modo_plus/modo —
    l'inclusion RBAC doit suffire, sans OR explicite côté Python."""
    grades = await _seed_staff_alpha(patched_get_session)
    await rbac.add_member(grades["op"], 7)

    interaction = _fake_interaction(7)
    assert await is_op_alpha(interaction) is True
    assert await is_modo_plus(interaction) is True
    assert await is_modo(interaction) is True


@pytest.mark.asyncio
async def test_modo_plus_member_is_not_op(patched_get_session):
    """L'inclusion ne remonte pas : un modo_plus n'est pas automatiquement op."""
    grades = await _seed_staff_alpha(patched_get_session)
    await rbac.add_member(grades["modo_plus"], 8)

    interaction = _fake_interaction(8)
    assert await is_op_alpha(interaction) is False
    assert await is_modo_plus(interaction) is True
    assert await is_modo(interaction) is True


@pytest.mark.asyncio
async def test_dev_grade_grants_op_alpha(patched_get_session):
    """DEV reste au-dessus de toute la hiérarchie staff_alpha (comme avant, mais via RBAC)."""
    await rbac.create_category("staff_alpha", "Staff Alpha")
    dev_cat = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    dev_grade = await rbac.create_grade(dev_cat.id, "dev", "Développeur")
    await rbac.add_member(dev_grade.id, 99)

    interaction = _fake_interaction(99)
    assert await is_op_alpha(interaction) is True
    assert await is_modo_plus(interaction) is True
    assert await is_modo(interaction) is True


@pytest.mark.asyncio
async def test_creator_bypasses_rbac_entirely(patched_get_session):
    await rbac.create_category("staff_alpha", "Staff Alpha")

    interaction = _fake_interaction(555)
    with patch("utils.perm_alpha.is_creator", return_value=True):
        assert await is_op_alpha(interaction) is True


@pytest.mark.asyncio
async def test_check_op_alpha_blocks_unauthorized_with_ephemeral(patched_get_session):
    grades = await _seed_staff_alpha(patched_get_session)
    await rbac.add_member(grades["op"], 1)

    interaction = _fake_interaction(2)  # pas membre
    allowed = await check_op_alpha(interaction, "gérer l'index")

    assert allowed is False
    interaction.response.send_message.assert_awaited_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_check_modo_plus_and_check_modo_allow_via_inclusion(patched_get_session):
    grades = await _seed_staff_alpha(patched_get_session)
    await rbac.add_member(grades["op"], 3)

    interaction = _fake_interaction(3)
    assert await check_modo_plus(interaction, "annoncer un event") is True
    assert await check_modo(interaction, "consulter la liste des events") is True


# ══════════════════════════════════════════════════════════════════════════
# 🔧 perm_dev.py
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_is_dev_recognizes_rbac_member_never_in_legacy_table(patched_get_session):
    dev_cat = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    dev_grade = await rbac.create_grade(dev_cat.id, "dev", "Développeur")
    await rbac.add_member(dev_grade.id, 111)

    interaction = _fake_interaction(111)
    assert await is_dev(interaction) is True


@pytest.mark.asyncio
async def test_check_dev_blocks_unauthorized(patched_get_session):
    dev_cat = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    await rbac.create_grade(dev_cat.id, "dev", "Développeur")

    interaction = _fake_interaction(222)
    allowed = await check_dev(interaction, "consulter le debug")

    assert allowed is False
    interaction.response.send_message.assert_awaited_once()


# ══════════════════════════════════════════════════════════════════════════
# 🔧 perm_staff.py
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_is_staff_recognizes_dev_and_staff_grades(patched_get_session):
    cat = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    dev_grade = await rbac.create_grade(cat.id, "dev", "Développeur")
    staff_grade = await rbac.create_grade(cat.id, "staff", "Staff")
    await rbac.add_member(dev_grade.id, 1)
    await rbac.add_member(staff_grade.id, 2)

    assert await is_staff(_fake_interaction(1)) is True
    assert await is_staff(_fake_interaction(2)) is True
    assert await is_staff(_fake_interaction(3)) is False


@pytest.mark.asyncio
async def test_check_staff_blocks_unauthorized(patched_get_session):
    cat = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    await rbac.create_grade(cat.id, "staff", "Staff")

    interaction = _fake_interaction(9)
    allowed = await check_staff(interaction, "faire ça")

    assert allowed is False
    interaction.response.send_message.assert_awaited_once()
