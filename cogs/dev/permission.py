"""
cogs/dev/permission.py — /dev permissions : dashboard RBAC (refonte
multi-serveurs, phase 4). Remplace l'ancien dashboard flat (PermissionRole
/ permission_entries, views/dev/permissions_view.py — retiré en phase 15,
nettoyage legacy, voir PHASE_15.md ; permission_entries elle-même n'est
que gelée pour l'instant, DROP TABLE préparé mais pas encore exécuté).

Accès réservé au grade RBAC "equipe_guideon.dev" + garde-fou is_creator
(utils.createur.CREATOR_IDS) — évite un verrouillage total de ce dashboard
si les IDs créateur n'ont pas (encore) de ligne dans permission_grade_members
suite au backfill de la phase 3. Même pattern que tous les autres
utils.perm_*.py du projet (is_creator OR <grade/role>).
"""
from __future__ import annotations

import logging

import discord
from discord import Interaction, app_commands

from utils.container_universel import error_container, send_ephemeral
from utils.control_admin import verifier_commande
from utils.createur import is_creator
from utils.error_handler import handle_app_command_error
from utils.managers.permission_rbac_manager import has_grade
from utils.track_commande import tracker_commande
from views.dev.permissions_rbac_view import build_category_list_view

log = logging.getLogger(__name__)

DEV_GRADE_SLUG = "equipe_guideon.dev"


async def _is_authorized(interaction: Interaction) -> bool:
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
    # NOTE correctif : l'ancienne version faisait `await is_creator(interaction)`.
    # utils.createur.is_creator est SYNCHRONE et prend un discord_id (int), pas
    # une Interaction — ce `await` levait systématiquement un TypeError, donc
    # /dev permissions était en pratique cassée pour tout le monde (y compris
    # les créateurs) avant ce correctif.
    if not await _is_authorized(interaction):
        await send_ephemeral(
            interaction, error_container(f"Permission insuffisante ({DEV_GRADE_SLUG}).")
        )
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
