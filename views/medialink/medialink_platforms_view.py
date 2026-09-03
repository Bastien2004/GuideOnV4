"""
views/medialink/medialink_platforms_view.py — ajout/suppression d'une
connexion (compte/chaîne suivi sur une plateforme), §6.

── MODE ACTUEL : AJOUT MANUEL (provisoire) ──────────────────────────
Tant que les Providers réels (partie API de Bastien) ne sont pas
branchés, il n'y a aucun moyen de valider un compte côté plateforme
(validate_account()/get_account()). Pour que Paul puisse quand même
peaufiner l'UI (dashboard, règles...), ce fichier permet d'ajouter une
connexion "à la main" via un Modal : external_id + nom affiché saisis
directement, SANS validation côté plateforme. C'est un mode de test,
pas le flux final.

QUAND LES PROVIDERS EXISTERONT (roadmap A1) — à faire à ce moment-là :
  - Appeler BaseMediaProvider.validate_account(external_id) avant de
    persister (refuser si False).
  - Appeler get_account(external_id) pour pré-remplir
    external_username/avatar_url/external_url au lieu de les faire
    saisir à la main.
  - Probablement garder CE flux manuel en plus, en option "avancé",
    plutôt que le supprimer — pratique pour du debug.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, Select, Separator, TextDisplay

from utils.db.models.medialink_connection import MediaPlatform
from utils.managers import medialink_manager as medialink_mgr
from views._components.base_view import BaseLayoutView

EMOJI_BACK = "<:retour:1515658955190308995>"

_PLATFORM_OPTIONS = [
    SelectOption(label="YouTube", value=MediaPlatform.YOUTUBE.value, emoji="▶️"),
    SelectOption(label="Twitch", value=MediaPlatform.TWITCH.value, emoji="🟣"),
    SelectOption(label="TikTok", value=MediaPlatform.TIKTOK.value, emoji="🎵"),
    SelectOption(label="Reddit", value=MediaPlatform.REDDIT.value, emoji="👽"),
]


class AddConnectionModal(discord.ui.Modal):
    """Saisie manuelle d'une connexion — cf. note en tête de fichier."""

    def __init__(self, *, guild_id: int, owner_id: int, platform: str):
        super().__init__(title="Ajouter une connexion (mode manuel)")
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.platform = platform

        self.external_id_input = discord.ui.TextInput(
            label="Identifiant du compte (external_id)",
            placeholder="Ex : ID de chaîne YouTube, pseudo Twitch, subreddit...",
            required=True,
            max_length=128,
        )
        self.username_input = discord.ui.TextInput(
            label="Nom affiché (optionnel)",
            required=False,
            max_length=255,
        )
        self.add_item(self.external_id_input)
        self.add_item(self.username_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await medialink_mgr.add_connection(
            self.guild_id,
            self.platform,
            self.external_id_input.value.strip(),
            external_username=self.username_input.value.strip() or None,
        )

        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)


class AddConnectionView(BaseLayoutView):
    """Étape 1 : choix de la plateforme à connecter."""

    def __init__(self, *, guild_id: int, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild_id = guild_id
        self._build()

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay("# ➕ Ajouter une connexion"))
        container.add_item(
            TextDisplay(
                "-# Mode manuel (provisoire) : pas de vérification côté "
                "plateforme tant que les providers ne sont pas branchés."
            )
        )
        container.add_item(Separator())
        container.add_item(TextDisplay("**Choisis la plateforme à connecter :**"))

        select = Select(placeholder="Plateforme", options=_PLATFORM_OPTIONS)
        select.callback = self._cb_platform_chosen
        container.add_item(ActionRow(select))

        container.add_item(Separator())
        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back
        container.add_item(ActionRow(back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _cb_platform_chosen(self, interaction: discord.Interaction) -> None:
        platform = interaction.data["values"][0]
        modal = AddConnectionModal(guild_id=self.guild_id, owner_id=self.owner_id, platform=platform)
        await interaction.response.send_modal(modal)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)