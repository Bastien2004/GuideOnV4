"""
Commande /ticket rename — Permet renommer un ticket existant.
"""

"""
cogs/ticket/ticket_rename.py — /ticket rename

Renomme le ticket courant (staff uniquement). Respecte la limite Discord
de renommage (2 edits / 10 min) gérée par le cooldown stocké sur le ticket.
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
from views.ticket._helpers import (
    closed_name,
    is_staff,
    strip_closed_prefix,
    try_rename,
)

log = logging.getLogger(__name__)


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="rename", description="✏️ Renommer ce ticket")
@app_commands.describe(nom="Nouveau nom du ticket (100 caractères max)")
async def ticket_rename(interaction: discord.Interaction, nom: str) -> None:
    if not await verifier_ban_utilisateur(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    if not await verifier_commande(interaction, "ticket_rename"):
        return

    channel = interaction.channel
    ticket = await tm.get_ticket(channel.id)
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Ce salon n'est pas un ticket."), ephemeral=True
        )
    if not await is_staff(interaction, ticket, interaction.guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la permission de renommer ce ticket."),
            ephemeral=True,
        )

    await tracker_commande(interaction, "ticket_rename")

    clean = strip_closed_prefix(nom.strip())[:100]
    if not clean:
        return await interaction.followup.send(
            view=error_container("Le nom fourni est vide."), ephemeral=True
        )

    # Si le ticket est fermé, on conserve le préfixe closed- visuellement.
    target = closed_name(clean) if ticket.get("closed") else clean

    if await try_rename(channel, target):
        await tm.update_ticket(
            channel.id, original_name=clean, last_rename_at=int(time.time())
        )
        await interaction.followup.send(
            view=success_container(f"Le ticket a été renommé en `{target}`."),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            view=error_container(
                "Impossible de renommer le salon — limite Discord atteinte.\n"
                "-# Réessayez dans quelques minutes."
            ),
            ephemeral=True,
        )


@ticket_rename.error
async def ticket_rename_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)