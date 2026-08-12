"""
tests/test_ngstaff_config_dashboard.py — Couvre §14 pour la phase 11 :
généralisation des 4 vues de config (Rank, ONU, Notations, Role-React) au
paramètre `server` + marqueur `dashboard`, dashboard /ngstaff config
(4 systèmes, serveur dynamique), et régression du bug pré-existant du
dashboard /alpha config_alpha (branches onu/notations/role_react qui
appelaient encore les managers alpha_* morts au lieu de ng_*).

Les managers alpha_onu_manager et alpha_role_react_manager ne sont PAS
monkeypatchés dans conftest.patched_get_session (contrairement à
alpha_nota_manager, resté patché pour d'autres tests) : si une des
branches du dashboard les appelait encore, l'appel tenterait une vraie
connexion Postgres et l'test échouerait/lèverait — c'est exactement ce
qui sert de garde-fou de non-régression ici.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.managers.ng_nota_manager import save_nota_config
from utils.managers.ng_onu_manager import save_onu_config
from utils.managers.ng_rank_config_manager import save_rank_config
from utils.managers.ng_role_react_manager import add_rr_entry, save_rr_config
from views.alpha.config_alpha_view import ConfigRankView
from views.alpha.config_dashboard_view import ConfigDashboardView
from views.alpha.config_nota_view import NotaConfigView
from views.alpha.config_onu_view import ONUConfigView
from views.alpha.config_role_react_view import RoleReactConfigView
from views.ngstaff.config_dashboard_view import NGStaffConfigDashboardView


def _fake_interaction(value: str | None = None) -> MagicMock:
    interaction = MagicMock()
    if value is not None:
        interaction.data = {"values": [value]}
    interaction.response.edit_message = AsyncMock()
    return interaction


# ══════════════════════════════════════════════════════════════════════════
# 🔁 Routing "Tableau de bord" : dashboard="alpha" vs dashboard="ngstaff"
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_config_rank_view_back_routes_to_alpha_dashboard_by_default(patched_get_session):
    view = ConfigRankView(111, "alpha", {}, 222)  # dashboard="alpha" par défaut
    interaction = _fake_interaction()

    await view._on_back_dash(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    assert isinstance(kwargs["view"], ConfigDashboardView)


@pytest.mark.asyncio
async def test_config_rank_view_back_routes_to_ngstaff_dashboard(patched_get_session):
    view = ConfigRankView(111, "delta", {}, 222, dashboard="ngstaff")
    interaction = _fake_interaction()

    await view._on_back_dash(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    dashboard_view = kwargs["view"]
    assert isinstance(dashboard_view, NGStaffConfigDashboardView)
    assert dashboard_view.server == "delta"
    assert dashboard_view.guild_id == 111
    assert dashboard_view.owner_id == 222


@pytest.mark.asyncio
async def test_onu_config_view_back_routes_to_alpha_dashboard_by_default(patched_get_session):
    alpha_view = ONUConfigView(1, "alpha", {}, 2)
    interaction = _fake_interaction()
    await alpha_view._on_back(interaction)
    kwargs = interaction.response.edit_message.call_args.kwargs
    assert isinstance(kwargs["view"], ConfigDashboardView)


@pytest.mark.asyncio
async def test_onu_config_view_back_routes_to_ngstaff_dashboard(patched_get_session):
    ngstaff_view = ONUConfigView(1, "delta", {}, 2, dashboard="ngstaff")
    interaction = _fake_interaction()
    await ngstaff_view._on_back(interaction)
    kwargs = interaction.response.edit_message.call_args.kwargs
    assert isinstance(kwargs["view"], NGStaffConfigDashboardView)
    assert kwargs["view"].server == "delta"


@pytest.mark.asyncio
async def test_nota_config_view_back_routes_by_dashboard_marker(patched_get_session):
    ngstaff_view = NotaConfigView(1, "delta", {}, 2, dashboard="ngstaff")
    interaction = _fake_interaction()
    await ngstaff_view._on_back(interaction)
    kwargs = interaction.response.edit_message.call_args.kwargs
    assert isinstance(kwargs["view"], NGStaffConfigDashboardView)
    assert kwargs["view"].server == "delta"


@pytest.mark.asyncio
async def test_role_react_config_view_back_routes_by_dashboard_marker(patched_get_session):
    ngstaff_view = RoleReactConfigView(1, "delta", {}, [], 2, dashboard="ngstaff")
    interaction = _fake_interaction()
    await ngstaff_view._on_back(interaction)
    kwargs = interaction.response.edit_message.call_args.kwargs
    assert isinstance(kwargs["view"], NGStaffConfigDashboardView)
    assert kwargs["view"].server == "delta"


# ══════════════════════════════════════════════════════════════════════════
# 🖥️ /ngstaff config — dashboard générique (4 systèmes, serveur dynamique)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ngstaff_dashboard_rank_branch_uses_correct_server(patched_get_session):
    await save_rank_config("delta", rank_channel_id=999)
    await save_rank_config("alpha", rank_channel_id=111)

    view = NGStaffConfigDashboardView(1, "delta", 2)
    interaction = _fake_interaction("rank")
    await view._on_select(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    sub_view = kwargs["view"]
    assert isinstance(sub_view, ConfigRankView)
    assert sub_view.server == "delta"
    assert sub_view.dashboard == "ngstaff"
    assert sub_view.cfg["rank_channel_id"] == 999  # bien delta, pas alpha


@pytest.mark.asyncio
async def test_ngstaff_dashboard_onu_branch_uses_correct_server(patched_get_session):
    await save_onu_config("delta", channel_id=777)
    await save_onu_config("alpha", channel_id=111)

    view = NGStaffConfigDashboardView(1, "delta", 2)
    interaction = _fake_interaction("onu")
    await view._on_select(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    sub_view = kwargs["view"]
    assert isinstance(sub_view, ONUConfigView)
    assert sub_view.server == "delta"
    assert sub_view.dashboard == "ngstaff"
    assert sub_view.cfg["channel_id"] == 777


@pytest.mark.asyncio
async def test_ngstaff_dashboard_notations_branch_uses_correct_server(patched_get_session):
    await save_nota_config("delta", channel_staff_id=555)
    await save_nota_config("alpha", channel_staff_id=111)

    view = NGStaffConfigDashboardView(1, "delta", 2)
    interaction = _fake_interaction("notations")
    await view._on_select(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    sub_view = kwargs["view"]
    assert isinstance(sub_view, NotaConfigView)
    assert sub_view.server == "delta"
    assert sub_view.dashboard == "ngstaff"
    assert sub_view.cfg["channel_staff_id"] == 555


@pytest.mark.asyncio
async def test_ngstaff_dashboard_role_react_branch_uses_correct_server(patched_get_session):
    await save_rr_config("delta", channel_id=333)
    await add_rr_entry("delta", 42, "Actus", "📰", None)
    await save_rr_config("alpha", channel_id=111)

    view = NGStaffConfigDashboardView(1, "delta", 2)
    interaction = _fake_interaction("role_react")
    await view._on_select(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    sub_view = kwargs["view"]
    assert isinstance(sub_view, RoleReactConfigView)
    assert sub_view.server == "delta"
    assert sub_view.dashboard == "ngstaff"
    assert sub_view.cfg["channel_id"] == 333
    assert len(sub_view.entries) == 1


@pytest.mark.asyncio
async def test_ngstaff_dashboard_unknown_option_sends_message(patched_get_session):
    view = NGStaffConfigDashboardView(1, "delta", 2)
    interaction = _fake_interaction("something_else")
    interaction.response.send_message = AsyncMock()
    await view._on_select(interaction)
    interaction.response.send_message.assert_awaited_once()


# ══════════════════════════════════════════════════════════════════════════
# 🩹 Régression : dashboard /alpha config_alpha n'appelle plus les managers
# alpha_onu_manager / alpha_role_react_manager / alpha_nota_manager morts
# (bug introduit par omission aux phases 8/9/10, corrigé phase 11).
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_alpha_dashboard_onu_branch_uses_ng_onu_manager(patched_get_session):
    await save_onu_config("alpha", channel_id=42)

    view = ConfigDashboardView(1, 2)
    interaction = _fake_interaction("onu")
    # Ne doit PAS lever (alpha_onu_manager.get_session n'est pas patché —
    # s'il était encore appelé, ceci tenterait une vraie connexion Postgres).
    await view._on_select(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    sub_view = kwargs["view"]
    assert isinstance(sub_view, ONUConfigView)
    assert sub_view.server == "alpha"
    assert sub_view.cfg["channel_id"] == 42


@pytest.mark.asyncio
async def test_alpha_dashboard_notations_branch_uses_ng_nota_manager(patched_get_session):
    await save_nota_config("alpha", channel_staff_id=42)

    view = ConfigDashboardView(1, 2)
    interaction = _fake_interaction("notations")
    await view._on_select(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    sub_view = kwargs["view"]
    assert isinstance(sub_view, NotaConfigView)
    assert sub_view.server == "alpha"
    assert sub_view.cfg["channel_staff_id"] == 42


@pytest.mark.asyncio
async def test_alpha_dashboard_role_react_branch_uses_ng_role_react_manager(patched_get_session):
    await save_rr_config("alpha", channel_id=42)
    await add_rr_entry("alpha", 7, "Actus", "📰", None)

    view = ConfigDashboardView(1, 2)
    interaction = _fake_interaction("role_react")
    await view._on_select(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    sub_view = kwargs["view"]
    assert isinstance(sub_view, RoleReactConfigView)
    assert sub_view.server == "alpha"
    assert sub_view.cfg["channel_id"] == 42
    assert len(sub_view.entries) == 1


@pytest.mark.asyncio
async def test_alpha_dashboard_rank_branch_still_works_explicit_server(patched_get_session):
    await save_rank_config("alpha", rank_channel_id=42)

    view = ConfigDashboardView(1, 2)
    interaction = _fake_interaction("rank")
    await view._on_select(interaction)

    kwargs = interaction.response.edit_message.call_args.kwargs
    sub_view = kwargs["view"]
    assert isinstance(sub_view, ConfigRankView)
    assert sub_view.server == "alpha"
    assert sub_view.dashboard == "alpha"  # défaut, pas explicitement passé
    assert sub_view.cfg["rank_channel_id"] == 42
