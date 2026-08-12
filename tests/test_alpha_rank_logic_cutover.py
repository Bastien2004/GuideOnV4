"""
tests/test_alpha_rank_logic_cutover.py — Couvre le point le plus sensible de
la refonte multi-serveurs (§14 du prompt) : apply_staff_roles doit rester
strictement idempotent après le cutover vers ng_staff/ng_rank_configs
("rejouer 2x = même état final" — ne PAS casser cette fonction, sinon rôles
sautent en prod). Vérifie aussi qu'après cutover, execute_grade_rank/
execute_statut_rank/execute_derank écrivent bien dans ng_staff et plus dans
alpha_staff.
"""
from __future__ import annotations

import pytest

from utils.alpha_derank_logic import execute_derank
from utils.alpha_rank_logic import apply_staff_roles, execute_grade_rank, execute_statut_rank
from utils.managers import ng_staff_manager as ng_staff

# ══════════════════════════════════════════════════════════════════════════
# 🧱 Doublures Discord (pas de dépendance réseau/gateway)
# ══════════════════════════════════════════════════════════════════════════

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
        self.add_calls: list[set[int]] = []
        self.remove_calls: list[set[int]] = []
        self.nick: str | None = None

    async def add_roles(self, *roles, reason: str = "") -> None:
        ids = {r.id for r in roles}
        self.add_calls.append(ids)
        current_ids = {r.id for r in self.roles}
        self.roles = [self.guild.get_role(rid) for rid in (current_ids | ids)]

    async def remove_roles(self, *roles, reason: str = "") -> None:
        ids = {r.id for r in roles}
        self.remove_calls.append(ids)
        self.roles = [r for r in self.roles if r.id not in ids]

    async def edit(self, nick: str | None = None, reason: str = "") -> None:
        self.nick = nick


class FakeBot:
    """cfg de test n'a jamais de channel configuré -> aucune I/O réseau déclenchée."""
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
    # Pas de salons configurés -> pas d'annonces envoyées pendant les tests.
    "rank_channel_id": None,
    "journaliste_channel_id": None,
    "dev_channel_id": None,
    "journaliste_ping_id": None,
    "dev_ping_id": None,
    "rank_emoji": None,
    "content_stafflist_channel_id": None,
}


# ══════════════════════════════════════════════════════════════════════════
# 🔁 apply_staff_roles — idempotence (§14, risque #1 du prompt)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_apply_staff_roles_first_application():
    guild = FakeGuild([10, 20, 99, 30, 31, 32])
    membre = FakeMember(1, guild, initial_role_ids=[])

    await apply_staff_roles(membre, CFG, grade="guide", secondary={})

    assert membre.add_calls == [{10, 99}]  # guide + équipe (grade général)
    assert membre.remove_calls == []
    assert {r.id for r in membre.roles} == {10, 99}


@pytest.mark.asyncio
async def test_apply_staff_roles_is_idempotent_on_replay():
    """Rejouer avec le même grade/secondary ne doit RIEN ajouter ni retirer."""
    guild = FakeGuild([10, 20, 99, 30, 31, 32])
    membre = FakeMember(1, guild, initial_role_ids=[])

    await apply_staff_roles(membre, CFG, grade="guide", secondary={})
    await apply_staff_roles(membre, CFG, grade="guide", secondary={})
    await apply_staff_roles(membre, CFG, grade="guide", secondary={})

    # Un seul appel réel (le premier) — les 2 suivants ne trouvent aucun delta.
    assert membre.add_calls == [{10, 99}]
    assert membre.remove_calls == []


@pytest.mark.asyncio
async def test_apply_staff_roles_promotion_swaps_grade_role_keeps_equipe():
    guild = FakeGuild([10, 20, 99, 30, 31, 32])
    membre = FakeMember(1, guild, initial_role_ids=[10, 99])  # déjà guide

    await apply_staff_roles(membre, CFG, grade="administrateur", secondary={})

    assert membre.add_calls == [{20}]       # rôle admin ajouté
    assert membre.remove_calls == [{10}]    # rôle guide retiré
    assert {r.id for r in membre.roles} == {20, 99}  # équipe conservé


@pytest.mark.asyncio
async def test_apply_staff_roles_derank_complet_removes_everything_managed():
    guild = FakeGuild([10, 20, 99, 30, 31, 32])
    membre = FakeMember(1, guild, initial_role_ids=[10, 99, 31])  # guide + équipe + affilié

    await apply_staff_roles(membre, CFG, grade=None, secondary={"journaliste": False, "affilie": False, "builder": False})

    assert membre.add_calls == []
    assert membre.remove_calls == [{10, 99, 31}]
    assert membre.roles == []


@pytest.mark.asyncio
async def test_apply_staff_roles_ignores_unconfigured_role_ids():
    """cfg avec role_id=None ne doit jamais planter (pas de rôle "0")."""
    guild = FakeGuild([99])
    membre = FakeMember(1, guild)
    cfg = {**CFG, "role_guide_id": None}

    await apply_staff_roles(membre, cfg, grade="guide", secondary={})

    # role_guide_id est None -> aucun rôle "guide" à ajouter, seulement équipe.
    assert membre.add_calls == [{99}]


# ══════════════════════════════════════════════════════════════════════════
# ✍️ execute_grade_rank / execute_statut_rank — écrivent dans ng_staff
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_execute_grade_rank_writes_to_ng_staff_not_alpha_staff(patched_get_session):
    from utils.db.models.ng_server import NGServer

    async with patched_get_session() as session:
        session.add(NGServer(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=1, active=True))
        await session.commit()

    guild = FakeGuild([10, 99])
    membre = FakeMember(42, guild, initial_role_ids=[])

    result = await execute_grade_rank(
        FakeBot(), guild_id=1, membre=membre, pseudo="Bob", new_grade="guide", cfg=CFG, existing=None,
    )

    assert result.label == "Guide"
    ng_member = await ng_staff.get_staff_member("alpha", 42)
    assert ng_member is not None
    assert ng_member["pseudo_jeu"] == "Bob"
    assert ng_member["grade"] == "guide"

    # Refonte multi-serveurs, phase 15 (nettoyage legacy) : la vérification
    # "alpha_staff n'a jamais été touchée" reposait sur le modèle ORM
    # AlphaStaffMember, retiré dans cette phase (plus aucun code vivant ne
    # l'utilise, voir PHASE_15.md). L'invariant qu'elle protégeait — que
    # seul ng_staff est écrit — reste couvert par les nombreux tests
    # d'isolation multi-serveurs de ce fichier et de test_ng_staff_manager.py.


@pytest.mark.asyncio
async def test_execute_statut_rank_writes_to_ng_staff(patched_get_session):
    from utils.db.models.ng_server import NGServer

    async with patched_get_session() as session:
        session.add(NGServer(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=1, active=True))
        await session.commit()

    guild = FakeGuild([30])
    membre = FakeMember(7, guild, initial_role_ids=[])

    result = await execute_statut_rank(
        FakeBot(), guild_id=1, membre=membre, pseudo="Alice", statut="journaliste",
        cfg=CFG, existing=None, pseudo_jeu_builder=None,
    )

    assert result.label == "Journaliste"
    ng_member = await ng_staff.get_staff_member("alpha", 7)
    assert ng_member is not None
    assert ng_member["is_journaliste"] is True


@pytest.mark.asyncio
async def test_execute_derank_removes_from_ng_staff(patched_get_session):
    from utils.db.models.ng_server import NGServer

    async with patched_get_session() as session:
        session.add(NGServer(name="alpha", display_name="Alpha", edition="bedrock", discord_guild_id=1, active=True))
        await session.commit()

    await ng_staff.add_staff_member("alpha", 55, "Carl", "guide")
    member_data = await ng_staff.get_staff_member("alpha", 55)

    guild = FakeGuild([10, 99])
    membre = FakeMember(55, guild, initial_role_ids=[10, 99])

    await execute_derank(FakeBot(), membre, member_data, CFG, guild_id=1, role="complet")

    assert await ng_staff.get_staff_member("alpha", 55) is None
    assert membre.roles == []
