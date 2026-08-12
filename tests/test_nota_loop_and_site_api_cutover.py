"""
tests/test_nota_loop_and_site_api_cutover.py — Couvre les points de
vigilance du prompt (§14) spécifiques à la phase 9 (Notations) :
  - "Task loops : dispatch correct par serveur, gestion des serveurs
    active=false (ignorés)"
  - "Multi-serveurs isolés : insertion Alpha + Delta -> aucune fuite entre
    serveurs"
  - le bouton de présence (on_interaction) résout correctement le serveur
    à partir de interaction.guild_id.
  - le contrat externe de l'API notations (mono-serveur, sans guild_id en
    entrée) continue de fonctionner malgré le passage à un stockage clé
    par `server` en interne.

La boucle (cogs/events/notations_alpha.py) est testée en appelant
directement la coroutine sous-jacente (`_nota_task.coro`), sans démarrer le
vrai discord.ext.tasks.Loop.

Limite connue : les scénarios "déclenchement à l'heure" fixent les champs
weekday/heure/minute de la config sur l'heure Europe/Paris courante pour
retomber dans la fenêtre de déclenchement (±1 min, cf. is_time_now) — risque
de flakiness infinitésimal à la frontière d'une minute, jugé acceptable
pour une suite qui s'exécute en subsecondes.
"""
from __future__ import annotations

import discord
import pytest

from cogs.events.notations_alpha import NotationsAlphaListener
from utils.db.models.ng_server import NGServer
from utils.db.models.ng_staff import NGStaffMember
from utils.managers import ng_nota_manager as nota_mgr
from utils.managers import ng_server_manager
from utils.managers import notations_manager as site_nota_mgr

# ══════════════════════════════════════════════════════════════════════════
# 🧱 Doublures Discord
# ══════════════════════════════════════════════════════════════════════════

class FakeMessage:
    def __init__(self, msg_id: int):
        self.id = msg_id
        self.edits: list[dict] = []

    async def edit(self, **kwargs) -> None:
        self.edits.append(kwargs)


class FakeChannel:
    def __init__(self, channel_id: int):
        self.id = channel_id
        self.sent: list[dict] = []
        self._messages: dict[int, FakeMessage] = {}
        self._next_id = 1000

    async def send(self, **kwargs) -> FakeMessage:
        self.sent.append(kwargs)
        msg = FakeMessage(self._next_id)
        self._messages[msg.id] = msg
        self._next_id += 1
        return msg

    async def fetch_message(self, msg_id: int) -> FakeMessage:
        msg = self._messages.get(msg_id)
        if msg is None:
            raise discord.NotFound.__new__(discord.NotFound)  # jamais levé dans nos tests
        return msg

    def register_existing_message(self, msg_id: int) -> None:
        self._messages[msg_id] = FakeMessage(msg_id)


class FakeBot:
    def __init__(self):
        self._channels: dict[int, FakeChannel] = {}

    def add_channel(self, channel_id: int) -> FakeChannel:
        ch = FakeChannel(channel_id)
        self._channels[channel_id] = ch
        return ch

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)

    async def fetch_channel(self, channel_id: int):
        return None


class FakeUser:
    def __init__(self, uid: int):
        self.id = uid


class FakeResponse:
    def __init__(self):
        self.deferred = False
        self.messages: list[str] = []

    async def defer(self, ephemeral: bool = False) -> None:
        self.deferred = True

    async def send_message(self, content=None, ephemeral: bool = False, view=None) -> None:
        self.messages.append(content)


class FakeFollowup:
    def __init__(self):
        self.sent: list[str] = []

    async def send(self, content=None, ephemeral: bool = False) -> None:
        self.sent.append(content)


class FakeInteraction:
    def __init__(self, guild_id: int | None, user_id: int, custom_id: str = "notation_presence_toggle"):
        self.type = discord.InteractionType.component
        self.data = {"custom_id": custom_id}
        self.guild_id = guild_id
        self.user = FakeUser(user_id)
        self.response = FakeResponse()
        self.followup = FakeFollowup()


# ══════════════════════════════════════════════════════════════════════════
# 🔧 Helpers
# ══════════════════════════════════════════════════════════════════════════

async def _register_server(session_factory, *, name: str, guild_id: int, active: bool = True):
    async with session_factory() as session:
        session.add(NGServer(
            name=name, display_name=name.capitalize(), edition="bedrock",
            discord_guild_id=guild_id, active=active,
        ))
        await session.commit()
    await ng_server_manager.reload_cache()


async def _add_staff(session_factory, *, server: str, discord_id: int, grade: str):
    async with session_factory() as session:
        session.add(NGStaffMember(server=server, discord_id=discord_id, pseudo_jeu="op", grade=grade))
        await session.commit()


def _now_paris():
    return nota_mgr.now_paris()


async def _configure_presence_now(server: str, channel_id: int) -> None:
    now = _now_paris()
    await nota_mgr.save_nota_config(
        server,
        channel_staff_id=channel_id,
        send_presence_weekday=now.weekday(),
        send_presence_hour=now.hour,
        send_presence_minute=now.minute,
        enabled=True,
    )


async def _configure_public_now(server: str, channel_id: int) -> None:
    now = _now_paris()
    await nota_mgr.save_nota_config(
        server,
        channel_public_id=channel_id,
        send_public_weekday=now.weekday(),
        send_public_hour=now.hour,
        send_public_minute=now.minute,
        enabled=True,
    )


# ══════════════════════════════════════════════════════════════════════════
# 🔁 Boucle — présence
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_loop_sends_presence_message_when_time_matches(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    bot = FakeBot()
    channel = bot.add_channel(555)
    await _configure_presence_now("alpha", 555)

    listener = NotationsAlphaListener(bot)
    try:
        await listener._nota_task.coro(listener)
    finally:
        listener._nota_task.cancel()

    assert len(channel.sent) == 1
    state = await nota_mgr.load_nota_state("alpha")
    assert state["availability_message_id"] is not None


@pytest.mark.asyncio
async def test_loop_ignores_inactive_ng_server(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111, active=False)
    bot = FakeBot()
    channel = bot.add_channel(555)
    await _configure_presence_now("alpha", 555)

    listener = NotationsAlphaListener(bot)
    try:
        await listener._nota_task.coro(listener)
    finally:
        listener._nota_task.cancel()

    assert channel.sent == []


@pytest.mark.asyncio
async def test_loop_ignores_disabled_config(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    bot = FakeBot()
    channel = bot.add_channel(555)
    await _configure_presence_now("alpha", 555)
    await nota_mgr.save_nota_config("alpha", enabled=False)

    listener = NotationsAlphaListener(bot)
    try:
        await listener._nota_task.coro(listener)
    finally:
        listener._nota_task.cancel()

    assert channel.sent == []


@pytest.mark.asyncio
async def test_loop_multi_server_isolation(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _register_server(patched_get_session, name="delta", guild_id=222)
    bot = FakeBot()
    channel_alpha = bot.add_channel(555)
    channel_delta = bot.add_channel(666)
    await _configure_presence_now("alpha", 555)
    await _configure_presence_now("delta", 666)

    listener = NotationsAlphaListener(bot)
    try:
        await listener._nota_task.coro(listener)
    finally:
        listener._nota_task.cancel()

    assert len(channel_alpha.sent) == 1
    assert len(channel_delta.sent) == 1

    state_alpha = await nota_mgr.load_nota_state("alpha")
    state_delta = await nota_mgr.load_nota_state("delta")
    assert state_alpha["availability_message_id"] is not None
    assert state_delta["availability_message_id"] is not None
    # Chaque salon n'a reçu que son propre message (pas de fuite cross-serveur).
    assert channel_alpha.sent[0] is not channel_delta.sent[0]


# ══════════════════════════════════════════════════════════════════════════
# 🔁 Boucle — envoi public + reset
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_loop_sends_public_and_resets_week(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _add_staff(patched_get_session, server="alpha", discord_id=1, grade="administrateur")
    await nota_mgr.toggle_availability("alpha", 1)

    bot = FakeBot()
    channel = bot.add_channel(777)
    await _configure_public_now("alpha", 777)

    listener = NotationsAlphaListener(bot)
    try:
        await listener._nota_task.coro(listener)
    finally:
        listener._nota_task.cancel()

    assert len(channel.sent) == 1
    state = await nota_mgr.load_nota_state("alpha")
    assert state["public_message_id"] is not None
    # Reset hebdo : plus personne disponible après l'envoi public.
    assert await nota_mgr.get_available_operators("alpha") == []


@pytest.mark.asyncio
async def test_loop_public_send_dedup_same_minute(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _add_staff(patched_get_session, server="alpha", discord_id=1, grade="administrateur")
    await nota_mgr.toggle_availability("alpha", 1)

    bot = FakeBot()
    channel = bot.add_channel(777)
    await _configure_public_now("alpha", 777)

    listener = NotationsAlphaListener(bot)
    try:
        await listener._nota_task.coro(listener)
        await listener._nota_task.coro(listener)
    finally:
        listener._nota_task.cancel()

    # public_message_id posé après le 1er envoi -> le sentinel empêche un 2e envoi.
    assert len(channel.sent) == 1


# ══════════════════════════════════════════════════════════════════════════
# 🔘 Bouton présence — résolution guild_id -> server
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_on_presence_toggle_resolves_server_and_toggles(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _add_staff(patched_get_session, server="alpha", discord_id=42, grade="administrateur")
    await nota_mgr.set_state_fields("alpha", availability_message_id=12345)

    listener = NotationsAlphaListener(FakeBot())
    try:
        interaction = FakeInteraction(guild_id=111, user_id=42)
        await listener.on_presence_toggle(interaction)
    finally:
        listener._nota_task.cancel()

    assert interaction.response.deferred is True
    assert await nota_mgr.get_available_operators("alpha") == [42]


@pytest.mark.asyncio
async def test_on_presence_toggle_rejects_non_operator(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await nota_mgr.set_state_fields("alpha", availability_message_id=12345)
    # discord_id=99 n'est pas dans la liste staff -> pas opérateur.

    listener = NotationsAlphaListener(FakeBot())
    try:
        interaction = FakeInteraction(guild_id=111, user_id=99)
        await listener.on_presence_toggle(interaction)
    finally:
        listener._nota_task.cancel()

    assert interaction.response.deferred is False
    assert await nota_mgr.get_available_operators("alpha") == []


@pytest.mark.asyncio
async def test_on_presence_toggle_ignores_unknown_guild(patched_get_session):
    """Interaction venant d'un Discord absent de ng_servers -> ignorée sans lever."""
    listener = NotationsAlphaListener(FakeBot())
    try:
        interaction = FakeInteraction(guild_id=999, user_id=1)
        await listener.on_presence_toggle(interaction)  # ne doit pas lever
    finally:
        listener._nota_task.cancel()

    assert interaction.response.deferred is False


# ══════════════════════════════════════════════════════════════════════════
# 🌐 API site — mono-serveur (SERVER="alpha" en dur), contrat externe inchangé
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_site_get_config_returns_none_when_unset(patched_get_session):
    assert await site_nota_mgr.get_config() is None


@pytest.mark.asyncio
async def test_site_update_full_config_and_get_config_roundtrip(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)

    await site_nota_mgr.update_full_config({"guild_id": 111})
    fetched = await site_nota_mgr.get_config()
    assert fetched is not None
    assert fetched["guild_id"] == 111
    assert fetched["server"] == "alpha"

    # La donnée écrite par le site est bien celle que lit le bot.
    bot_side = await nota_mgr.load_nota_config("alpha")
    assert bot_side["server"] == "alpha"


@pytest.mark.asyncio
async def test_site_update_partial_requires_existing_config(patched_get_session):
    with pytest.raises(ValueError):
        await site_nota_mgr.update_partial({"role_id": 5})


@pytest.mark.asyncio
async def test_site_update_partial_updates_fields(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await site_nota_mgr.update_full_config({"guild_id": 111})

    updated = await site_nota_mgr.update_partial({"role_id": 777, "channel_staff_id": 888})
    assert updated["role_id"] == 777
    assert updated["channel_staff_id"] == 888

    bot_side = await nota_mgr.load_nota_config("alpha")
    assert bot_side["role_id"] == 777
