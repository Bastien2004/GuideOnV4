"""
cogs/ngstaff/ngstaff_nota_debug.py — /ngstaff nota_debug : affiche l'état du
système de notations pour le serveur NG détecté, généralisé multi-serveurs
(refonte multi-serveurs, phase 12, §13 du prompt).

Réplique de cogs/alpha/nota_debug.py — mêmes gardes (dev + utilisateur
restreint), server résolu via require_ng_server au lieu du "alpha" câblé en
dur. ng_nota_manager est déjà multi-serveurs depuis la phase 9 : aucun
changement requis côté manager.
"""

from __future__ import annotations

import discord
from discord import Interaction, app_commands

from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.ng_nota_manager import (
    is_past_deadline,
    is_time_now,
    load_nota_config,
    load_nota_state,
    now_paris,
)
from utils.ng_server_check import require_ng_server
from utils.perm_dev import check_dev
from utils.track_commande import tracker_commande
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
# 🔍 Commande : /ngstaff nota_debug
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="nota_debug", description="🔍 [DEV] Affiche l'état du système de notations (debug)")
async def ngstaff_nota_debug(interaction: Interaction) -> None:

    # 🌐 Vérification "Discord NG" (résout le serveur, sinon message + return).
    server = await require_ng_server(interaction)
    if server is None:
        return

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**consulter** l'état du système de notations."):
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
    if not await verifier_commande(interaction, "ngstaff_nota_debug"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ngstaff_nota_debug")

    # 📚 Récupération des données.
    cfg = await load_nota_config(server.name)
    state = await load_nota_state(server.name)

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

@ngstaff_nota_debug.error
async def ngstaff_nota_debug_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
