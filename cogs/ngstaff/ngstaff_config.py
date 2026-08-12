"""
cogs/ngstaff/ngstaff_config.py — /ngstaff config : dashboard générique
multi-serveurs NG (refonte multi-serveurs, phase 11, §13 du prompt).

Structure similaire à /alpha config_alpha, mais le serveur n'est pas câblé
en dur : il est résolu dynamiquement à partir de l'interaction (flow deux
temps décrit dans utils.perm_check, §5 option a du prompt) :

    1. utils.ng_server_check.require_ng_server — vérifie que l'interaction
       vient bien d'un Discord NG enregistré dans ng_servers.
    2. utils.perm_check.has_grade_check(interaction, f"staff_{server.name}.op")
       — vérifie le grade RBAC dynamique, propre au serveur détecté.
"""
from __future__ import annotations

import discord
from discord import Interaction, app_commands

from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.ng_server_check import require_ng_server
from utils.perm_check import has_grade_check
from utils.track_commande import tracker_commande
from views.ngstaff.config_dashboard_view import NGStaffConfigDashboardView


# ============================================================
# 🧭 Commande : /ngstaff config
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(name="config", description="⚙️ [OP] Dashboard configuration systèmes NG")
async def ngstaff_config(interaction: Interaction) -> None:

    # 🌐 Vérification "Discord NG" (résout le serveur, sinon message + return).
    server = await require_ng_server(interaction)
    if server is None:
        return

    # 🔐 Vérification RBAC dynamique, propre au serveur détecté.
    if not await has_grade_check(interaction, f"staff_{server.name}.op"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ngstaff_config"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ngstaff_config")

    # 🚀 Envoi du dashboard.
    view = NGStaffConfigDashboardView(
        guild_id=interaction.guild_id, server=server.name, owner_id=interaction.user.id
    )
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@ngstaff_config.error
async def ngstaff_config_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
