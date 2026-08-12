"""
tests/test_ng_role_react_manager.py — Couvre §14 du prompt pour la
migration Rôle Réaction (phase 10) : config par défaut, upsert partiel,
isolation multi-serveurs, CRUD des entrées (MAX_ROLES, doublons, positions),
et la garantie FK cascade (§4.2 : NGRoleReactCouple.server -> FK réelle vers
NGRoleReaction.server) sans casser le flux existant où un rôle pouvait être
ajouté avant même qu'un salon soit configuré.
"""
from __future__ import annotations

import pytest

from utils.managers import ng_role_react_manager as mgr


@pytest.mark.asyncio
async def test_load_rr_config_default(patched_get_session):
    cfg = await mgr.load_rr_config("alpha")
    assert cfg == {"server": "alpha", "channel_id": None, "message_id": None}


@pytest.mark.asyncio
async def test_save_rr_config_partial_isolates_fields(patched_get_session):
    await mgr.save_rr_config("alpha", channel_id=111)
    cfg = await mgr.save_rr_config("alpha", message_id=222)
    assert cfg["channel_id"] == 111
    assert cfg["message_id"] == 222


@pytest.mark.asyncio
async def test_multi_server_config_isolation(patched_get_session):
    await mgr.save_rr_config("alpha", channel_id=1)
    await mgr.save_rr_config("delta", channel_id=2)
    assert (await mgr.load_rr_config("alpha"))["channel_id"] == 1
    assert (await mgr.load_rr_config("delta"))["channel_id"] == 2


# ══════════════════════════════════════════════════════════════════════════
# 🎭 Entrées — CRUD de base
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_add_rr_entry_without_prior_config_row(patched_get_session):
    """Le flux historique (ajouter un rôle avant tout salon configuré) doit
    continuer à fonctionner malgré la FK cascade — get-or-create de la
    ligne parente NGRoleReaction."""
    ok = await mgr.add_rr_entry("alpha", role_id=555, label="Fan")
    assert ok is True

    entries = await mgr.get_rr_entries("alpha")
    assert len(entries) == 1
    assert entries[0]["role_id"] == 555
    assert entries[0]["position"] == 0

    # La ligne parente a bien été créée en creux.
    cfg = await mgr.load_rr_config("alpha")
    assert cfg["server"] == "alpha"


@pytest.mark.asyncio
async def test_add_rr_entry_rejects_duplicate_role(patched_get_session):
    assert await mgr.add_rr_entry("alpha", role_id=1, label="A") is True
    assert await mgr.add_rr_entry("alpha", role_id=1, label="A bis") is False
    assert await mgr.get_rr_entry_count("alpha") == 1


@pytest.mark.asyncio
async def test_add_rr_entry_respects_max_roles(patched_get_session):
    for i in range(mgr.MAX_ROLES):
        assert await mgr.add_rr_entry("alpha", role_id=1000 + i, label=f"R{i}") is True
    assert await mgr.get_rr_entry_count("alpha") == mgr.MAX_ROLES

    # Le 11e est refusé.
    assert await mgr.add_rr_entry("alpha", role_id=9999, label="Trop") is False
    assert await mgr.get_rr_entry_count("alpha") == mgr.MAX_ROLES


@pytest.mark.asyncio
async def test_add_rr_entry_reuses_freed_position(patched_get_session):
    await mgr.add_rr_entry("alpha", role_id=1, label="A")
    await mgr.add_rr_entry("alpha", role_id=2, label="B")
    entries = await mgr.get_rr_entries("alpha")
    entry_a = next(e for e in entries if e["role_id"] == 1)

    await mgr.remove_rr_entry("alpha", entry_a["id"])
    await mgr.add_rr_entry("alpha", role_id=3, label="C")

    entries = await mgr.get_rr_entries("alpha")
    positions = sorted(e["position"] for e in entries)
    assert positions == [0, 1]  # la position 0 libérée par A est réutilisée


@pytest.mark.asyncio
async def test_remove_rr_entry_unknown_returns_false(patched_get_session):
    assert await mgr.remove_rr_entry("alpha", 9999) is False


@pytest.mark.asyncio
async def test_update_rr_entry_fields(patched_get_session):
    await mgr.add_rr_entry("alpha", role_id=1, label="Old", emoji=None, description=None)
    entry = (await mgr.get_rr_entries("alpha"))[0]

    ok = await mgr.update_rr_entry("alpha", entry["id"], label="New", emoji="🔥")
    assert ok is True

    updated = (await mgr.get_rr_entries("alpha"))[0]
    assert updated["label"] == "New"
    assert updated["emoji"] == "🔥"


@pytest.mark.asyncio
async def test_update_rr_entry_unknown_returns_false(patched_get_session):
    assert await mgr.update_rr_entry("alpha", 9999, label="X") is False


@pytest.mark.asyncio
async def test_update_rr_entry_no_allowed_fields_returns_false(patched_get_session):
    await mgr.add_rr_entry("alpha", role_id=1, label="A")
    entry = (await mgr.get_rr_entries("alpha"))[0]
    assert await mgr.update_rr_entry("alpha", entry["id"], role_id=999) is False


# ══════════════════════════════════════════════════════════════════════════
# 🌐 Isolation multi-serveurs
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_entries_isolated_per_server(patched_get_session):
    await mgr.add_rr_entry("alpha", role_id=1, label="A")
    await mgr.add_rr_entry("delta", role_id=1, label="A-delta")  # même role_id, autre serveur -> OK

    alpha_entries = await mgr.get_rr_entries("alpha")
    delta_entries = await mgr.get_rr_entries("delta")
    assert len(alpha_entries) == 1
    assert len(delta_entries) == 1
    assert alpha_entries[0]["label"] == "A"
    assert delta_entries[0]["label"] == "A-delta"


@pytest.mark.asyncio
async def test_max_roles_isolated_per_server(patched_get_session):
    """Remplir alpha à MAX_ROLES ne doit pas affecter la capacité de delta."""
    for i in range(mgr.MAX_ROLES):
        await mgr.add_rr_entry("alpha", role_id=i, label=f"A{i}")
    assert await mgr.add_rr_entry("alpha", role_id=999, label="Trop") is False

    # delta démarre à zéro, indépendant du remplissage d'alpha.
    assert await mgr.add_rr_entry("delta", role_id=0, label="D0") is True
    assert await mgr.get_rr_entry_count("delta") == 1


# ══════════════════════════════════════════════════════════════════════════
# 📦 Cache
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cache_reflects_writes(patched_get_session):
    await mgr.load_rr_config("alpha")  # peuple le cache config
    await mgr.get_rr_entries("alpha")  # peuple le cache liste

    await mgr.save_rr_config("alpha", channel_id=777)
    await mgr.add_rr_entry("alpha", role_id=1, label="A")

    cfg = await mgr.load_rr_config("alpha")
    entries = await mgr.get_rr_entries("alpha")
    assert cfg["channel_id"] == 777
    assert len(entries) == 1
