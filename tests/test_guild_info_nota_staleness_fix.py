"""
tests/test_guild_info_nota_staleness_fix.py — Couvre §14 pour la phase 15
(nettoyage legacy) : utils.guild_info.detect_modules lisait auparavant
l'ancien alpha_nota_manager.load_nota_config(guild_id) (table gelée depuis
la bascule de phase 9) pour détecter si le module "Notations" est
configuré. Corrigé pour lire ng_nota_manager (server-keyed, vivant).

list_panels (ticket_manager) et load_birthday_config (birthday_manager)
sont mockés directement : ces deux managers ne font pas partie du
fixture partagé patched_get_session (conftest.py) et tenteraient sinon
une vraie connexion Postgres, sans rapport avec ce qui est testé ici.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from utils.guild_info import detect_modules
from utils.managers import ng_server_manager as ngsrv
from utils.managers.ng_nota_manager import save_nota_config


@pytest.mark.asyncio
async def test_detect_modules_reads_ng_nota_manager_not_frozen_legacy(patched_get_session):
    await ngsrv.dev_create_server(
        name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=1000,
    )
    await save_nota_config("alpha", enabled=True)

    with patch("utils.guild_info.list_panels", new=AsyncMock(return_value=[])), \
         patch("utils.guild_info.load_birthday_config", new=AsyncMock(return_value={})):
        modules = await detect_modules(1000)

    assert modules["Notations"] is True


@pytest.mark.asyncio
async def test_detect_modules_notations_false_when_disabled(patched_get_session):
    await ngsrv.dev_create_server(
        name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=1001,
    )
    await save_nota_config("alpha", enabled=False)

    with patch("utils.guild_info.list_panels", new=AsyncMock(return_value=[])), \
         patch("utils.guild_info.load_birthday_config", new=AsyncMock(return_value={})):
        modules = await detect_modules(1001)

    assert modules["Notations"] is False


@pytest.mark.asyncio
async def test_detect_modules_unknown_guild_does_not_crash(patched_get_session):
    """guild_id qui n'est pas un Discord NG connu -> ng_server est None ->
    ne doit pas tenter de résoudre nota_cfg (sinon AttributeError sur None.name)."""
    with patch("utils.guild_info.list_panels", new=AsyncMock(return_value=[])), \
         patch("utils.guild_info.load_birthday_config", new=AsyncMock(return_value={})):
        modules = await detect_modules(9999)

    assert modules["Notations"] is False
    assert modules["Alpha"] is False
