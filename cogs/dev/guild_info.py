"""
cogs/dev/guild_info.py — Affiche les informations d'un serveur Discord.

2026-10-06 (Paul, refonte) : le panel est désormais interactif
(BaseLayoutView, page Aperçu + page Systèmes) — build_guild_info_view
construit directement l'aperçu (et appelle gather_guild_info lui-même),
donc on ne l'appelle plus séparément ici.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_check import has_grade_check

from views.dev.guild_info_view import build_guild_info_view


# ============================================================
# 🧭 Commande : /dev guild_info
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="guild_info", description="🏠 [DEV] Affiche les informations d'un serveur")
@app_commands.describe(id_serveur="ID du serveur cible")
async def guild_info(interaction: Interaction, id_serveur: str) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "consulter les **informations** d'un serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_guild_info"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_guild_info")

    # 🔎 Vérification de l'ID.
    try:
        guild_id = int(id_serveur)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_serveur` doit être un **identifiant numérique**."),
            ephemeral=True,
        )

    guild = interaction.client.get_guild(guild_id)
    if guild is None:
        return await interaction.followup.send(
            view=error_container("GuideOn n'est présent sur **aucun serveur** avec cet ID."),
            ephemeral=True,
        )

    # 🚀 Construction et envoi du panel (récupère les infos à l'intérieur).
    view = await build_guild_info_view(guild, owner_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@guild_info.error
async def guild_info_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
