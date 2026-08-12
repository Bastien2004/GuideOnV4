"""
tests/test_ng_onu_manager.py — Couvre §14 du prompt pour la migration ONU
(phase 8) : chargement par défaut, upsert partiel avec isolation des champs,
isolation multi-serveurs (aucune fuite entre serveurs), cache reflète les
écritures, CRUD de la ping-list.
"""
from __future__ import annotations

import pytest

from utils.managers import ng_onu_manager as mgr


@pytest.mark.asyncio
async def test_load_onu_config_default_when_unset(patched_get_session):
    cfg = await mgr.load_onu_config("alpha")
    assert cfg["server"] == "alpha"
    assert cfg["enabled"] is True
    assert cfg["ping_mp"] is False
    assert cfg["timezone"] == "Europe/Paris"
    assert cfg["channel_id"] is None


@pytest.mark.asyncio
async def test_save_onu_config_partial_upsert_isolates_fields(patched_get_session):
    await mgr.save_onu_config("alpha", channel_id=555)
    cfg = await mgr.save_onu_config("alpha", role_id=777)

    # Le champ précédemment posé (channel_id) doit survivre à un 2e upsert
    # partiel qui ne le mentionne pas.
    assert cfg["channel_id"] == 555
    assert cfg["role_id"] == 777
    assert cfg["jour_onu"] is None


@pytest.mark.asyncio
async def test_save_onu_config_ignores_unknown_fields(patched_get_session):
    cfg = await mgr.save_onu_config("alpha", channel_id=1, not_a_real_field=999)
    assert "not_a_real_field" not in cfg
    assert cfg["channel_id"] == 1


@pytest.mark.asyncio
async def test_multi_server_isolation(patched_get_session):
    await mgr.save_onu_config("alpha", channel_id=100, jour_onu=6)
    await mgr.save_onu_config("delta", channel_id=200, jour_onu=0)

    alpha_cfg = await mgr.load_onu_config("alpha")
    delta_cfg = await mgr.load_onu_config("delta")

    assert alpha_cfg["channel_id"] == 100
    assert alpha_cfg["jour_onu"] == 6
    assert delta_cfg["channel_id"] == 200
    assert delta_cfg["jour_onu"] == 0


@pytest.mark.asyncio
async def test_list_all_onu_configs_returns_every_server(patched_get_session):
    await mgr.save_onu_config("alpha", channel_id=1)
    await mgr.save_onu_config("delta", channel_id=2)

    all_cfgs = await mgr.list_all_onu_configs()
    servers = {c["server"] for c in all_cfgs}
    assert servers == {"alpha", "delta"}


@pytest.mark.asyncio
async def test_cache_reflects_writes_immediately(patched_get_session):
    await mgr.load_onu_config("alpha")  # peuple le cache avec les defaults
    saved = await mgr.save_onu_config("alpha", enabled=False)
    assert saved["enabled"] is False

    # Une lecture immédiate (dans la fenêtre TTL) doit refléter l'écriture,
    # pas l'ancienne valeur en cache.
    reloaded = await mgr.load_onu_config("alpha")
    assert reloaded["enabled"] is False


@pytest.mark.asyncio
async def test_ping_member_add_get_remove(patched_get_session):
    added = await mgr.add_onu_ping_member("alpha", 111)
    assert added is True

    members = await mgr.get_onu_ping_members("alpha")
    assert members == [111]

    # Doublon refusé.
    added_again = await mgr.add_onu_ping_member("alpha", 111)
    assert added_again is False

    removed = await mgr.remove_onu_ping_member("alpha", 111)
    assert removed is True
    assert await mgr.get_onu_ping_members("alpha") == []

    # Retirer un membre absent renvoie False, ne lève pas.
    assert await mgr.remove_onu_ping_member("alpha", 111) is False


@pytest.mark.asyncio
async def test_ping_members_isolated_per_server(patched_get_session):
    await mgr.add_onu_ping_member("alpha", 1)
    await mgr.add_onu_ping_member("delta", 2)

    assert await mgr.get_onu_ping_members("alpha") == [1]
    assert await mgr.get_onu_ping_members("delta") == [2]
