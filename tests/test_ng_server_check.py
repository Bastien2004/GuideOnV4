"""
tests/test_ng_server_check.py — Couvre §14 pour la phase 11 : require_ng_server
(utils/ng_server_check.py), première étape du flow deux temps du dashboard
/ngstaff config (résolution du NGServer depuis interaction.guild_id, avant
même de vérifier un grade RBAC qui dépend du nom du serveur détecté).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.managers import ng_server_manager as ngsrv
from utils.ng_server_check import require_ng_server


def _fake_interaction(guild_id: int | None, *, response_done: bool = False) -> MagicMock:
    interaction = MagicMock()
    interaction.guild_id = guild_id
    interaction.response.is_done.return_value = response_done
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_require_ng_server_resolves_known_guild(patched_get_session):
    await ngsrv.dev_create_server(
        name="delta", display_name="Delta", edition="java", discord_guild_id=1234,
    )

    interaction = _fake_interaction(1234)
    server = await require_ng_server(interaction)

    assert server is not None
    assert server.name == "delta"
    interaction.response.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_require_ng_server_rejects_unknown_guild(patched_get_session):
    await ngsrv.dev_create_server(
        name="delta", display_name="Delta", edition="java", discord_guild_id=1234,
    )

    interaction = _fake_interaction(9999)  # Discord inconnu du cache ng_servers
    server = await require_ng_server(interaction)

    assert server is None
    interaction.response.send_message.assert_awaited_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_require_ng_server_rejects_dm_guild_id_none(patched_get_session):
    await ngsrv.dev_create_server(
        name="delta", display_name="Delta", edition="java", discord_guild_id=1234,
    )

    interaction = _fake_interaction(None)  # DM : guild_id absent
    server = await require_ng_server(interaction)

    assert server is None
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_require_ng_server_uses_followup_if_already_responded(patched_get_session):
    interaction = _fake_interaction(9999, response_done=True)
    server = await require_ng_server(interaction)

    assert server is None
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_require_ng_server_isolates_multiple_guilds(patched_get_session):
    await ngsrv.dev_create_server(
        name="alpha", display_name="Alpha", edition="java", discord_guild_id=111,
    )
    await ngsrv.dev_create_server(
        name="delta", display_name="Delta", edition="java", discord_guild_id=222,
    )

    server_a = await require_ng_server(_fake_interaction(111))
    server_d = await require_ng_server(_fake_interaction(222))

    assert server_a.name == "alpha"
    assert server_d.name == "delta"
