"""
cogs/ngstaff/ngstaff_edit_stafflist.py — /ngstaff edit_stafflist : dashboard
CRUD de la liste staff, généralisé multi-serveurs (refonte multi-serveurs,
phase 12, §13 du prompt).

Réplique de cogs/alpha/edit_stafflist.py. Contrairement à ngstaff_rank /
ngstaff_derank / ngstaff_stafflist, la permission reste réservée aux
développeurs (is_creator), à l'identique de son équivalent Alpha — cet
éditeur contourne entièrement le flow rank/derank (pas d'annonces, pas de
rôles Discord touchés), volontairement gardé plus restrictif qu'un simple
grade "op". require_ng_server sert uniquement à résoudre `server`.
"""

from __future__ import annotations

import discord
from discord import Interaction, app_commands

from utils.control_admin import verifier_commande

from utils.perm_check import has_grade_check
from utils.error_handler import handle_app_command_error
from utils.managers.ng_staff_manager import list_staff
from utils.ng_server_check import require_ng_server
from utils.track_commande import tracker_commande
from views.alpha.edit_list_view import EditListView


# ============================================================
# 🧭 Commande : /ngstaff edit_stafflist
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(name="edit_stafflist", description="📋 [OP] Gestion de la liste staff")
async def ngstaff_edit_stafflist(interaction: Interaction) -> None:

    # 🌐 Vérification "Discord NG".
    server = await require_ng_server(interaction)
    if server is None:
        return

    # 🔐 Vérification RBAC dynamique, propre au serveur détecté.
    if not await has_grade_check(interaction, (f"staff_{server.name}.op" or f"staff_{server.name}.operateur")):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "ngstaff_edit_stafflist"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ngstaff_edit_stafflist")

    # 📋 Chargement de la liste actuelle du staff.
    members = await list_staff(server.name)
    view = EditListView(
        guild_id=interaction.guild_id,
        owner_id=interaction.user.id,
        members=members,
        server=server.name,
    )

    # ✉️ Envoi de l'interface d'édition.
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@ngstaff_edit_stafflist.error
async def ngstaff_edit_stafflist_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
