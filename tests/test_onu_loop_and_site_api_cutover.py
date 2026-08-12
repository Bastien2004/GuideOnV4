"""
tests/test_onu_loop_and_site_api_cutover.py — Couvre les points de vigilance
du prompt (§14) spécifiques à la phase 8 :
  - "Task loops : dispatch correct par serveur, gestion des serveurs
    active=false (ignorés)"
  - "Multi-serveurs isolés : insertion Alpha + Delta -> aucune fuite entre
    serveurs"
  - le contrat externe de l'API site (guild_id) reste inchangé malgré le
    passage à un stockage clé par `server` en interne.

La boucle ONU (cogs/events/onu_alpha.py) est testée en appelant directement
la coroutine sous-jacente (`onu_task.coro`), sans démarrer le vrai
discord.ext.tasks.Loop — on évite ainsi toute dépendance à une vraie
connexion gateway.

Limite connue : les cas "annonce déclenchée" fixent jour_onu/pre_heure/
pre_minute sur l'heure UTC courante (timezone="UTC" dans la config test)
pour retomber pile dans la fenêtre de déclenchement — un test lancé pile à
la frontière d'une minute a un risque infinitésimal de flakiness, jugé
acceptable pour une suite qui s'exécute en subsecondes.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cogs.events.onu_alpha import ONUAlphaListener
from utils.db.models.ng_server import NGServer
from utils.managers import ng_onu_manager as onu_mgr
from utils.managers import ng_server_manager
from utils.managers import onu_manager as site_onu_mgr

# ══════════════════════════════════════════════════════════════════════════
# 🧱 Doublures Discord
# ══════════════════════════════════════════════════════════════════════════

class FakeChannel:
    def __init__(self, channel_id: int, guild):
        self.id = channel_id
        self.guild = guild
        self.sent: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.sent.append(kwargs)


class FakeGuild:
    def __init__(self, guild_id: int):
        self.id = guild_id
        self._channels: dict[int, FakeChannel] = {}
        self._members: dict[int, object] = {}

    def add_channel(self, channel_id: int) -> FakeChannel:
        ch = FakeChannel(channel_id, self)
        self._channels[channel_id] = ch
        return ch

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)

    def get_member(self, uid: int):
        return self._members.get(uid)


class FakeBot:
    def __init__(self):
        self._guilds: dict[int, FakeGuild] = {}

    def add_guild(self, guild_id: int) -> FakeGuild:
        g = FakeGuild(guild_id)
        self._guilds[guild_id] = g
        return g

    def get_guild(self, guild_id: int):
        return self._guilds.get(guild_id)

    async def fetch_channel(self, channel_id: int):
        return None


async def _register_server(session_factory, *, name: str, guild_id: int, active: bool = True):
    async with session_factory() as session:
        session.add(NGServer(
            name=name, display_name=name.capitalize(), edition="bedrock",
            discord_guild_id=guild_id, active=active,
        ))
        await session.commit()
    await ng_server_manager.reload_cache()


def _now_utc():
    # timezone.utc plutôt que datetime.UTC (3.11+) pour rester compatible
    # avec l'interpréteur 3.10 utilisé par ce sandbox de test.
    return datetime.now(timezone.utc)  # noqa: UP017


async def _configure_pre_annonce_now(server: str, channel_id: int) -> None:
    now = _now_utc()
    await onu_mgr.save_onu_config(
        server,
        channel_id=channel_id,
        timezone="UTC",
        jour_onu=now.weekday(),
        pre_heure=now.hour,
        pre_minute=now.minute,
        enabled=True,
    )


# ══════════════════════════════════════════════════════════════════════════
# 🔁 Boucle ONU — dispatch multi-serveurs
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_onu_task_dispatches_to_correct_server_channel(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _configure_pre_annonce_now("alpha", channel_id=555)

    bot = FakeBot()
    guild = bot.add_guild(111)
    channel = guild.add_channel(555)

    listener = ONUAlphaListener(bot)
    try:
        await listener.onu_task.coro(listener)
    finally:
        listener.onu_task.cancel()

    assert len(channel.sent) == 1


@pytest.mark.asyncio
async def test_onu_task_ignores_inactive_ng_server(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111, active=False)
    await _configure_pre_annonce_now("alpha", channel_id=555)

    bot = FakeBot()
    guild = bot.add_guild(111)
    channel = guild.add_channel(555)

    listener = ONUAlphaListener(bot)
    try:
        await listener.onu_task.coro(listener)
    finally:
        listener.onu_task.cancel()

    assert channel.sent == []


@pytest.mark.asyncio
async def test_onu_task_ignores_disabled_config(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _configure_pre_annonce_now("alpha", channel_id=555)
    await onu_mgr.save_onu_config("alpha", enabled=False)

    bot = FakeBot()
    guild = bot.add_guild(111)
    channel = guild.add_channel(555)

    listener = ONUAlphaListener(bot)
    try:
        await listener.onu_task.coro(listener)
    finally:
        listener.onu_task.cancel()

    assert channel.sent == []


@pytest.mark.asyncio
async def test_onu_task_ignores_unknown_server_without_crashing(patched_get_session):
    """Config orpheline (server absent de ng_servers, ex: guild supprimée) -> ignorée."""
    await onu_mgr.save_onu_config(
        "ghost", channel_id=1, timezone="UTC",
        jour_onu=_now_utc().weekday(), pre_heure=_now_utc().hour, pre_minute=_now_utc().minute,
        enabled=True,
    )
    # ng_servers cache jamais rechargé -> "ghost" est inconnu.

    listener = ONUAlphaListener(FakeBot())
    try:
        await listener.onu_task.coro(listener)  # ne doit pas lever
    finally:
        listener.onu_task.cancel()


@pytest.mark.asyncio
async def test_onu_task_multi_server_isolation(patched_get_session):
    """Alpha + Delta configurés simultanément -> chacun reçoit son propre message, pas de fuite."""
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _register_server(patched_get_session, name="delta", guild_id=222)
    await _configure_pre_annonce_now("alpha", channel_id=555)
    await _configure_pre_annonce_now("delta", channel_id=666)

    bot = FakeBot()
    guild_alpha = bot.add_guild(111)
    channel_alpha = guild_alpha.add_channel(555)
    guild_delta = bot.add_guild(222)
    channel_delta = guild_delta.add_channel(666)

    listener = ONUAlphaListener(bot)
    try:
        await listener.onu_task.coro(listener)
    finally:
        listener.onu_task.cancel()

    assert len(channel_alpha.sent) == 1
    assert len(channel_delta.sent) == 1
    # Chaque salon n'a reçu qu'un seul message (pas celui de l'autre serveur).
    assert channel_alpha.sent[0] is not channel_delta.sent[0]


@pytest.mark.asyncio
async def test_onu_task_dedup_same_minute(patched_get_session):
    """Rejouer la boucle dans la même minute ne doit pas renvoyer le message 2x."""
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await _configure_pre_annonce_now("alpha", channel_id=555)

    bot = FakeBot()
    guild = bot.add_guild(111)
    channel = guild.add_channel(555)

    listener = ONUAlphaListener(bot)
    try:
        await listener.onu_task.coro(listener)
        await listener.onu_task.coro(listener)
        await listener.onu_task.coro(listener)
    finally:
        listener.onu_task.cancel()

    assert len(channel.sent) == 1


# ══════════════════════════════════════════════════════════════════════════
# 🌐 API site — résolution guild_id -> server, contrat externe inchangé
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_site_get_config_returns_none_for_unknown_guild(patched_get_session):
    assert await site_onu_mgr.get_config(999) is None


@pytest.mark.asyncio
async def test_site_update_full_config_unknown_guild_raises(patched_get_session):
    with pytest.raises(ValueError):
        await site_onu_mgr.update_full_config({"guild_id": 999, "channel_id": 1})


@pytest.mark.asyncio
async def test_site_update_and_get_config_roundtrip_via_guild_id(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)

    result = await site_onu_mgr.update_full_config({
        "guild_id": 111,
        "channel_id": 42,
        "role_id": 43,
        "ping_list": {"1": 1, "2": 2},
    })
    assert result["guild_id"] == 111
    assert result["channel_id"] == 42

    fetched = await site_onu_mgr.get_config(111)
    assert fetched is not None
    assert fetched["guild_id"] == 111
    assert fetched["channel_id"] == 42
    assert set(fetched["ping_list"].keys()) == {"1", "2"}

    # La config a bien été écrite sous la clé 'alpha' côté bot (même source de vérité).
    bot_side_cfg = await onu_mgr.load_onu_config("alpha")
    assert bot_side_cfg["channel_id"] == 42


@pytest.mark.asyncio
async def test_site_add_and_remove_ping_via_guild_id(patched_get_session):
    await _register_server(patched_get_session, name="alpha", guild_id=111)
    await site_onu_mgr.update_full_config({"guild_id": 111, "channel_id": 1})

    await site_onu_mgr.add_ping(111, 500, "Bob")
    members = await onu_mgr.get_onu_ping_members("alpha")
    assert members == [500]

    await site_onu_mgr.remove_ping(111, 500)
    assert await onu_mgr.get_onu_ping_members("alpha") == []
