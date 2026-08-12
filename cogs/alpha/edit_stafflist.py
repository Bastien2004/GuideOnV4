"""
cogs/alpha/edit_stafflist.py — Gestion de la liste du staff Alpha.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.createur import is_creator

from utils.managers.ng_staff_manager import list_staff
from views.alpha.edit_list_view import EditListView

# Refonte multi-serveurs (§7 du prompt) : câblé en dur sur "alpha" en
# permanence. **Dépréciée** depuis la phase 13 au profit de
# /ngstaff edit_stafflist (phase 12, voir PHASE_12.md) — le prompt note
# explicitement que /alpha edit_stafflist_alpha "disparaît". Ce fichier
# reste sur disque mais n'est plus enregistré dans bot.py (voir
# PHASE_13.md) — safety net, jamais supprimé.
SERVER = "alpha"


# ============================================================
# 🧭 Commande : /alpha edit_stafflist_alpha
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(name="edit_stafflist_alpha", description="📋 [ALPHA] Gestion de la liste staff Alpha")
async def alpha_edit_stafflist(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not is_creator(interaction.user.id):
        return await interaction.response.send_message(view=error_container("Cette commande est __réservée__ aux **développeurs**."), ephemeral=True)

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "alpha_edit_stafflist"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_edit_stafflist")

    # 📋 Chargement de la liste actuelle du staff.
    members = await list_staff(SERVER)
    view = EditListView(
        guild_id=interaction.guild_id,
        owner_id=interaction.user.id,
        members=members,
    )

    # ✉️ Envoi de l'interface d'édition.
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@alpha_edit_stafflist.error
async def alpha_edit_stafflist_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
