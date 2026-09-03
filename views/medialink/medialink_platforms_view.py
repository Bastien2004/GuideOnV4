"""
views/medialink/medialink_platforms_view.py — ajout/suppression d'une
connexion (compte/chaîne suivi sur une plateforme), §6.

STUB : la structure exacte de ce flux (choix de plateforme → saisie de
l'identifiant → validate_account() du Provider → confirmation) dépend
des premiers Providers réels (partie API de Bastien), pas encore
disponibles. Le contrat DB (utils.managers.medialink_manager.
add_connection / remove_connection) et le contrat Provider
(utils/medialink/providers/base.py) sont eux déjà stables, donc cette
vue peut être branchée dessus dès qu'un Provider concret existe.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, SelectOption
from discord.ui import Button, Container, Select, Separator, TextDisplay

from utils.db.models.medialink_connection import MediaPlatform
from views._components.base_view import BaseLayoutView

_PLATFORM_OPTIONS = [
    SelectOption(label="YouTube", value=MediaPlatform.YOUTUBE.value, emoji="▶️"),
    SelectOption(label="Twitch", value=MediaPlatform.TWITCH.value, emoji="🟣"),
    SelectOption(label="TikTok", value=MediaPlatform.TIKTOK.value, emoji="🎵"),
    SelectOption(label="Reddit", value=MediaPlatform.REDDIT.value, emoji="👽"),
]


class AddConnectionView(BaseLayoutView):
    """Étape 1 : choix de la plateforme à connecter."""

    def __init__(self, *, guild_id: int, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild_id = guild_id
        self._build()

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay("# ➕ Ajouter une connexion"))
        container.add_item(Separator())
        container.add_item(TextDisplay("Choisis la plateforme à connecter :"))

        select = Select(placeholder="Plateforme", options=_PLATFORM_OPTIONS)
        select.callback = self._cb_platform_chosen
        container.add_item(select)

        back_btn = Button(label="Retour", style=ButtonStyle.secondary)
        back_btn.callback = self._cb_back
        container.add_item(back_btn)

        self.add_item(container)

    async def _cb_platform_chosen(self, interaction: discord.Interaction) -> None:
        # TODO : ouvrir un Modal de saisie de l'identifiant du compte,
        # puis appeler BaseMediaProvider.validate_account() avant de
        # persister via utils.managers.medialink_manager.add_connection().
        raise NotImplementedError(
            "platforms._cb_platform_chosen — saisie identifiant + validate_account() (roadmap A1)"
        )

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)
