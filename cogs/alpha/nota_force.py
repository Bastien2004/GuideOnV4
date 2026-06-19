"""
cogs/dev/nota_force.py — Force l'envoi du message de présence des notations
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.perm_dev import check_dev

from utils.container_universel import success_container, error_container
from utils.error_handler import handle_app_command_error

from utils.managers.alpha_nota_manager import (
    load_nota_config,
    load_nota_state,
)

from views.alpha.nota_view import build_presence_view
from utils.managers.alpha_nota_manager import (
    get_all_nota_operators,
    get_available_operators,
)


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(
    name="nota_force",
    description="🧪 [OP] Force l'envoi du message de présence"
)
async def nota_force(interaction: Interaction) -> None:

    if not await check_dev(interaction, "**forcer les notations**"):
        return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "dev_nota_force"):
        return

    await tracker_commande(interaction, "dev_nota_force")

    cfg = await load_nota_config(interaction.guild_id)
    state = await load_nota_state(interaction.guild_id)

    channel_id = cfg.get("channel_staff_id")

    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Aucun salon staff configuré."
            ),
            ephemeral=True
        )

    channel = interaction.client.get_channel(channel_id)

    if channel is None:
        return await interaction.followup.send(
            view=error_container(
                f"Salon introuvable : `{channel_id}`"
            ),
            ephemeral=True
        )

    operators = await get_all_nota_operators(interaction.guild_id)
    available_ids = await get_available_operators(interaction.guild_id)

    view = build_presence_view(
        operators=operators,
        available_ids=available_ids,
        deadline_passed=False,
    )

    try:
        msg = await channel.send(view=view)

    except Exception as e:
        return await interaction.followup.send(
            view=error_container(
                f"Erreur d'envoi : `{e}`"
            ),
            ephemeral=True
        )

    await interaction.followup.send(
        view=success_container(
            f"Message envoyé.\n"
            f"Message ID : `{msg.id}`"
        ),
        ephemeral=True
    )


@nota_force.error
async def nota_force_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)