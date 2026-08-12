"""
tests/test_ngstaff_rank_derank_logic.py — Couvre §14 pour la phase 12 :
execute_grade_rank / execute_statut_rank (utils/alpha_rank_logic.py) et
execute_derank (utils/alpha_derank_logic.py) acceptent désormais un kwarg
`server` (défaut "alpha", ajouté phase 12 pour /ngstaff rank/derank).
Vérifie : le défaut ne change rien pour /alpha (déjà couvert par
test_alpha_rank_logic_cutover.py, non dupliqué ici), et server="delta"
écrit bien dans le bon namespace ng_staff, isolé de "alpha".

Comme dans test_alpha_rank_logic_cutover.py, CFG garde tous les channel_id
à None pour que le refresh_staff_message() appelé en interne reste un
no-op silencieux (pas de dépendance à alpha_message_manager, non patché
dans conftest — voir tests/test_refresh_staff_message_multiserver.py pour
la couverture dédiée de ce helper).
"""
from __future__ import annotations

import pytest

from utils.alpha_derank_logic import execute_derank
from utils.alpha_rank_logic import execute_grade_rank, execute_statut_rank
from utils.db.models.ng_server import NGServer
from utils.managers import ng_staff_manager as ng_staff


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


class FakeBot:
    def get_channel(self, channel_id):
        return None

    async def fetch_channel(self, channel_id):
        return None


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
    "content_stafflist_channel_id": None,
}


async def _seed_ng_servers(session_factory) -> None:
    async with session_factory() as session:
        session.add(NGServer(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=1, active=True))
        session.add(NGServer(name="delta", display_name="Delta", edition="java", discord_guild_id=2, active=True))
        await session.commit()


@pytest.mark.asyncio
async def test_execute_grade_rank_default_server_is_alpha(patched_get_session):
    await _seed_ng_servers(patched_get_session)
    guild = FakeGuild([10, 99])
    membre = FakeMember(1, guild)

    await execute_grade_rank(
        FakeBot(), guild_id=1, membre=membre, pseudo="Bob", new_grade="guide", cfg=CFG, existing=None,
    )

    assert await ng_staff.get_staff_member("alpha", 1) is not None


@pytest.mark.asyncio
async def test_execute_grade_rank_explicit_server_isolated_from_alpha(patched_get_session):
    await _seed_ng_servers(patched_get_session)
    guild = FakeGuild([10, 99])
    membre = FakeMember(2, guild)

    await execute_grade_rank(
        FakeBot(), guild_id=2, membre=membre, pseudo="Dee", new_grade="guide", cfg=CFG, existing=None,
        server="delta",
    )

    assert await ng_staff.get_staff_member("delta", 2) is not None
    assert await ng_staff.get_staff_member("alpha", 2) is None


@pytest.mark.asyncio
async def test_execute_statut_rank_explicit_server_isolated(patched_get_session):
    await _seed_ng_servers(patched_get_session)
    guild = FakeGuild([30])
    membre = FakeMember(7, guild)

    result = await execute_statut_rank(
        FakeBot(), guild_id=2, membre=membre, pseudo="Alice", statut="journaliste",
        cfg=CFG, existing=None, pseudo_jeu_builder=None, server="delta",
    )

    assert result.label == "Journaliste"
    ng_member = await ng_staff.get_staff_member("delta", 7)
    assert ng_member is not None
    assert ng_member["is_journaliste"] is True
    assert await ng_staff.get_staff_member("alpha", 7) is None


@pytest.mark.asyncio
async def test_execute_derank_explicit_server_isolated(patched_get_session):
    await _seed_ng_servers(patched_get_session)

    await ng_staff.add_staff_member("delta", 55, "Carl", "guide")
    await ng_staff.add_staff_member("alpha", 55, "Carl", "guide")  # même discord_id, autre serveur
    member_data = await ng_staff.get_staff_member("delta", 55)

    guild = FakeGuild([10, 99])
    membre = FakeMember(55, guild, initial_role_ids=[10, 99])

    await execute_derank(FakeBot(), membre, member_data, CFG, guild_id=2, role="complet", server="delta")

    assert await ng_staff.get_staff_member("delta", 55) is None
    # Le membre alpha (même discord_id) n'a pas été touché.
    assert await ng_staff.get_staff_member("alpha", 55) is not None


@pytest.mark.asyncio
async def test_execute_grade_rank_default_still_works_without_server_kwarg(patched_get_session):
    """Régression : /alpha rank ne passe jamais `server=` — le défaut doit
    continuer à se comporter exactement comme avant la phase 12."""
    await _seed_ng_servers(patched_get_session)
    guild = FakeGuild([20, 99])
    membre = FakeMember(9, guild)

    result = await execute_grade_rank(
        FakeBot(), guild_id=1, membre=membre, pseudo="Zoe", new_grade="administrateur", cfg=CFG, existing=None,
    )

    assert result.label == "Administrateur"
    assert (await ng_staff.get_staff_member("alpha", 9))["grade"] == "administrateur"
