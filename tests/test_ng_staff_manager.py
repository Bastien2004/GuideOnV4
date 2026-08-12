"""
tests/test_ng_staff_manager.py — Couvre §14 du prompt de refonte pour la
migration ng_staff (phase 6) : isolation multi-serveurs, cache.

Refonte multi-serveurs, phase 15 (nettoyage legacy) : la suite de tests
"resync_server_from_alpha_staff" a été retirée en même temps que la
fonction elle-même (utils/managers/ng_staff_manager.py) et le modèle ORM
AlphaStaffMember (utils/db/models/alpha_staff.py) — c'était un outil de
préparation pré-phase-7 ("resync à la demande, pas un cutover"), jamais
câblé à une commande, et rendu obsolète par le vrai cutover Alembic de
phase 7 (voir migrations/versions/*_ng_staff.py et PHASE_7.md).
"""
from __future__ import annotations

import pytest

from utils.db.models.ng_server import NGServer
from utils.managers import ng_staff_manager as ng_staff


async def _seed_ng_servers(session_factory):
    async with session_factory() as session:
        session.add_all([
            NGServer(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=1, active=True),
            NGServer(name="delta", display_name="Delta", edition="bedrock", discord_guild_id=2, active=True),
        ])
        await session.commit()



# ══════════════════════════════════════════════════════════════════════════
# 📖 CRUD de base + isolation multi-serveurs
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_add_and_get_staff_member(patched_get_session):
    await _seed_ng_servers(patched_get_session)

    created = await ng_staff.add_staff_member("alpha", 111, "PseudoA", "guide")
    assert created is True

    member = await ng_staff.get_staff_member("alpha", 111)
    assert member is not None
    assert member["pseudo_jeu"] == "PseudoA"
    assert member["grade"] == "guide"


@pytest.mark.asyncio
async def test_add_staff_member_duplicate_returns_false(patched_get_session):
    await _seed_ng_servers(patched_get_session)
    await ng_staff.add_staff_member("alpha", 111, "PseudoA", "guide")
    assert await ng_staff.add_staff_member("alpha", 111, "Autre", "guide") is False


@pytest.mark.asyncio
async def test_same_discord_id_isolated_per_server(patched_get_session):
    """Le même discord_id peut être staff sur deux serveurs NG différents
    (PK composite (server, discord_id)) — aucune fuite entre serveurs."""
    await _seed_ng_servers(patched_get_session)

    await ng_staff.add_staff_member("alpha", 111, "PseudoAlpha", "guide")
    await ng_staff.add_staff_member("delta", 111, "PseudoDelta", "administrateur")

    alpha_member = await ng_staff.get_staff_member("alpha", 111)
    delta_member = await ng_staff.get_staff_member("delta", 111)

    assert alpha_member["pseudo_jeu"] == "PseudoAlpha"
    assert alpha_member["grade"] == "guide"
    assert delta_member["pseudo_jeu"] == "PseudoDelta"
    assert delta_member["grade"] == "administrateur"

    assert [m["discord_id"] for m in await ng_staff.list_staff("alpha")] == [111]
    assert [m["discord_id"] for m in await ng_staff.list_staff("delta")] == [111]


@pytest.mark.asyncio
async def test_update_and_remove_staff_member(patched_get_session):
    await _seed_ng_servers(patched_get_session)
    await ng_staff.add_staff_member("alpha", 111, "PseudoA", "guide")

    updated = await ng_staff.update_staff_member("alpha", 111, grade="administrateur")
    assert updated is True
    assert (await ng_staff.get_staff_member("alpha", 111))["grade"] == "administrateur"

    assert await ng_staff.update_staff_member("alpha", 999, grade="guide") is False  # absent

    removed = await ng_staff.remove_staff_member("alpha", 111)
    assert removed is True
    assert await ng_staff.get_staff_member("alpha", 111) is None
    assert await ng_staff.remove_staff_member("alpha", 111) is False  # déjà absent


@pytest.mark.asyncio
async def test_upsert_creates_then_updates(patched_get_session):
    await _seed_ng_servers(patched_get_session)

    created = await ng_staff.upsert_staff_member("alpha", 111, "PseudoA", "guide")
    assert created is True

    created_again = await ng_staff.upsert_staff_member("alpha", 111, "PseudoA modifié", "administrateur")
    assert created_again is False
    member = await ng_staff.get_staff_member("alpha", 111)
    assert member["pseudo_jeu"] == "PseudoA modifié"
    assert member["grade"] == "administrateur"


@pytest.mark.asyncio
async def test_cache_reflects_writes_without_manual_invalidation(patched_get_session):
    await _seed_ng_servers(patched_get_session)
    await ng_staff.list_staff("alpha")  # force un premier chargement du cache

    await ng_staff.add_staff_member("alpha", 111, "PseudoA", "guide")
    members = await ng_staff.list_staff("alpha")
    assert len(members) == 1

