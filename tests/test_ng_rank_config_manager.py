"""
tests/test_ng_rank_config_manager.py — Couvre le manager de config rank
multi-serveurs (phase 7, ex-alpha_rank_config_manager) : valeurs par défaut,
upsert partiel, isolation par serveur, cache.
"""
from __future__ import annotations

import pytest

from utils.managers import ng_rank_config_manager as cfgmgr


@pytest.mark.asyncio
async def test_load_default_when_not_configured(patched_get_session):
    cfg = await cfgmgr.load_rank_config("alpha")
    assert cfg["server"] == "alpha"
    assert cfg["rank_channel_id"] is None
    assert cfg["role_administrateur_id"] is None


@pytest.mark.asyncio
async def test_save_partial_upsert_creates_row(patched_get_session):
    cfg = await cfgmgr.save_rank_config("alpha", rank_channel_id=111)
    assert cfg["rank_channel_id"] == 111
    assert cfg["dev_channel_id"] is None  # non fourni, reste au défaut


@pytest.mark.asyncio
async def test_save_partial_upsert_only_touches_given_fields(patched_get_session):
    await cfgmgr.save_rank_config("alpha", rank_channel_id=111, role_guide_id=222)
    cfg = await cfgmgr.save_rank_config("alpha", role_guide_id=333)

    assert cfg["role_guide_id"] == 333
    assert cfg["rank_channel_id"] == 111  # inchangé


@pytest.mark.asyncio
async def test_save_ignores_unknown_fields(patched_get_session):
    cfg = await cfgmgr.save_rank_config("alpha", rank_channel_id=111, champ_inconnu="x")
    assert "champ_inconnu" not in cfg
    assert cfg["rank_channel_id"] == 111


@pytest.mark.asyncio
async def test_isolation_between_servers(patched_get_session):
    await cfgmgr.save_rank_config("alpha", rank_channel_id=111)
    await cfgmgr.save_rank_config("delta", rank_channel_id=222)

    alpha_cfg = await cfgmgr.load_rank_config("alpha")
    delta_cfg = await cfgmgr.load_rank_config("delta")

    assert alpha_cfg["rank_channel_id"] == 111
    assert delta_cfg["rank_channel_id"] == 222


@pytest.mark.asyncio
async def test_get_rank_config_obj(patched_get_session):
    assert await cfgmgr.get_rank_config_obj("alpha") is None

    await cfgmgr.save_rank_config("alpha", rank_channel_id=111)
    obj = await cfgmgr.get_rank_config_obj("alpha")
    assert obj is not None
    assert obj.server == "alpha"
    assert obj.rank_channel_id == 111


@pytest.mark.asyncio
async def test_cache_reflects_writes(patched_get_session):
    await cfgmgr.load_rank_config("alpha")  # force un premier chargement (défaut)
    await cfgmgr.save_rank_config("alpha", rank_channel_id=999)
    cfg = await cfgmgr.load_rank_config("alpha")
    assert cfg["rank_channel_id"] == 999
