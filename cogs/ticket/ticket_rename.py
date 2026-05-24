"""
Commande /ticket rename — Permet renommer un ticket existant.
"""

from __future__ import annotations

import logging
import time

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

from utils.managers import ticket_manager as tm
from views.ticket._helpers import closed_name, is_staff, strip_closed_prefix, try_rename

log = logging.getLogger(__name__)

# ============================================================
# 🧭 Commande principale : /ticket rename
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="rename", description="✏️ Renommer ce ticket")
@app_commands.describe(nom="Nouveau nom du ticket (100 caractères max)")
async def ticket_rename(interaction: discord.Interaction, nom: str) -> None:

    # 🛡️ Vérification ban utilisateur
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_rename"):
        return

    # 📦 Récupération des données.
    channel = interaction.channel
    ticket = await tm.get_ticket(channel.id)


    # 🔎 Véirification que le salon soit bien un ticket.
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Vous n'êtes pas dans un **ticket**."), ephemeral=True
        )
    
    # ⛔ Vérification des permissions.
    if not await is_staff(interaction, ticket, interaction.guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la **permission** de __renommer ce ticket__."),
            ephemeral=True,
        )

    # 📊 Tracking
    await tracker_commande(interaction, "ticket_rename")

    # 🧹 Nettoyage du nom du ticket.
    clean = strip_closed_prefix(nom.strip())[:100]
    if not clean:
        return await interaction.followup.send(
            view=error_container("Le **nom** fourni est __vide__."), ephemeral=True
        )

    target = closed_name(clean) if ticket.get("closed") else clean

    # 🔐 Tentative de renommage du salon.
    if await try_rename(channel, target):
        await tm.update_ticket(
            channel.id, original_name=clean, last_rename_at=int(time.time())
        )
        await interaction.followup.send(
            view=success_container(f"Le ticket a été **renommé** en `{target}`."),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            view=error_container(
                "Impossible de **renommer** le salon — __limite Discord__ atteinte.\n"
                "-# Réessayez dans quelques minutes."
            ),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_rename.error
async def ticket_rename_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)