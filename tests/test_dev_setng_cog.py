"""
tests/test_dev_setng_cog.py — Garde de /dev setng et /dev unsetng (phase 5) :
refus systématique hors env=dev (même pour un créateur/dev), et grade requis
sinon. Le refus "hors dev" doit primer sur tout le reste (§9 du prompt :
"Vérifie settings.env == 'dev' (refuse en prod)" est la première étape).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from cogs.dev.setng import _guard
from utils.createur import CREATOR_IDS
from utils.managers import permission_rbac_manager as rbac
from utils.settings import settings


def _fake_interaction(user_id: int) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture(autouse=True)
def _reset_env():
    original = settings.env
    yield
    settings.env = original


@pytest.mark.asyncio
async def test_guard_blocks_in_prod_even_for_creator(patched_get_session):
    settings.env = "prod"
    creator_id = next(iter(CREATOR_IDS))
    interaction = _fake_interaction(creator_id)

    assert await _guard(interaction) is False
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_guard_blocks_dev_without_grade(patched_get_session):
    settings.env = "dev"
    interaction = _fake_interaction(99999999)

    assert await _guard(interaction) is False


@pytest.mark.asyncio
async def test_guard_allows_dev_with_grade(patched_get_session):
    settings.env = "dev"
    category = await rbac.create_category("equipe_guideon", "Équipe GuideOn")
    dev_grade = await rbac.create_grade(category.id, "dev", "Développeur")
    await rbac.add_member(dev_grade.id, 42)

    interaction = _fake_interaction(42)
    assert await _guard(interaction) is True


@pytest.mark.asyncio
async def test_guard_allows_dev_with_creator_bypass(patched_get_session):
    settings.env = "dev"
    creator_id = next(iter(CREATOR_IDS))
    interaction = _fake_interaction(creator_id)

    assert await _guard(interaction) is True
