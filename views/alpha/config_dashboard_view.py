"""
views/alpha/config_dashboard_view.py — Hub de configuration Alpha.
"""

from __future__ import annotations

import discord
from discord import Interaction
from discord.ui import ActionRow, Container, LayoutView, Separator, TextDisplay

from utils.managers.alpha_rank_config_manager import load_rank_config


# ════════════════════════════════════════════════════════════
# 🏠 Dashboard principal
# ════════════════════════════════════════════════════════════

_OPTIONS = [
    discord.SelectOption(
        label="Système Rank / Derank",
        value="rank",
        description="Configuration du système de rank/derank.",
        emoji="⚙️",
    ),
    discord.SelectOption(
        label="Contenu Discord",
        value="content",
        description="Configuration des systèmes du Discord Alpha. ",
        emoji="📢",
    ),
    discord.SelectOption(
        label="🎮 Système Events",
        value="events",
        description="start_event, event_list, gestion des statuts",
        emoji="🎮",
    ),
    discord.SelectOption(
        label="🔔 Rôle Réaction",
        value="role_react",
        description="Boutons de notification auto-assignés par les membres",
        emoji="🔔",
    ),
    discord.SelectOption(
        label="Système Notations",
        value="notations",
        description="Configuration du système de notations.",
        emoji="📋",
    ),
    discord.SelectOption(
        label="Système ONU",
        value="onu",
        description="Boucle automatique, pré-annonce, ping MP",
        emoji="🌐",
    ),
]


class ConfigDashboardView(LayoutView):
    """Interface de sélection des systèmes à configurer."""

    def __init__(self, guild_id: int, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Seul l'**auteur** peut utiliser ce menu.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# <:parametre:1495444004328706059> Configuration Alpha"))
        c.add_item(Separator())

        c.add_item(TextDisplay("Sélectionnez un système à configurer."))
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
        elif value == "onu":
            from utils.managers.alpha_onu_manager import load_onu_config
            from views.alpha.config_onu_view import ONUConfigView
            cfg = await load_onu_config(self.guild_id)
            await interaction.response.edit_message(
                view=ONUConfigView(self.guild_id, cfg, self.owner_id)
            )
        elif value == "events":
            from utils.managers.alpha_event_config_manager import load_event_config
            from views.alpha.config_event_view import EventConfigView
            ev_cfg = await load_event_config(self.guild_id)
            await interaction.response.edit_message(
                view=EventConfigView(self.guild_id, ev_cfg, self.owner_id)
            )
        elif value == "role_react":
            from utils.managers.alpha_role_react_manager import load_rr_config, get_rr_entries
            from views.alpha.config_role_react_view import RoleReactConfigView
            rr_cfg = await load_rr_config(self.guild_id)
            entries = await get_rr_entries(self.guild_id)
            await interaction.response.edit_message(
                view=RoleReactConfigView(self.guild_id, rr_cfg, entries, self.owner_id)
            )
        elif value == "notations":
            from utils.managers.alpha_nota_manager import load_nota_config
            from views.alpha.config_nota_view import NotaConfigView
            cfg = await load_nota_config(self.guild_id)
            await interaction.response.edit_message(
                view=NotaConfigView(self.guild_id, cfg, self.owner_id)
            )
        else:
            await interaction.response.send_message("Ce système n'est pas encore disponible. 🔜", ephemeral=True)