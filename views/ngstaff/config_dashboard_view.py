"""
views/ngstaff/config_dashboard_view.py — Hub de configuration /ngstaff config.

Refonte multi-serveurs phase 11 : équivalent de views/alpha/config_dashboard_view.py
mais générique à tout serveur NG (le `server` est résolu dynamiquement à
l'exécution par la commande /ngstaff config via utils.ng_server_check, pas
câblé en dur). Volontairement limité aux 4 systèmes déjà généralisés en
phase 11 (§13 du prompt de refonte) : Rank/Derank, ONU, Notations,
Role Réaction. Les autres sections du hub Alpha (Contenu, Events) sont
spécifiques au Discord Alpha historique et ne sont pas exposées ici.
"""

from __future__ import annotations

import discord
from discord import Interaction
from discord.ui import ActionRow, Container, LayoutView, Separator, TextDisplay

from utils.managers.ng_rank_config_manager import load_rank_config

_OPTIONS = [
    discord.SelectOption(
        label="Système Rank / Derank",
        value="rank",
        description="Configuration du système de rank/derank.",
        emoji="⚙️",
    ),
    discord.SelectOption(
        label="Système ONU",
        value="onu",
        description="Boucle automatique, pré-annonce, ping MP",
        emoji="🌐",
    ),
    discord.SelectOption(
        label="Système Notations",
        value="notations",
        description="Configuration du système de notations.",
        emoji="📋",
    ),
    discord.SelectOption(
        label="🔔 Rôle Réaction",
        value="role_react",
        description="Boutons de notification auto-assignés par les membres",
        emoji="🔔",
    ),
]


class NGStaffConfigDashboardView(LayoutView):
    """Interface de sélection des systèmes à configurer, pour un serveur NG
    donné (résolu dynamiquement, pas forcément "alpha")."""

    def __init__(self, guild_id: int, server: str, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'**auteur** peut utiliser ce menu.", ephemeral=True
            )
            return False
        return True

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay(
            f"# <:parametre:1495444004328706059> Configuration — `{self.server}`"
        ))
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
            cfg = await load_rank_config(self.server)
            from views.alpha.config_alpha_view import ConfigRankView
            await interaction.response.edit_message(
                view=ConfigRankView(
                    self.guild_id, self.server, cfg, self.owner_id, dashboard="ngstaff"
                )
            )
        elif value == "onu":
            from utils.managers.ng_onu_manager import load_onu_config
            from views.alpha.config_onu_view import ONUConfigView
            cfg = await load_onu_config(self.server)
            await interaction.response.edit_message(
                view=ONUConfigView(
                    self.guild_id, self.server, cfg, self.owner_id, dashboard="ngstaff"
                )
            )
        elif value == "notations":
            from utils.managers.ng_nota_manager import load_nota_config
            from views.alpha.config_nota_view import NotaConfigView
            cfg = await load_nota_config(self.server)
            await interaction.response.edit_message(
                view=NotaConfigView(
                    self.guild_id, self.server, cfg, self.owner_id, dashboard="ngstaff"
                )
            )
        elif value == "role_react":
            from utils.managers.ng_role_react_manager import get_rr_entries, load_rr_config
            from views.alpha.config_role_react_view import RoleReactConfigView
            rr_cfg = await load_rr_config(self.server)
            entries = await get_rr_entries(self.server)
            await interaction.response.edit_message(
                view=RoleReactConfigView(
                    self.guild_id, self.server, rr_cfg, entries, self.owner_id, dashboard="ngstaff"
                )
            )
        else:
            await interaction.response.send_message(
                "Ce système n'est pas encore disponible. 🔜", ephemeral=True
            )
