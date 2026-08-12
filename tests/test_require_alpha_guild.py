"""
tests/test_require_alpha_guild.py — Couvre §14 pour la phase 13 :
require_alpha_guild (utils/perm_alpha.py), garde-fou défense-en-profondeur
qui protège les commandes "systèmes particuliers" (/alpha config_alpha,
index, regle_interne, nous_rejoindre, event_start/regle/list) — elles ne
sont enregistrées que sur le Discord Alpha en usage normal (bot.py), mais
ce garde vérifie explicitement `server.name == "alpha"` à l'exécution,
au cas où un câblage futur viendrait à les synchroniser ailleurs.

Miroir de tests/test_ng_server_check.py (phase 11), mais avec la logique
inversée : on rejette *sauf* si le serveur résolu est "alpha" (pas
n'importe quel serveur NG connu).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.managers import ng_server_manager as ngsrv
from utils.perm_alpha import require_alpha_guild


def _fake_interaction(guild_id: int | None, *, response_done: bool = False) -> MagicMock:
    interaction = MagicMock()
    interaction.guild_id = guild_id
    interaction.response.is_done.return_value = response_done
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_require_alpha_guild_allows_alpha_guild(patched_get_session):
    await ngsrv.dev_create_server(
        name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=111,
    )

    interaction = _fake_interaction(111)
    ok = await require_alpha_guild(interaction)

    assert ok is True
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_not_called()


@pytest.mark.asyncio
async def test_require_alpha_guild_blocks_other_ng_server(patched_get_session):
    """Un Discord NG valide (ex: delta) mais qui n'est pas Alpha doit être
    bloqué — ce n'est pas parce qu'un serveur est un Discord NG connu qu'il
    a le droit d'utiliser les commandes "systèmes particuliers" Alpha."""
    await ngsrv.dev_create_server(
        name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=111,
    )
    await ngsrv.dev_create_server(
        name="delta", display_name="Delta", edition="java", discord_guild_id=222,
    )

    interaction = _fake_interaction(222)
    ok = await require_alpha_guild(interaction)

    assert ok is False
    interaction.response.send_message.assert_awaited_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_require_alpha_guild_blocks_unknown_guild(patched_get_session):
    await ngsrv.dev_create_server(
        name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=111,
    )

    interaction = _fake_interaction(999)  # Discord totalement inconnu du cache ng_servers
    ok = await require_alpha_guild(interaction)

    assert ok is False
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_require_alpha_guild_blocks_dm_guild_id_none(patched_get_session):
    await ngsrv.dev_create_server(
        name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=111,
    )

    interaction = _fake_interaction(None)  # DM : guild_id absent
    ok = await require_alpha_guild(interaction)

    assert ok is False
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_require_alpha_guild_uses_followup_if_already_responded(patched_get_session):
    interaction = _fake_interaction(222, response_done=True)
    ok = await require_alpha_guild(interaction)

    assert ok is False
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_awaited_once()
