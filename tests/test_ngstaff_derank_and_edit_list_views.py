"""
tests/test_ngstaff_derank_and_edit_list_views.py — Couvre §14 pour la phase
12 : généralisation de DerankConfirmView (views/alpha/derank_view.py) et
EditListView + sous-vues (views/alpha/edit_list_view.py) au paramètre
`server` (kwarg-only, défaut "alpha" — /alpha derank et
/alpha edit_stafflist_alpha ne le passent jamais, donc leur comportement
doit rester strictement identique).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.managers import ng_staff_manager as ng_staff
from views.alpha.derank_view import DerankConfirmView
from views.alpha.edit_list_view import EditListView, _ConfirmRemoveView, _ModifyOptionsView

CFG = {
    "role_guide_id": 10,
    "role_administrateur_id": 20,
    "role_equipe_id": 99,
    "role_journaliste_id": 30,
    "role_affilie_id": 31,
    "role_builder_id": 32,
    "rank_channel_id": None,
    "journaliste_channel_id": None,
    "dev_channel_id": None,
    "journaliste_ping_id": None,
    "dev_ping_id": None,
    "rank_emoji": None,
    "content_stafflist_channel_id": None,  # court-circuite refresh_staff_message
}


class FakeRole:
    def __init__(self, role_id: int):
        self.id = role_id


class FakeGuild:
    def __init__(self, role_ids: list[int]):
        self._roles = {rid: FakeRole(rid) for rid in role_ids}

    def get_role(self, rid: int):
        return self._roles.get(rid)


class FakeMember:
    def __init__(self, discord_id: int, guild: FakeGuild, initial_role_ids: list[int] | None = None):
        self.id = discord_id
        self.name = "testuser"
        self.guild = guild
        self.roles = [guild.get_role(rid) for rid in (initial_role_ids or [])]

    async def add_roles(self, *roles, reason: str = "") -> None:
        current_ids = {r.id for r in self.roles}
        ids = {r.id for r in roles}
        self.roles = [self.guild.get_role(rid) for rid in (current_ids | ids)]

    async def remove_roles(self, *roles, reason: str = "") -> None:
        ids = {r.id for r in roles}
        self.roles = [r for r in self.roles if r.id not in ids]

    async def edit(self, nick: str | None = None, reason: str = "") -> None:
        self.nick = nick


def _fake_interaction() -> MagicMock:
    interaction = MagicMock()
    interaction.client = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


# ══════════════════════════════════════════════════════════════════════════
# ⬇️ DerankConfirmView
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_derank_confirm_view_default_server_is_alpha(patched_get_session):
    await ng_staff.add_staff_member("alpha", 1, "Bob", "guide")
    member_data = await ng_staff.get_staff_member("alpha", 1)

    guild = FakeGuild([10, 99])
    membre = FakeMember(1, guild, initial_role_ids=[10, 99])

    view = DerankConfirmView(membre, member_data, CFG, 111, "complet", owner_id=42)
    assert view.server == "alpha"

    interaction = _fake_interaction()
    await view._on_confirm(interaction)

    assert await ng_staff.get_staff_member("alpha", 1) is None


@pytest.mark.asyncio
async def test_derank_confirm_view_explicit_server_isolated(patched_get_session):
    await ng_staff.add_staff_member("delta", 5, "Dee", "guide")
    await ng_staff.add_staff_member("alpha", 5, "Dee", "guide")  # même discord_id, autre serveur
    member_data = await ng_staff.get_staff_member("delta", 5)

    guild = FakeGuild([10, 99])
    membre = FakeMember(5, guild, initial_role_ids=[10, 99])

    view = DerankConfirmView(membre, member_data, CFG, 222, "complet", owner_id=42, server="delta")
    interaction = _fake_interaction()
    await view._on_confirm(interaction)

    assert await ng_staff.get_staff_member("delta", 5) is None
    assert await ng_staff.get_staff_member("alpha", 5) is not None  # non touché


# ══════════════════════════════════════════════════════════════════════════
# 📋 EditListView — CRUD multi-serveurs
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_edit_list_view_default_server_is_alpha():
    view = EditListView(guild_id=1, owner_id=2, members=[])
    assert view.server == "alpha"


@pytest.mark.asyncio
async def test_edit_list_view_confirm_remove_isolated_per_server(patched_get_session):
    await ng_staff.add_staff_member("delta", 9, "Zoe", "guide")
    await ng_staff.add_staff_member("alpha", 9, "Zoe", "guide")
    data = await ng_staff.get_staff_member("delta", 9)

    view = _ConfirmRemoveView(guild_id=1, owner_id=2, member_data=data, server="delta")
    interaction = _fake_interaction()
    await view._on_confirm(interaction)

    assert await ng_staff.get_staff_member("delta", 9) is None
    assert await ng_staff.get_staff_member("alpha", 9) is not None

    kwargs = interaction.response.edit_message.call_args.kwargs
    new_view = kwargs["view"]
    assert isinstance(new_view, EditListView)
    assert new_view.server == "delta"


@pytest.mark.asyncio
async def test_edit_list_view_modify_options_save_grade_isolated(patched_get_session):
    await ng_staff.add_staff_member("delta", 11, "Milo", "guide")
    data = await ng_staff.get_staff_member("delta", 11)

    view = _ModifyOptionsView(guild_id=1, owner_id=2, member_data=data, server="delta")
    interaction = _fake_interaction()
    await view._save_grade(interaction, discord_id=11, member_name="Milo", grade="administrateur")

    updated = await ng_staff.get_staff_member("delta", 11)
    assert updated["grade"] == "administrateur"

    kwargs = interaction.response.edit_message.call_args.kwargs
    assert kwargs["view"].server == "delta"


@pytest.mark.asyncio
async def test_edit_list_view_add_flow_writes_to_correct_server(patched_get_session):
    view = EditListView(guild_id=1, owner_id=2, members=[], server="delta")

    interaction = _fake_interaction()
    interaction.response.send_modal = AsyncMock()
    await view._after_grade_add(interaction, discord_id=77, member_name="NewGuy", grade="guide")

    # send_modal appelé -> la modal capture le on_submit ; on l'invoque directement.
    modal = interaction.response.send_modal.call_args.args[0]
    submit_interaction = _fake_interaction()
    await modal._on_submit(submit_interaction, ("Pseudo77", ""))

    assert await ng_staff.get_staff_member("delta", 77) is not None
    assert await ng_staff.get_staff_member("alpha", 77) is None
