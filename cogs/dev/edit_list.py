"""
cogs/dev/edit_list.py — Commande /dev edit_list.

Ouvre le dashboard CRUD de la liste staff Alpha.
Permet d'ajouter / modifier / supprimer des entrées sans les messages
décoratifs du processus rank/derank.
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
from utils.managers.alpha_staff_manager import list_staff
from views.alpha.edit_list_view import EditListView


# ════════════════════════════════════════════════════════════
# 🧭 Commande
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(
    name="edit_list",
    description="📋 Dashboard CRUD de la liste staff Alpha (sans effets rank/derank)",
)
async def edit_list(interaction: Interaction) -> None:

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
    if not await verifier_commande(interaction, "dev_edit_list"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "dev_edit_list")

    # 📋 Chargement de la liste courante
    members = await list_staff()
    view = EditListView(
        guild_id=interaction.guild_id,
        owner_id=interaction.user.id,
        members=members,
    )

    await interaction.followup.send(view=view, ephemeral=True)


# ── Erreurs ────────────────────────────────────────────────

@edit_list.error
async def edit_list_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    await handle_app_command_error(interaction, error)