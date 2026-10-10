"""
cogs/eco/eco_balance.py — Commande /eco balance [membre].
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.eco_manager import get_balance
from utils.track_commande import tracker_commande

from views.eco.balance_view import build_balance_view

log = logging.getLogger(__name__)


# ============================================================
# 💰 Commande : /eco balance [membre]
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="balance", description="💰 Affiche le solde d'un membre")
@app_commands.describe(membre="Le membre dont tu veux voir le solde (toi par défaut)")
async def eco_balance(interaction: discord.Interaction, membre: Optional[discord.Member] = None) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer()
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "eco_balance"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "eco_balance")

    target = membre or interaction.user

    # 🚫 Refus des bots.
    if isinstance(target, discord.Member) and target.bot:
        await interaction.followup.send(view=error_container("Les **bots** n'ont pas de solde."))
        return

    # 🧩 Récup solde, puis affichage.
    try:
        balance = await get_balance(interaction.guild.id, target.id)
        view = build_balance_view(target, balance)
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("[ECO BALANCE] Affichage du solde échoué (guild=%s, target=%s)", interaction.guild.id, target.id)
        await interaction.followup.send(view=error_container("Impossible d'afficher le **solde** de ce membre."))


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@eco_balance.error
async def eco_balance_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
