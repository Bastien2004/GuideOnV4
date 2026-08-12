"""
tests/test_dev_permissions_cog.py — Couvre le garde d'accès de /dev
permissions (phase 4) : is_creator (garde-fou) OU grade equipe_guideon.dev.
Ne teste pas l'envoi Discord (defer/followup) — seulement `_is_authorized`,
la fonction qui aurait empêché la régression du bug pré-existant
(`await is_creator(interaction)` sur une fonction sync prenant un int).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cogs.dev.permission import _is_authorized
from utils.createur import CREATOR_IDS
from utils.managers import permission_rbac_manager as rbac


def _fake_interaction(user_id: int) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = user_id
    return interaction


@pytest.mark.asyncio
async def test_creator_bypass(patched_get_session):
    creator_id = next(iter(CREATOR_IDS))
    interaction = _fake_interaction(creator_id)
    assert await _is_authorized(interaction) is True


@pytest.mark.asyncio
async def test_dev_grade_member_authorized(patched_get_session):
    category = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    dev = await rbac.create_grade(category.id, "dev", "Développeur")
    await rbac.add_member(dev.id, 12345)

    interaction = _fake_interaction(12345)
    assert await _is_authorized(interaction) is True


@pytest.mark.asyncio
async def test_random_user_not_authorized(patched_get_session):
    await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    interaction = _fake_interaction(99999999)
    assert await _is_authorized(interaction) is False


@pytest.mark.asyncio
async def test_no_dev_grade_in_db_does_not_crash(patched_get_session):
    """Aucune catégorie equipe_guideon en base -> refuse proprement, pas d'exception."""
    interaction = _fake_interaction(99999999)
    assert await _is_authorized(interaction) is False
