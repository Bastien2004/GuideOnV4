"""
tests/test_ng_server_manager.py — Couvre §14 du prompt de refonte pour
ng_servers : reload cache, lookup guild->server, insertion nouveau serveur,
isolation dev/prod (implicite : chaque test a sa propre DB en mémoire).
"""
from __future__ import annotations

import pytest

from utils.db.models.ng_server import NGServer
from utils.managers import ng_server_manager as mgr


async def _insert_server(session_factory, **kwargs):
    async with session_factory() as session:
        session.add(NGServer(**kwargs))
        await session.commit()


@pytest.mark.asyncio
async def test_cache_not_ready_before_first_reload(patched_get_session):
    assert mgr.cache_is_ready() is False
    assert mgr.get_server_by_guild(123) is None
    assert mgr.get_server_by_name("alpha") is None
    assert mgr.list_active_servers() == []


@pytest.mark.asyncio
async def test_reload_cache_and_lookup(patched_get_session):
    await _insert_server(
        patched_get_session,
        name="alpha", display_name="Alpha", edition="bedrock",
        discord_guild_id=111, active=True,
    )
    await _insert_server(
        patched_get_session,
        name="delta", display_name="Delta", edition="bedrock",
        discord_guild_id=222, active=False,
    )

    await mgr.reload_cache()

    assert mgr.cache_is_ready() is True

    alpha = mgr.get_server_by_guild(111)
    assert alpha is not None
    assert alpha.name == "alpha"

    assert mgr.get_server_by_guild(999) is None

    by_name = mgr.get_server_by_name("delta")
    assert by_name is not None
    assert by_name.discord_guild_id == 222

    assert mgr.get_server_by_name("omega") is None


@pytest.mark.asyncio
async def test_list_active_servers_excludes_inactive(patched_get_session):
    await _insert_server(
        patched_get_session,
        name="alpha", display_name="Alpha", edition="bedrock",
        discord_guild_id=111, active=True,
    )
    await _insert_server(
        patched_get_session,
        name="delta", display_name="Delta", edition="bedrock",
        discord_guild_id=222, active=False,
    )

    await mgr.reload_cache()
    active = mgr.list_active_servers()

    assert [s.name for s in active] == ["alpha"]


@pytest.mark.asyncio
async def test_reload_cache_picks_up_new_server(patched_get_session):
    await _insert_server(
        patched_get_session,
        name="alpha", display_name="Alpha", edition="bedrock",
        discord_guild_id=111, active=True,
    )
    await mgr.reload_cache()
    assert mgr.get_server_by_name("sigma") is None

    await _insert_server(
        patched_get_session,
        name="sigma", display_name="Sigma", edition="bedrock",
        discord_guild_id=333, active=True,
    )
    await mgr.reload_cache()

    sigma = mgr.get_server_by_name("sigma")
    assert sigma is not None
    assert sigma.discord_guild_id == 333


@pytest.mark.asyncio
async def test_reload_cache_keeps_old_cache_on_db_error(patched_get_session, monkeypatch):
    await _insert_server(
        patched_get_session,
        name="alpha", display_name="Alpha", edition="bedrock",
        discord_guild_id=111, active=True,
    )
    await mgr.reload_cache()
    assert mgr.get_server_by_name("alpha") is not None

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _broken_get_session():
        raise RuntimeError("DB down")
        yield  # pragma: no cover

    monkeypatch.setattr(mgr, "get_session", _broken_get_session)

    await mgr.reload_cache()  # ne doit pas lever, doit garder l'ancien cache
    assert mgr.get_server_by_name("alpha") is not None
