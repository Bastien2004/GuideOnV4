"""
utils/error_handler.py — Gestion des erreurs de commandes.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.container_universel import error_container

# ============================================================
# 📂 Constantes
# ============================================================

log = logging.getLogger(__name__)

DM_ERROR_MESSAGE = ("Cette commande ne peut être __utilisée__ que dans un **serveur Discord**.")


# ============================================================
# 🧩 Fonctions
# ============================================================

async def handle_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError,) -> None:
    """Handler appelé par les @command.error dans les cogs"""
    if interaction.response.is_done():
        send = interaction.followup.send
    else:
        send = interaction.response.send_message

    # ⏳ Cooldown
    if isinstance(error, app_commands.CommandOnCooldown):
        return await send(
            view=error_container(f"Doucement ! Attends `{round(error.retry_after, 1)}s` avant de réutiliser cette commande."),
            ephemeral=True,
        )

    original = getattr(error, "original", error)

    log.error("Command error | guild=%s user=%s error=%r", interaction.guild_id, interaction.user.id, original)

    # 🚫 MP interdit
    if isinstance(error, app_commands.NoPrivateMessage):
        return await send(view=error_container(DM_ERROR_MESSAGE), ephemeral=True)

    if isinstance(error, app_commands.TransformerError):
        if interaction.guild is None:
            return await send(view=error_container(DM_ERROR_MESSAGE), ephemeral=True)

    if isinstance(original, AttributeError) and interaction.guild is None:
        return await send(view=error_container(DM_ERROR_MESSAGE), ephemeral=True)

    # ❓ Erreur inconnue
    return await send(
        view=error_container("Une **erreur imprévue** est survenue lors de l'exécution de la commande."),
        ephemeral=True,
    )