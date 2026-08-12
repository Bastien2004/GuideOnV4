"""
tests/test_ng_server_manager_dev_write.py — Écritures ng_servers réservées à
/dev setng et /dev unsetng (phase 5) : création, conflits name/guild_id,
suppression, et rechargement automatique du cache après écriture.
"""
from __future__ import annotations

import pytest

from utils.managers import ng_server_manager as mgr
from utils.managers.ng_server_manager import (
    NGServerGuildConflictError,
    NGServerNameConflictError,
    dev_create_server,
    dev_delete_server_by_guild,
)


@pytest.mark.asyncio
async def test_dev_create_server_success_and_cache_reload(patched_get_session):
    server = await dev_create_server(
        name="delta", display_name="Delta", edition="bedrock", discord_guild_id=111,
    )
    assert server.name == "delta"
    assert server.discord_guild_id == 111

    # Le cache doit déjà refléter la création, sans reload_cache() manuel.
    assert mgr.get_server_by_name("delta") is not None
    assert mgr.get_server_by_guild(111) is not None


@pytest.mark.asyncio
async def test_dev_create_server_name_conflict(patched_get_session):
    await dev_create_server(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=111)

    with pytest.raises(NGServerNameConflictError):
        await dev_create_server(name="alpha", display_name="Alpha (bis)", edition="bedrock", discord_guild_id=222)


@pytest.mark.asyncio
async def test_dev_create_server_guild_conflict(patched_get_session):
    await dev_create_server(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=111)

    with pytest.raises(NGServerGuildConflictError):
        await dev_create_server(name="sigma", display_name="Sigma", edition="bedrock", discord_guild_id=111)


@pytest.mark.asyncio
async def test_dev_delete_server_by_guild(patched_get_session):
    await dev_create_server(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=111)

    removed = await dev_delete_server_by_guild(111)
    assert removed is not None
    assert removed.name == "alpha"

    # Cache mis à jour immédiatement.
    assert mgr.get_server_by_guild(111) is None
    assert mgr.get_server_by_name("alpha") is None


@pytest.mark.asyncio
async def test_dev_delete_server_by_guild_not_found(patched_get_session):
    removed = await dev_delete_server_by_guild(999999)
    assert removed is None


@pytest.mark.asyncio
async def test_dev_create_after_delete_is_allowed(patched_get_session):
    """Un guild_id libéré par unsetng doit pouvoir simuler un autre serveur NG."""
    await dev_create_server(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=111)
    await dev_delete_server_by_guild(111)

    server = await dev_create_server(name="sigma", display_name="Sigma", edition="bedrock", discord_guild_id=111)
    assert server.name == "sigma"
    assert mgr.get_server_by_guild(111).name == "sigma"
