"""
tests/test_ng_nota_manager.py — Couvre §14 du prompt pour la migration
Notations (phase 9) : config par défaut, upsert partiel, isolation
multi-serveurs, état hebdo (reset/historique), présence, et surtout la
logique de répartition (rotation + anti-répétition) qui doit continuer à
fonctionner à l'identique une fois clée par `server` au lieu de `guild_id`.
"""
from __future__ import annotations

import pytest

from utils.db.models.ng_staff import NGStaffMember
from utils.managers import ng_nota_manager as mgr


async def _add_staff(session_factory, *, server: str, discord_id: int, grade: str, pseudo: str = "op"):
    async with session_factory() as session:
        session.add(NGStaffMember(
            server=server, discord_id=discord_id, pseudo_jeu=pseudo, grade=grade,
        ))
        await session.commit()


# ══════════════════════════════════════════════════════════════════════════
# ⚒️ Config
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_load_nota_config_default(patched_get_session):
    cfg = await mgr.load_nota_config("alpha")
    assert cfg["server"] == "alpha"
    assert cfg["countries_count"] == 238
    assert cfg["enabled"] is True


@pytest.mark.asyncio
async def test_save_nota_config_partial_isolates_fields(patched_get_session):
    await mgr.save_nota_config("alpha", channel_staff_id=1)
    cfg = await mgr.save_nota_config("alpha", role_id=2)
    assert cfg["channel_staff_id"] == 1
    assert cfg["role_id"] == 2
    assert cfg["channel_public_id"] is None


@pytest.mark.asyncio
async def test_multi_server_config_isolation(patched_get_session):
    await mgr.save_nota_config("alpha", countries_count=100)
    await mgr.save_nota_config("delta", countries_count=50)
    assert (await mgr.load_nota_config("alpha"))["countries_count"] == 100
    assert (await mgr.load_nota_config("delta"))["countries_count"] == 50


# ══════════════════════════════════════════════════════════════════════════
# 📊 État hebdo
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_load_nota_state_default(patched_get_session):
    state = await mgr.load_nota_state("alpha")
    assert state["server"] == "alpha"
    assert state["availability_message_id"] is None
    assert state["assigned_ranges"] == "[]"


@pytest.mark.asyncio
async def test_set_state_fields_partial(patched_get_session):
    await mgr.set_state_fields("alpha", availability_message_id=999)
    state = await mgr.load_nota_state("alpha")
    assert state["availability_message_id"] == 999
    assert state["reminder_sent"] is False


@pytest.mark.asyncio
async def test_reset_nota_week_clears_availability_and_updates_history(patched_get_session):
    await mgr.toggle_availability("alpha", 1)
    await mgr.toggle_availability("alpha", 2)
    await mgr.set_state_fields("alpha", availability_message_id=1, assigned_ranges="[[1,2,1]]")

    await mgr.reset_nota_week("alpha", [(1, 120, 1), (121, 238, 2)])

    # Disponibilités nettoyées.
    assert await mgr.get_available_operators("alpha") == []

    # État remis à zéro (sentinel prêt pour le prochain cycle).
    state = await mgr.load_nota_state("alpha")
    assert state["availability_message_id"] is None
    assert state["reminder_sent"] is False
    assert state["assigned_ranges"] == "[]"

    # Historique mis à jour.
    history = await mgr.get_operator_history("alpha")
    assert history[1] == (1, 120)
    assert history[2] == (121, 238)


@pytest.mark.asyncio
async def test_state_and_history_isolated_per_server(patched_get_session):
    await mgr.set_state_fields("alpha", availability_message_id=1)
    await mgr.set_state_fields("delta", availability_message_id=2)
    assert (await mgr.load_nota_state("alpha"))["availability_message_id"] == 1
    assert (await mgr.load_nota_state("delta"))["availability_message_id"] == 2

    await mgr.reset_nota_week("alpha", [(1, 10, 100)])
    await mgr.reset_nota_week("delta", [(1, 10, 200)])
    hist_alpha = await mgr.get_operator_history("alpha")
    hist_delta = await mgr.get_operator_history("delta")
    assert 100 in hist_alpha and 100 not in hist_delta
    assert 200 in hist_delta and 200 not in hist_alpha


# ══════════════════════════════════════════════════════════════════════════
# ✅ Présence
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_toggle_availability_add_remove(patched_get_session):
    added, status = await mgr.toggle_availability("alpha", 111)
    assert added is True and "ajouté" in status
    assert await mgr.get_available_operators("alpha") == [111]

    removed, status2 = await mgr.toggle_availability("alpha", 111)
    assert removed is False and "retiré" in status2
    assert await mgr.get_available_operators("alpha") == []


@pytest.mark.asyncio
async def test_availability_isolated_per_server(patched_get_session):
    await mgr.toggle_availability("alpha", 1)
    await mgr.toggle_availability("delta", 2)
    assert await mgr.get_available_operators("alpha") == [1]
    assert await mgr.get_available_operators("delta") == [2]


# ══════════════════════════════════════════════════════════════════════════
# 💻 Opérateurs (lecture staff)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_all_nota_operators_filters_grade_and_server(patched_get_session):
    await _add_staff(patched_get_session, server="alpha", discord_id=1, grade="administrateur")
    await _add_staff(patched_get_session, server="alpha", discord_id=2, grade="super_moderateur")
    await _add_staff(patched_get_session, server="alpha", discord_id=3, grade="guide")  # pas opérateur
    await _add_staff(patched_get_session, server="delta", discord_id=4, grade="administrateur")

    ops = await mgr.get_all_nota_operators("alpha")
    ids = {o["discord_id"] for o in ops}
    assert ids == {1, 2}  # ni le guide, ni delta


# ══════════════════════════════════════════════════════════════════════════
# 📑 Répartition — rotation + anti-répétition (risque identifié §14)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_generate_notation_ranges_basic_split(patched_get_session):
    await _add_staff(patched_get_session, server="alpha", discord_id=1, grade="administrateur")
    await _add_staff(patched_get_session, server="alpha", discord_id=2, grade="super_moderateur")
    await mgr.toggle_availability("alpha", 1)
    await mgr.toggle_availability("alpha", 2)

    assignments = await mgr.generate_notation_ranges("alpha", 10)
    assert len(assignments) == 2
    covered = sorted(a[0] for a in assignments)
    assert covered == [1, 6]  # 10 pays / 2 ops = blocs de 5


@pytest.mark.asyncio
async def test_generate_notation_ranges_no_available_operators(patched_get_session):
    await _add_staff(patched_get_session, server="alpha", discord_id=1, grade="administrateur")
    # Personne n'a togglé sa présence.
    assert await mgr.generate_notation_ranges("alpha", 238) == []


@pytest.mark.asyncio
async def test_generate_notation_ranges_multi_server_isolation(patched_get_session):
    await _add_staff(patched_get_session, server="alpha", discord_id=1, grade="administrateur")
    await _add_staff(patched_get_session, server="delta", discord_id=2, grade="administrateur")
    await mgr.toggle_availability("alpha", 1)
    await mgr.toggle_availability("alpha", 2)  # dispo côté alpha mais pas staff alpha

    assignments = await mgr.generate_notation_ranges("alpha", 100)
    assigned_ids = {a[2] for a in assignments}
    assert assigned_ids == {1}  # le user 2 n'est pas opérateur *alpha*, donc ignoré


@pytest.mark.asyncio
async def test_generate_notation_ranges_rotation_after_history(patched_get_session):
    """Sans historique, l'ordre suit le tri par discord_id/pseudo (stable). Avec
    historique, le premier de la semaine précédente passe en dernier (rotation)."""
    await _add_staff(patched_get_session, server="alpha", discord_id=1, grade="administrateur")
    await _add_staff(patched_get_session, server="alpha", discord_id=2, grade="super_moderateur")
    await mgr.toggle_availability("alpha", 1)
    await mgr.toggle_availability("alpha", 2)

    first_week = await mgr.generate_notation_ranges("alpha", 10)
    await mgr.reset_nota_week("alpha", first_week)

    # Rejouer une 2e semaine (dispo à nouveau) : l'opérateur en tête de la
    # semaine précédente doit être décalé en fin de rotation.
    await mgr.toggle_availability("alpha", 1)
    await mgr.toggle_availability("alpha", 2)
    second_week = await mgr.generate_notation_ranges("alpha", 10)

    first_order = [a[2] for a in first_week]
    second_order = [a[2] for a in second_week]
    assert first_order != second_order or len(first_order) < 2  # rotation effective
