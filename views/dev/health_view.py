"""
views/dev/health_view.py — Panel d'état de santé du bot pour /dev health.

2026-10-06 (Paul, refonte) : remplace l'ancienne vue plate (LayoutView
statique, 6 TextDisplay) par un panel BaseLayoutView interactif avec un
bouton "Actualiser" (relance utils.health.gather_health_data en place,
sans refaire /dev health) et une nouvelle section "Activité" (commandes
les plus utilisées, serveurs actifs, bans actifs).
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from utils.health import HealthData, gather_health_data, status_emoji
from views._components.base_view import BaseLayoutView

EMOJI_REFRESH = "🔄"
_PODIUM_MEDALS = ("🥇", "🥈", "🥉")


def _format_latency(ms: float | None) -> str:
    return f"{ms:.0f}ms" if ms is not None else "—"


def _format_podium(podium: list[dict]) -> str:
    if not podium:
        return "*Aucune commande enregistrée.*"
    lines = []
    for i, entry in enumerate(podium):
        medal = _PODIUM_MEDALS[i] if i < len(_PODIUM_MEDALS) else "▫️"
        lines.append(f"{medal} `/{entry['command_name']}` — {entry['total']} utilisation(s)")
    return "\n".join(lines)


# ============================================================
# 🧩 Panel principal
# ============================================================

class HealthView(BaseLayoutView):
    """Panel d'état de santé — système, Discord, infra, activité."""

    def __init__(self, *, bot: discord.Client, data: HealthData, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=600)
        self.bot = bot
        self.data = data
        self._build()

    @classmethod
    async def build(cls, *, bot: discord.Client, owner_id: int) -> "HealthView":
        data = await gather_health_data(bot)
        return cls(bot=bot, data=data, owner_id=owner_id)

    def _build(self) -> None:
        data = self.data
        container = Container()

        container.add_item(TextDisplay("# 🤖 GuideOn Health"))
        container.add_item(Separator())

        container.add_item(TextDisplay("### 🧬 __Environnement__ :"))
        container.add_item(TextDisplay(
            f"**Version :** V4\n"
            f"**Python :** {data.python_version} • **discord.py :** {data.discordpy_version}\n"
            f"**Uptime :** {data.uptime_str} • **Ping Discord :** {data.ping_ms}ms"
        ))
        container.add_item(Separator())

        container.add_item(TextDisplay("### 🌐 __Discord__ :"))
        container.add_item(TextDisplay(
            f"**Serveurs :** {data.guild_count} • **Utilisateurs :** {data.user_count}\n"
            f"**Cogs chargés :** {data.cogs_count} • **Slash Commands :** {data.commands_count}"
        ))
        container.add_item(Separator())

        container.add_item(TextDisplay("### 🖥️ __Ressources__ :"))
        container.add_item(TextDisplay(
            f"**RAM :** {data.ram_mb:.0f} MB\n"
            f"**CPU :** {data.cpu_percent:.1f} %\n"
            f"**Threads :** {data.thread_count}"
        ))
        container.add_item(Separator())

        container.add_item(TextDisplay("### 🩺 __Infrastructure__ :"))
        container.add_item(TextDisplay(
            f"**Database :** {status_emoji(data.db_ok)} ({_format_latency(data.db_ms)})\n"
            f"**API :** {status_emoji(data.api_ok)} ({_format_latency(data.api_ms)})"
        ))
        container.add_item(Separator())

        container.add_item(TextDisplay("### 📊 __Activité__ :"))
        container.add_item(TextDisplay(
            f"**Commandes exécutées (total) :** {data.commands_grand_total}\n"
            f"**Serveurs actifs (7j) :** {data.active_guilds_7d}\n"
            f"**Bans actifs :** {data.active_bans_count}\n\n"
            f"**Commandes les plus utilisées :**\n{_format_podium(data.commands_podium)}"
        ))
        container.add_item(Separator())

        refresh_btn = Button(label="Actualiser", style=ButtonStyle.secondary, emoji=EMOJI_REFRESH)
        refresh_btn.callback = self._cb_refresh
        container.add_item(ActionRow(refresh_btn))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _cb_refresh(self, interaction: discord.Interaction) -> None:
        view = await HealthView.build(bot=self.bot, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)


# ============================================================
# 🧭 Point d'entrée pour cogs/dev/health.py
# ============================================================

async def build_health_view(bot: discord.Client, owner_id: int) -> HealthView:
    """Construit directement le panel (appelle gather_health_data)."""
    return await HealthView.build(bot=bot, owner_id=owner_id)
