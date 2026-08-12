"""
tests/test_role_react_listener_cutover.py — Couvre §14 du prompt pour la
phase 10 (Rôle Réaction) : le listener (cogs/events/role_react_alpha.py)
doit résoudre correctement interaction.guild -> server via
ng_server_manager avant tout appel à ng_role_react_manager, ignorer
silencieusement un Discord inconnu du cache, et conserver le comportement
toggle + cooldown anti-spam inchangé.

Le listener vérifie `isinstance(member, discord.Member)` avant de toucher
aux rôles — plutôt que de construire un vrai discord.Member (lourd, dépend
de l'état interne du client), on monkeypatch temporairement `discord.Member`
pour qu'il pointe vers notre doublure légère le temps du test.
"""
from __future__ import annotations

import discord
import pytest

from cogs.events.role_react_alpha import RoleReactAlphaListener
from utils.db.models.ng_server import NGServer
from utils.managers import ng_role_react_manager as rr_mgr
from utils.managers import ng_server_manager

# ══════════════════════════════════════════════════════════════════════════
# 🧱 Doublures Discord
# ══════════════════════════════════════════════════════════════════════════

class FakeRole:
    def __init__(self, role_id: int, name: str = "Role"):
        self.id = role_id
        self.name = name


class FakeGuild:
    def __init__(self, guild_id: int, roles: list[FakeRole]):
        self.id = guild_id
        self._roles = {r.id: r for r in roles}

    def get_role(self, role_id: int):
        return self._roles.get(role_id)


class FakeMember:
    def __init__(self, user_id: int, roles: list[FakeRole] | None = None):
        self.id = user_id
        self.roles = list(roles or [])
        self.add_calls: list[list[int]] = []
        self.remove_calls: list[list[int]] = []

    async def add_roles(self, *roles, reason: str = "") -> None:
        self.add_calls.append([r.id for r in roles])
        self.roles = list(self.roles) + list(roles)

    async def remove_roles(self, *roles, reason: str = "") -> None:
        self.remove_calls.append([r.id for r in roles])
        ids = {r.id for r in roles}
        self.roles = [r for r in self.roles if r.id not in ids]


class FakeResponse:
    def __init__(self):
        self.messages: list[str] = []

    async def send_message(self, content=None, ephemeral: bool = False) -> None:
        self.messages.append(content)


class FakeInteraction:
    def __init__(self, guild, user, role_id: int, custom_id: str | None = None):
        self.type = discord.InteractionType.component
        self.data = {"custom_id": custom_id or f"role_react_{role_id}"}
        self.guild = guild
        self.user = user
        self.response = FakeResponse()


@pytest.fixture(autouse=True)
def _patch_discord_member(monkeypatch):
    """Le listener fait isinstance(member, discord.Member) — on substitue
    temporairement la classe pour que nos doublures FakeMember passent ce
    garde-fou, sans avoir à construire un vrai discord.Member (état interne
    du client requis, hors de portée pour un test unitaire)."""
    monkeypatch.setattr(discord, "Member", FakeMember)


async def _register_server(session_factory, *, name: str, guild_id: int):
    async with session_factory() as session:
        session.add(NGServer(
            name=name, display_name=name.capitalize(), edition="bedrock",
            discord_guild_id=guild_id, active=True,
        ))
        await session.commit()
    await ng_server_manager.reload_cache()


# ══════════════════════════════════════════════════════════════════════════
# 🔘 Toggle de rôle — résolution guild -> server
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_click_resolves_server_and_adds_role(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await rr_mgr.add_rr_entry("alpha", role_id=42, label="Fan", emoji="🔥")

    role = FakeRole(42)
    guild = FakeGuild(111, [role])
    member = FakeMember(1)
    interaction = FakeInteraction(guild, member, role_id=42)

    listener = RoleReactAlphaListener(bot=None)
    await listener.on_role_react_click(interaction)

    assert member.add_calls == [[42]]
    assert any("activé" in m for m in interaction.response.messages)


@pytest.mark.asyncio
async def test_click_toggles_off_if_already_present(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await rr_mgr.add_rr_entry("alpha", role_id=42, label="Fan")

    role = FakeRole(42)
    guild = FakeGuild(111, [role])
    member = FakeMember(1, roles=[role])  # a déjà le rôle
    interaction = FakeInteraction(guild, member, role_id=42)

    listener = RoleReactAlphaListener(bot=None)
    await listener.on_role_react_click(interaction)

    assert member.remove_calls == [[42]]
    assert any("retiré" in m for m in interaction.response.messages)


@pytest.mark.asyncio
async def test_click_ignores_unknown_guild(patched_get_session):
    """Discord absent de ng_servers -> ignoré silencieusement, pas de crash."""
    role = FakeRole(42)
    guild = FakeGuild(999, [role])  # jamais enregistré
    member = FakeMember(1)
    interaction = FakeInteraction(guild, member, role_id=42)

    listener = RoleReactAlphaListener(bot=None)
    await listener.on_role_react_click(interaction)

    assert member.add_calls == []
    assert interaction.response.messages == []


@pytest.mark.asyncio
async def test_click_rejects_role_not_in_configured_list(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    # Aucune entrée configurée pour role_id=42.

    role = FakeRole(42)
    guild = FakeGuild(111, [role])
    member = FakeMember(1)
    interaction = FakeInteraction(guild, member, role_id=42)

    listener = RoleReactAlphaListener(bot=None)
    await listener.on_role_react_click(interaction)

    assert member.add_calls == []
    assert any("n'est plus dans la liste" in m for m in interaction.response.messages)


@pytest.mark.asyncio
async def test_click_respects_cooldown(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await rr_mgr.add_rr_entry("alpha", role_id=42, label="Fan")

    role = FakeRole(42)
    guild = FakeGuild(111, [role])
    member = FakeMember(1)

    listener = RoleReactAlphaListener(bot=None)

    await listener.on_role_react_click(FakeInteraction(guild, member, role_id=42))
    assert len(member.add_calls) == 1

    # Rejoue immédiatement (même utilisateur, même rôle) -> bloqué par le cooldown.
    second = FakeInteraction(guild, member, role_id=42)
    await listener.on_role_react_click(second)
    assert len(member.add_calls) == 1  # pas de 2e appel add_roles
    assert any("Doucement" in m for m in second.response.messages)


@pytest.mark.asyncio
async def test_click_multi_server_isolation(patched_get_session):
    """Une entrée configurée sur alpha ne doit pas être visible sur delta."""
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _register_server(patched_get_session, name="delta", guild_id=222)
    await rr_mgr.add_rr_entry("alpha", role_id=42, label="Fan Alpha")

    role = FakeRole(42)
    guild_delta = FakeGuild(222, [role])
    member = FakeMember(1)
    interaction = FakeInteraction(guild_delta, member, role_id=42)

    listener = RoleReactAlphaListener(bot=None)
    await listener.on_role_react_click(interaction)

    assert member.add_calls == []  # role_id=42 n'est configuré que côté alpha
    assert any("n'est plus dans la liste" in m for m in interaction.response.messages)
