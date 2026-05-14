"""
Handler global d'erreurs pour les slash commands.

Génère un error_id corrélé entre les logs serveur et le message utilisateur.
Résout le problème OBS-002 de l'audit V3.

Usage : appelé depuis bot.py setup_hook() via register_error_handlers(bot).
"""
from __future__ import annotations

import logging
import uuid

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)


class GuideONError(Exception):
    """Exception métier — affichée telle quelle à l'utilisateur."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def register_error_handlers(bot: commands.Bot) -> None:
    """À appeler depuis setup_hook."""

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        # Erreur métier connue → message clean
        if isinstance(error, app_commands.CommandInvokeError) and isinstance(
            error.original, GuideONError
        ):
            msg = f"❌ {error.original.user_message}"
        elif isinstance(error, app_commands.MissingPermissions):
            msg = f"❌ Permissions manquantes : {', '.join(error.missing_permissions)}"
        elif isinstance(error, app_commands.CheckFailure):
            msg = "❌ Tu n'as pas accès à cette commande."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Doucement ! Réessaie dans {error.retry_after:.0f}s."
        else:
            # Erreur inconnue : log avec ID corrélé
            error_id = uuid.uuid4().hex[:8]
            log.error(
                "AppCommand error [%s] from %s in %s: %s",
                error_id,
                interaction.user,
                interaction.guild.name if interaction.guild else "DM",
                error,
                exc_info=True,
            )
            msg = f"❌ Erreur inattendue. Donne ce code à un admin : `{error_id}`"

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            log.exception("Impossible de répondre à l'erreur de commande")
