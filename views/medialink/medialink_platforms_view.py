"""
views/medialink/medialink_platforms_view.py — ajout/suppression d'une
connexion (compte/chaîne suivi sur une plateforme), §6.

── YOUTUBE : PROVIDER RÉEL BRANCHÉ (2026-09) ─────────────────────────
utils/medialink/providers/youtube.py n'est plus un stub (Bastien) : pour
YouTube, AddConnectionModal appelle désormais get_account(external_id)
(YouTubeProvider) avant de persister — un seul appel API qui fait à la
fois la validation (lève ProviderNotFoundError si la chaîne n'existe
pas) et le pré-remplissage de external_username/avatar_url/external_url,
donc plus besoin de demander le nom affiché à la main pour YouTube (cf.
_submit_youtube ci-dessous). validate_account() séparément n'est donc
plus nécessaire ici (get_account() fait déjà l'équivalent).

── TWITCH / TIKTOK / REDDIT : TOUJOURS EN AJOUT MANUEL (provisoire) ──
Leurs Providers respectifs (utils/medialink/providers/{twitch,tiktok,
reddit}.py) sont encore des stubs (NotImplementedError) — ces 3
plateformes gardent donc le flux manuel d'origine : external_id + nom
affiché saisis à la main, SANS validation côté plateforme. À basculer
plateforme par plateforme au même principe que YouTube au fur et à
mesure que Bastien livre chaque Provider (cf. _submit_manual).
"""
from __future__ import annotations

import logging

import discord
import httpx
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, Select, Separator, TextDisplay
from sqlalchemy.exc import IntegrityError

from utils.container_universel import error_container, send_ephemeral
from utils.db.models.medialink_connection import MediaPlatform
from utils.managers import medialink_manager as medialink_mgr
from utils.medialink.providers.youtube import (
    ProviderAuthError,
    ProviderNotFoundError,
    YouTubeProvider,
)
from views._components.base_view import BaseLayoutView

log = logging.getLogger(__name__)

EMOJI_BACK = "<:retour:1515658955190308995>"

_PLATFORM_OPTIONS = [
    SelectOption(label="YouTube", value=MediaPlatform.YOUTUBE.value, emoji="▶️"),
    SelectOption(label="Twitch", value=MediaPlatform.TWITCH.value, emoji="🟣"),
    SelectOption(label="TikTok", value=MediaPlatform.TIKTOK.value, emoji="🎵"),
    SelectOption(label="Reddit", value=MediaPlatform.REDDIT.value, emoji="👽"),
]


class AddConnectionModal(discord.ui.Modal):
    """Saisie d'une connexion. YouTube passe par le Provider réel
    (validation + pré-remplissage via l'API, cf. _submit_youtube) ;
    Twitch/TikTok/Reddit restent en saisie manuelle tant que leurs
    Providers sont des stubs (cf. _submit_manual, et note en tête de
    fichier)."""

    def __init__(self, *, guild_id: int, owner_id: int, platform: str):
        is_youtube = platform == MediaPlatform.YOUTUBE.value
        super().__init__(
            title="Ajouter une chaîne YouTube" if is_youtube else "Ajouter une connexion (mode manuel)"
        )
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.platform = platform

        if is_youtube:
            # Un seul champ : get_account() (appelé dans _submit_youtube)
            # valide le compte ET renvoie nom/avatar/URL — plus besoin de
            # les faire saisir à la main pour cette plateforme.
            self.external_id_input = discord.ui.TextInput(
                label="ID de chaîne ou @handle YouTube",
                placeholder="Ex : UCxxxxxxxxxxxxxxxxxxxxxx ou @NomDeChaine",
                required=True,
                max_length=128,
            )
            self.username_input = None
            self.add_item(self.external_id_input)
        else:
            self.external_id_input = discord.ui.TextInput(
                label="Identifiant du compte (external_id)",
                placeholder="Ex : pseudo Twitch, subreddit...",
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
        external_id = self.external_id_input.value.strip()

        if self.platform == MediaPlatform.YOUTUBE.value:
            await self._submit_youtube(interaction, external_id)
        else:
            await self._submit_manual(interaction, external_id)

    async def _submit_manual(self, interaction: discord.Interaction, external_id: str) -> None:
        try:
            await medialink_mgr.add_connection(
                self.guild_id,
                self.platform,
                external_id,
                external_username=self.username_input.value.strip() or None,
            )
        except IntegrityError:
            await interaction.response.send_message(
                view=error_container("Cette connexion existe déjà sur ce serveur."),
                ephemeral=True,
            )
            return

        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)

    async def _submit_youtube(self, interaction: discord.Interaction, external_id: str) -> None:
        # L'appel API peut prendre plus que les 3s allouées à une réponse
        # d'interaction directe — defer() d'abord, comme le reste du bot
        # le fait déjà pour un appel externe depuis un Modal/bouton (cf.
        # ex. views/ngstaff/config_role_react_view.py::_on_deploy).
        await interaction.response.defer(ephemeral=True)

        provider = YouTubeProvider()
        try:
            account = await provider.get_account(external_id)
        except ProviderNotFoundError:
            await send_ephemeral(
                interaction,
                error_container(
                    "Aucune chaîne YouTube trouvée pour cet identifiant. "
                    "Vérifie l'ID de chaîne (commence par `UC`) ou le `@handle`."
                ),
            )
            return
        except ProviderAuthError:
            log.error("[MEDIALINK] YouTube ProviderAuthError (clé API invalide/quota épuisé) | guild=%d", self.guild_id)
            await send_ephemeral(
                interaction,
                error_container(
                    "La clé API YouTube du bot est invalide ou son quota "
                    "quotidien est épuisé — réessaie plus tard ou préviens "
                    "un développeur."
                ),
            )
            return
        except httpx.HTTPError:
            log.exception("[MEDIALINK] Erreur réseau YouTube API | guild=%d", self.guild_id)
            await send_ephemeral(
                interaction,
                error_container("Impossible de contacter l'API YouTube pour le moment — réessaie plus tard."),
            )
            return
        finally:
            await provider.disconnect()

        try:
            await medialink_mgr.add_connection(
                self.guild_id,
                self.platform,
                account.external_id,
                external_username=account.username,
                external_url=account.url,
                avatar_url=account.avatar_url,
            )
        except IntegrityError:
            await send_ephemeral(
                interaction,
                error_container(f"**{account.username or external_id}** est déjà connectée sur ce serveur."),
            )
            return

        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await interaction.edit_original_response(view=view)


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
                "-# YouTube : vérifiée automatiquement (nom et avatar "
                "récupérés depuis la chaîne). Twitch, TikTok, Reddit : "
                "ajout manuel pour l'instant, sans vérification côté "
                "plateforme."
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