"""
tests/test_perm_check.py — Couvre §14 : requires_grade bloque correctement
les non-autorisés et laisse passer les autorisés (directs + via inclusion).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.managers import permission_rbac_manager as rbac
from utils.perm_check import has_grade_check, requires_grade


def _fake_interaction(user_id: int, *, response_done: bool = False) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response.is_done.return_value = response_done
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_has_grade_check_allows_authorized_user(patched_get_session):
    category = await rbac.create_category("staff_alpha", "Staff Alpha")
    admin = await rbac.create_grade(category.id, "admin", "Administrateur")
    await rbac.add_member(admin.id, 42)

    interaction = _fake_interaction(42)
    allowed = await has_grade_check(interaction, "staff_alpha.admin")

    assert allowed is True
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_not_called()


@pytest.mark.asyncio
async def test_has_grade_check_blocks_unauthorized_user(patched_get_session):
    category = await rbac.create_category("staff_alpha", "Staff Alpha")
    admin = await rbac.create_grade(category.id, "admin", "Administrateur")
    await rbac.add_member(admin.id, 42)

    interaction = _fake_interaction(999)  # pas membre
    allowed = await has_grade_check(interaction, "staff_alpha.admin")

    assert allowed is False
    interaction.response.send_message.assert_awaited_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_has_grade_check_uses_followup_if_already_responded(patched_get_session):
    category = await rbac.create_category("staff_alpha", "Staff Alpha")
    await rbac.create_grade(category.id, "admin", "Administrateur")

    interaction = _fake_interaction(999, response_done=True)
    allowed = await has_grade_check(interaction, "staff_alpha.admin")

    assert allowed is False
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_requires_grade_decorator_predicate(patched_get_session):
    category = await rbac.create_category("staff_alpha", "Staff Alpha")
    admin = await rbac.create_grade(category.id, "admin", "Administrateur")
    await rbac.add_member(admin.id, 42)

    async def dummy_command(interaction):  # pragma: no cover - jamais appelé ici
        return "ok"

    decorated = requires_grade("staff_alpha.admin")(dummy_command)

    # app_commands.check stocke le predicate sur __discord_app_commands_checks__
    # (voir discord.app_commands.check) quand la cible n'est pas encore un
    # objet Command (cas normal : le décorateur @app_commands.command
    # tourne au-dessus dans le code réel, donc au-dessous ici à l'exécution).
    checks = decorated.__discord_app_commands_checks__
    assert len(checks) == 1
    predicate = checks[0]

    allowed_interaction = _fake_interaction(42)
    assert await predicate(allowed_interaction) is True

    blocked_interaction = _fake_interaction(1)
    assert await predicate(blocked_interaction) is False
    blocked_interaction.response.send_message.assert_awaited_once()
