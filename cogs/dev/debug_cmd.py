"""
cogs/dev/debug_cmd.py — Outil de diagnostic pour une commande GuideOn.

⚠️ utils/command_debug.py à mettre à jour
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

from utils.command_debug import get_command_debug_info
from views.dev.debug_cmd_view import build_debug_cmd_view


# ============================================================
# 🧭 Commande : /dev debug_cmd
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="debug_cmd", description="🔍 [DEV] Diagnostic d'une commande (debug)")
@app_commands.describe(commande="Préfixe de la commande GuideOn")
async def debug_cmd(interaction: Interaction, commande: str) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**effectuer** le diagnostic de nos commandes"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_debug_cmd"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_debug_cmd")

    command_name = commande.strip()

    # 🔎 Diagnostic complet.
    info = await get_command_debug_info(command_name)

    if info is None:
        return await interaction.followup.send(
            view=error_container(
                f"Commande `{command_name}` **inconnue** (absente du système de maintenance, "
                f"des registres internes, et jamais utilisée)."
            ),
            ephemeral=True,
        )

    view = build_debug_cmd_view(info)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@debug_cmd.error
async def debug_cmd_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)