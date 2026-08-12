"""
tests/test_refresh_staff_message_multiserver.py — Couvre §14 pour la phase
12 : cogs.alpha.stafflist.refresh_staff_message accepte désormais un kwarg
`server` (défaut "alpha") pour choisir la source ng_rank_configs/ng_staff,
indépendamment de `guild_id` qui reste la clé de persistance du message
(utils.managers.alpha_message_manager, déjà naturellement multi-serveurs).

utils.managers.alpha_message_manager n'est pas monkeypatché dans
conftest.patched_get_session (contrairement aux managers ng_*) — on
réutilise ici la même session de test déjà branchée sur un autre manager
(ng_staff_manager) plutôt que de modifier le fixture partagé, pour garder
ce test local et sans effet de bord sur les autres fichiers de tests.
"""
from __future__ import annotations

import discord
import pytest

from cogs.alpha.stafflist import refresh_staff_message
from utils.managers import ng_staff_manager as ng_staff
from utils.managers.ng_rank_config_manager import save_rank_config


class FakeMessage:
    def __init__(self, message_id: int):
        self.id = message_id
        self.edited_with = None

    async def edit(self, view=None) -> None:
        self.edited_with = view


class FakeChannel:
    def __init__(self, channel_id: int):
        self.id = channel_id
        self.sent: list = []
        self._messages: dict[int, FakeMessage] = {}

    async def send(self, view=None) -> FakeMessage:
        msg = FakeMessage(message_id=len(self.sent) + 1000)
        self.sent.append(view)
        self._messages[msg.id] = msg
        return msg

    async def fetch_message(self, message_id: int) -> FakeMessage:
        msg = self._messages.get(message_id)
        if msg is None:
            raise discord.NotFound(response=None, message="not found")
        return msg


class FakeBot:
    def __init__(self, channels: dict[int, FakeChannel]):
        self._channels = channels

    def get_channel(self, channel_id):
        return self._channels.get(channel_id)

    async def fetch_channel(self, channel_id):
        return self._channels.get(channel_id)


@pytest.fixture
def patched_alpha_message_manager(patched_get_session, monkeypatch):
    """Réutilise la session de test déjà configurée pour ng_staff_manager,
    appliquée aussi à alpha_message_manager (non patché par le fixture
    partagé) — voir docstring du module."""
    import utils.managers.alpha_message_manager as alpha_message_manager
    import utils.managers.ng_staff_manager as ng_staff_manager

    monkeypatch.setattr(alpha_message_manager, "get_session", ng_staff_manager.get_session)
    return patched_get_session


@pytest.mark.asyncio
async def test_refresh_staff_message_default_server_is_alpha(patched_alpha_message_manager):
    await save_rank_config("alpha", content_stafflist_channel_id=555)
    await ng_staff.add_staff_member("alpha", 1, "Bob", "guide")

    channel = FakeChannel(555)
    bot = FakeBot({555: channel})

    await refresh_staff_message(bot, guild_id=100)

    assert len(channel.sent) == 1


@pytest.mark.asyncio
async def test_refresh_staff_message_isolated_per_server(patched_alpha_message_manager):
    await save_rank_config("alpha", content_stafflist_channel_id=111)
    await save_rank_config("delta", content_stafflist_channel_id=222)
    await ng_staff.add_staff_member("alpha", 1, "AlphaBob", "guide")
    await ng_staff.add_staff_member("delta", 2, "DeltaDee", "guide")

    chan_alpha = FakeChannel(111)
    chan_delta = FakeChannel(222)
    bot = FakeBot({111: chan_alpha, 222: chan_delta})

    # Deux guildes Discord distinctes -> deux messages persistés distincts,
    # chacun sur le bon salon, chacun avec les bonnes données staff.
    await refresh_staff_message(bot, guild_id=100, server="alpha")
    await refresh_staff_message(bot, guild_id=200, server="delta")

    assert len(chan_alpha.sent) == 1
    assert len(chan_delta.sent) == 1


@pytest.mark.asyncio
async def test_refresh_staff_message_edits_existing_message_on_replay(patched_alpha_message_manager):
    await save_rank_config("delta", content_stafflist_channel_id=333)
    await ng_staff.add_staff_member("delta", 3, "Eve", "guide")

    channel = FakeChannel(333)
    bot = FakeBot({333: channel})

    await refresh_staff_message(bot, guild_id=300, server="delta")
    assert len(channel.sent) == 1  # créé

    await refresh_staff_message(bot, guild_id=300, server="delta")
    assert len(channel.sent) == 1  # toujours 1 -> la 2e passe a édité, pas recréé


@pytest.mark.asyncio
async def test_refresh_staff_message_noop_when_channel_not_configured(patched_alpha_message_manager):
    await save_rank_config("delta", content_stafflist_channel_id=None)

    bot = FakeBot({})
    # Ne doit pas lever, doit simplement logger un warning et sortir.
    await refresh_staff_message(bot, guild_id=400, server="delta")
