"""
views/medialink/medialink_platforms_view.py — ajout/suppression d'une
connexion (compte/chaîne suivi sur une plateforme), §6.
"""

from __future__ import annotations

import logging

import discord
import httpx
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, Select, Separator, TextDisplay
from sqlalchemy.exc import IntegrityError

from utils.container_universel import error_container, send_ephemeral, warning_container
from utils.db.models.medialink_connection import MediaPlatform
from utils.managers import medialink_manager as medialink_mgr
from utils.medialink import event_manager
from utils.medialink.providers.twitch import (
    ProviderAuthError as TwitchAuthError,
    ProviderNotFoundError as TwitchNotFoundError,
    TwitchProvider,
)
from utils.medialink.providers.youtube import (
    ProviderAuthError as YouTubeAuthError,
    ProviderNotFoundError as YouTubeNotFoundError,
    YouTubeProvider,
)
from views._components.base_view import BaseLayoutView

log = logging.getLogger(__name__)

EMOJI_BACK = "<:retour:1515658955190308995>"


_VERIFIED_PLATFORMS = (MediaPlatform.YOUTUBE.value, MediaPlatform.TWITCH.value)
_UNAVAILABLE_PREFIX = "__unavailable__"

_PLATFORM_LABELS: list[tuple[MediaPlatform, str, str]] = [
    (MediaPlatform.YOUTUBE, "YouTube", "▶️"),
    (MediaPlatform.TWITCH, "Twitch", "🟣"),
    (MediaPlatform.TIKTOK, "TikTok", "🎵"),
    (MediaPlatform.REDDIT, "Reddit", "👽"),
]


def _build_platform_options() -> list[SelectOption]:
    options: list[SelectOption] = []
    for platform, label, emoji in _PLATFORM_LABELS:
        if platform.value in medialink_mgr.BLOCKED_PLATFORMS:
            options.append(SelectOption(
                label=label,
                description="Bientôt disponible",
                value=f"{_UNAVAILABLE_PREFIX}{platform.value}",
                emoji=emoji,
            ))
        else:
            options.append(SelectOption(label=label, value=platform.value, emoji=emoji))
    return options


_PLATFORM_OPTIONS = _build_platform_options()


class AddConnectionModal(discord.ui.Modal):
    """Saisie d'une connexion. YouTube et Twitch passent par leur
    Provider réel (validation + pré-remplissage via l'API, cf.
    _submit_youtube / _submit_twitch) ; TikTok/Reddit restent en saisie
    manuelle tant que leurs Providers sont des stubs (cf. _submit_manual,
    et note en tête de fichier)."""

    def __init__(self, *, guild_id: int, owner_id: int, platform: str):
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.platform = platform

        if platform == MediaPlatform.YOUTUBE.value:
            super().__init__(title="Ajouter une chaîne YouTube")
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
        elif platform == MediaPlatform.TWITCH.value:
            super().__init__(title="Ajouter un compte Twitch")
            # Idem YouTube : get_account() (cf. _submit_twitch) résout le
            # pseudo en ID numérique et renvoie nom/avatar/URL.
            self.external_id_input = discord.ui.TextInput(
                label="Pseudo Twitch",
                placeholder="Ex : ninja ou @ninja",
                required=True,
                max_length=128,
            )
            self.username_input = None
            self.add_item(self.external_id_input)
        else:
            super().__init__(title="Ajouter une connexion (mode manuel)")
            self.external_id_input = discord.ui.TextInput(
                label="Identifiant du compte (external_id)",
                placeholder="Ex : subreddit...",
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
        elif self.platform == MediaPlatform.TWITCH.value:
            await self._submit_twitch(interaction, external_id)
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
        await interaction.response.defer(ephemeral=True)

        provider = YouTubeProvider()
        try:
            account = await provider.get_account(external_id)
        except YouTubeNotFoundError:
            await send_ephemeral(
                interaction,
                error_container(
                    "Aucune chaîne YouTube trouvée pour cet identifiant. "
                    "Vérifie l'ID de chaîne (commence par `UC`) ou le `@handle`."
                ),
            )
            return
        except YouTubeAuthError:
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
            connection = await medialink_mgr.add_connection(
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
        try:
            await provider.connect(account.external_id)
            baseline_events = await provider.fetch_events()
            await event_manager.seed_baseline_events(connection["id"], baseline_events)
        except Exception:
            log.warning(
                "[MEDIALINK] Échec de l'immunisation anti-rétroactif (baseline) guild=%d connection=%s",
                self.guild_id, connection["id"], exc_info=True,
            )
        finally:
            await provider.disconnect()

        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await interaction.edit_original_response(view=view)

    async def _submit_twitch(self, interaction: discord.Interaction, external_id: str) -> None:
        await interaction.response.defer(ephemeral=True)

        provider = TwitchProvider()
        try:
            account = await provider.get_account(external_id)
        except TwitchNotFoundError:
            await send_ephemeral(
                interaction,
                error_container("Aucun compte Twitch trouvé pour ce pseudo. Vérifie l'orthographe."),
            )
            return
        except TwitchAuthError:
            log.error("[MEDIALINK] Twitch ProviderAuthError (client_id/secret invalide) | guild=%d", self.guild_id)
            await send_ephemeral(
                interaction,
                error_container(
                    "L'authentification Twitch du bot a échoué "
                    "(client_id/secret invalide) — réessaie plus tard ou "
                    "préviens un développeur."
                ),
            )
            return
        except httpx.HTTPError:
            log.exception("[MEDIALINK] Erreur réseau Twitch API | guild=%d", self.guild_id)
            await send_ephemeral(
                interaction,
                error_container("Impossible de contacter l'API Twitch pour le moment — réessaie plus tard."),
            )
            return
        finally:
            await provider.disconnect()

        try:
            connection = await medialink_mgr.add_connection(
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
        try:
            await provider.connect(account.external_id)
            baseline_events = await provider.fetch_events()
            await event_manager.seed_baseline_events(connection["id"], baseline_events)
        except Exception:
            log.warning(
                "[MEDIALINK] Échec de l'immunisation anti-rétroactif (baseline) guild=%d connection=%s",
                self.guild_id, connection["id"], exc_info=True,
            )
        finally:
            await provider.disconnect()

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
                "-# YouTube et Twitch : vérifiés automatiquement (nom et "
                "avatar récupérés depuis le compte). TikTok, Reddit : "
                "bientôt disponibles."
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

        if platform.startswith(_UNAVAILABLE_PREFIX):
            await interaction.response.send_message(
                view=warning_container("🚧 Cette plateforme sera **bientôt disponible**."),
                ephemeral=True,
            )
            return

        modal = AddConnectionModal(guild_id=self.guild_id, owner_id=self.owner_id, platform=platform)
        await interaction.response.send_modal(modal)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)