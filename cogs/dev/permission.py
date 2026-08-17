"""
cogs/dev/permission.py — Gestion des permissions interne du bot
"""

from __future__ import annotations

import logging

import discord
from discord import Interaction, app_commands

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.createur import is_creator

from utils.container_universel import error_container, send_ephemeral
from utils.error_handler import handle_app_command_error
from utils.managers.permission_rbac_manager import has_grade

from views.dev.permissions_rbac_view import build_category_list_view

log = logging.getLogger(__name__)

DEV_GRADE_SLUG = "equipe_guideon.dev"


# ============================================================
# 🔩 Fonction utilitaire
# ============================================================

async def _is_authorized(interaction: Interaction) -> bool:
    """Vérification des permissions."""
    if is_creator(interaction.user.id):
        return True
    return await has_grade(interaction.user.id, DEV_GRADE_SLUG)


# ============================================================
# 🧭 Commande principale : /dev permissions
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="permissions", description="🔐 [DEV] Gérer les permissions internes du bot")
async def permissions(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await _is_authorized(interaction):
        await send_ephemeral(interaction, error_container(f"Vous n'avez pas la permission requise !\n ➥ `({DEV_GRADE_SLUG})`."))
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_permissions"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_permissions")

    # 🧩 Création interface.
    try:
        view = await build_category_list_view(interaction.client, interaction.user.id)
    except Exception:
        log.exception("[DEV PERMISSIONS] Erreur interface permissions")
        await interaction.followup.send(
            view=error_container("Impossible de charger l'**interface des permissions**."),
            ephemeral=True,
        )
        return

    # 📤 Envoi de l'interface.
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@permissions.error
async def permissions_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)