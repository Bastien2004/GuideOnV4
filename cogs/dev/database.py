"""
cogs/dev/database.py — /dev database : explorateur générique et en LECTURE
SEULE de toutes les tables de la base (menu de sélection + indices +
aperçu/recherche), pour diagnostiquer sans avoir besoin d'un accès direct
à la BDD (celle-ci n'étant accessible qu'au propriétaire du VPS d'hébergement).
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.error_handler import handle_app_command_error
from utils.perm_check import has_grade_check

from views.dev.db_explorer_view import DBTableListView


# ============================================================
# 🧭 Commande : /dev database
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="database", description="🗄️ [DEV] Explore les tables de la base de données (lecture seule)")
async def database(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "consulter la **base de données**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_database"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_database")

    # 🚀 Envoi de l'explorateur (liste des tables, page 0).
    view = DBTableListView(owner_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@database.error
async def database_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)