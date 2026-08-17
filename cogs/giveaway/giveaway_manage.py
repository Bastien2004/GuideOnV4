"""
cogs/giveaway/giveaway_manage.py — Gère un giveaway existant.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.boutique.gold_manager import is_gold

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.managers.giveaway_manager import get_giveaway
from views.giveaway.manage_view import GiveawayManageView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /giveaway manage
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="manage", description="🛠️ Gère un giveaway existant")
@app_commands.describe(giveaway_id="L'ID du giveaway à gérer")
async def giveaway_manage(interaction: discord.Interaction, giveaway_id: str) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # 🔐 Vérification des permissions (Admin ou Organisateur).
    is_admin = (
        isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.administrator
    )
    is_host = interaction.user.id == data["host_id"]
    if not (is_admin or is_host):
        await interaction.followup.send(
            view=error_container("Seul l'**organisateur** ou un **administrateur** peut gérer ce giveaway."),
            ephemeral=True,
        )
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "giveaway_manage"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "giveaway_manage")

    # 🔎 Récupération du giveaway.
    giveaway_id = giveaway_id.strip().upper()
    data = await get_giveaway(giveaway_id)
    if data is None:
        await interaction.followup.send(
            view=error_container(f"Aucun giveaway trouvé avec l'ID `{giveaway_id}`."),
            ephemeral=True,
        )
        return

    # 🛡️ Sécurité : appartient bien à ce serveur.
    if data["guild_id"] != interaction.guild.id:
        await interaction.followup.send(view=error_container("Il n'existe pas de giveaway avec cet ID sur ce serveur."), ephemeral=True)
        return

    # 🧩 Ouverture de la vue.
    try:
        view = await GiveawayManageView.create(
            giveaway_data=data,
            guild=interaction.guild,
            owner_id=interaction.user.id,
            is_gold_guild=is_gold(interaction.guild.id),
        )
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[GIVEAWAY MANAGE] Ouverture de l'interface de gestion échouée (guild=%s, gid=%s)", interaction.guild.id, giveaway_id)
        await interaction.followup.send(view=error_container("Impossible d'ouvrir l'interface de **gestion**."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@giveaway_manage.error
async def giveaway_manage_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)