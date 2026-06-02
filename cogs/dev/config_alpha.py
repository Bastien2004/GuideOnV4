"""
cogs/dev/config_alpha.py — Commande /dev config_alpha.

Ouvre le dashboard de configuration du système rank/derank Alpha.
Accessible : créateurs (is_creator) uniquement.
"""
from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.createur import is_creator
from utils.managers.alpha_rank_config_manager import load_rank_config
from views.alpha.config_alpha_view import ConfigAlphaView


# ════════════════════════════════════════════════════════════
# 🧭 Commande
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(
    name="config_alpha",
    description="⚙️ Dashboard de configuration du système rank Alpha",
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

    # ⚙️ Activation commande
    if not await verifier_commande(interaction, "dev_config_alpha"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "dev_config_alpha")

    # 📋 Chargement config
    cfg = await load_rank_config(interaction.guild_id)
    view = ConfigAlphaView(
        guild_id=interaction.guild_id,
        cfg=cfg,
        owner_id=interaction.user.id,
    )

    await interaction.followup.send(view=view, ephemeral=True)


# ── Erreurs ────────────────────────────────────────────────

@config_alpha.error
async def config_alpha_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    await handle_app_command_error(interaction, error)