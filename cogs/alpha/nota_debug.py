"""
cogs/alpha/nota_debug.py — Affiche les informations du système de notations Alpha (debug).
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

from utils.managers.alpha_nota_manager import (
    load_nota_config,
    load_nota_state,
    now_paris,
    is_time_now,
    is_past_deadline,
)


from views.alpha.nota_debug_view import build_nota_debug_view


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
# 🔍 Commande : /alpha nota_debug
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="nota_debug", description="🔍 [OP] Affiche l'état du système de notations Alpha (debug)")
async def nota_debug(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**consulter** l'état du système de notations Alpha."):
        return

    # 🔒 Restriction Ruixi62.
    if not await _check_restricted(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "alpha_nota_debug"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_nota_debug")

    # 📚 Récupération des données.
    cfg = await load_nota_config(interaction.guild_id)
    state = await load_nota_state(interaction.guild_id)

    now = now_paris()

    presence_trigger = is_time_now(
        cfg.get("send_presence_weekday"),
        cfg.get("send_presence_hour"),
        cfg.get("send_presence_minute"),
    )

    deadline_trigger = is_past_deadline(
        cfg.get("deadline_weekday"),
        cfg.get("deadline_hour"),
        cfg.get("deadline_minute"),
    )

    public_trigger = is_time_now(
        cfg.get("send_public_weekday"),
        cfg.get("send_public_hour"),
        cfg.get("send_public_minute"),
    )

    # 🧩 Envoi de l'interface de debug.
    await interaction.followup.send(
        view=build_nota_debug_view(now, cfg, state, presence_trigger, deadline_trigger, public_trigger),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@nota_debug.error
async def nota_debug_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)