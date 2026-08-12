"""
cogs/alpha/nota_force.py — Force l'envoi du message de présence des notations.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.perm_dev import check_dev

from utils.container_universel import success_container, error_container
from utils.error_handler import handle_app_command_error

from utils.managers.ng_nota_manager import (
    load_nota_config,
    get_all_nota_operators,
    get_available_operators,
)

from views.alpha.nota_view import build_presence_view

# Refonte multi-serveurs phase 9 : commande dédiée au dashboard Alpha.
SERVER = "alpha"

log = logging.getLogger(__name__)

# ============================================================
# 🔩 Paramètre
# ============================================================

RESTRICTED_USER_ID = 930821995787091988

async def _check_restricted(interaction: Interaction) -> bool:
    """Restreint la commande à RESTRICTED_USER_ID."""
    if interaction.user.id != RESTRICTED_USER_ID:
        await interaction.response.send_message(
            view=error_container("Vous n'avez pas la **permission** pour effectuer cette __commande__."),
            ephemeral=True,
        )
        return False
    return True


# ============================================================
# 🧪 Commande : /alpha nota_force
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="nota_force", description="🧪 [OP] Force l'envoi du message de présence")
async def nota_force(interaction: Interaction) -> None:

    # 🔐 Permissions
    if not await check_dev(interaction, "**forcer les notations**"):
        return

    # 🔒 Restriction supplémentaire (utilisateur unique)
    if not await _check_restricted(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande
    if not await verifier_commande(interaction, "alpha_nota_force"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "alpha_nota_force")

    cfg = await load_nota_config(SERVER)
    channel_id = cfg.get("channel_staff_id")

    # 🔎 Vérification qu'un salon est configuré.
    if not channel_id:
        return await interaction.followup.send(
            view=error_container("Aucun **salon staff** configuré."),
            ephemeral=True,
        )

    # 🔎 Vérification que le salon existe.
    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container(f"Salon **introuvable** (ID `{channel_id}` invalide ou bot sans accès)."),
                ephemeral=True,
            )

    operators = await get_all_nota_operators(SERVER)
    available_ids = await get_available_operators(SERVER)

    view = build_presence_view(
        operators=operators,
        available_ids=available_ids,
        deadline_passed=False,
    )

    # 💻 Envoi.
    try:
        msg = await channel.send(view=view)
    except discord.HTTPException:
        log.exception("[NOTA_FORCE] Erreur envoi | guild=%s", interaction.guild_id)
        return await interaction.followup.send(
            view=error_container("Une **erreur Discord** est survenue."),
            ephemeral=True,
        )

    await interaction.followup.send(
        view=success_container(f"Message envoyé dans {channel.mention} !\nMessage ID : `{msg.id}`"),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@nota_force.error
async def nota_force_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)