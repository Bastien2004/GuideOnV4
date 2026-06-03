"""
views/alpha/config_dashboard_view.py — Hub de configuration Alpha.

Dashboard principal ouvert par /dev config_alpha.
Un select menu liste tous les systèmes configurables.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Container, LayoutView, Separator, TextDisplay

from utils.managers.alpha_rank_config_manager import load_rank_config


# ════════════════════════════════════════════════════════════
# 🏠 Dashboard principal
# ════════════════════════════════════════════════════════════

_OPTIONS = [
    discord.SelectOption(
        label="Système Rank / Derank",
        value="rank",
        description="Salons d'annonce, rôles Discord par grade, pings",
        emoji="⚙️",
    ),
    discord.SelectOption(
        label="Contenu Discord",
        value="content",
        description="Salons, pings et emojis de Nous rejoindre, Index, Règle interne",
        emoji="📢",
    ),
    discord.SelectOption(
        label="Système Notations",
        value="notations",
        description="Bientôt disponible",
        emoji="📋",
    ),
    discord.SelectOption(
        label="Système ONU",
        value="onu",
        description="Bientôt disponible",
        emoji="🌐",
    ),
]


class ConfigDashboardView(LayoutView):
    """Hub de configuration — select menu des systèmes Alpha."""

    def __init__(self, guild_id: int, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'auteur peut utiliser ce menu.", ephemeral=True
            )
            return False
        return True

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# ⚙️ Configuration Alpha — Hub"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Sélectionnez un système dans le menu ci-dessous pour le configurer."
        ))
        c.add_item(Separator())

        select = discord.ui.Select(
            placeholder="Choisir un système...",
            options=_OPTIONS,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        c.add_item(ActionRow(select))

        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_select(self, interaction: Interaction) -> None:
        value = interaction.data["values"][0]

        if value == "rank":
            cfg = await load_rank_config(self.guild_id)
            from views.alpha.config_alpha_view import ConfigRankView
            await interaction.response.edit_message(
                view=ConfigRankView(self.guild_id, cfg, self.owner_id)
            )
        elif value == "content":
            cfg = await load_rank_config(self.guild_id)
            from views.alpha.config_content_view import ConfigContentView
            await interaction.response.edit_message(
                view=ConfigContentView(self.guild_id, cfg, self.owner_id)
            )
        else:
            await interaction.response.send_message(
                "Ce système n'est pas encore disponible. 🔜", ephemeral=True
            )