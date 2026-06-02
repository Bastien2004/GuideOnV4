"""
cogs/dev/config_alpha.py — Commande /dev config_alpha.

Ouvre le hub de configuration Alpha : liste de tous les systèmes
configurables (Rank/Derank, Notations, ONU, futurs systèmes).
Accessible : créateurs uniquement.
"""
from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.createur import is_creator
from views.alpha.config_dashboard_view import ConfigDashboardView


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(
    name="config_alpha",
    description="⚙️ Hub de configuration des systèmes Alpha",
)
async def config_alpha(interaction: Interaction) -> None:

    # 🔐 Créateurs uniquement
    if not is_creator(interaction.user.id):
        return await interaction.response.send_message(
            view=error_container("Cette commande est réservée aux **créateurs**."),
            ephemeral=True,
        )

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation + tracking
    if not await verifier_commande(interaction, "dev_config_alpha"):
        return
    await tracker_commande(interaction, "dev_config_alpha")

    # 🚀 Dashboard
    view = ConfigDashboardView(
        guild_id=interaction.guild_id,
        owner_id=interaction.user.id,
    )
    await interaction.followup.send(view=view, ephemeral=True)


@config_alpha.error
async def config_alpha_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    await handle_app_command_error(interaction, error)