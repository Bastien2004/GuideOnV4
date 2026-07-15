"""
cogs/alpha/event_regle.py — Affiche les règles des events m+
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.perm_alpha import check_modo_plus
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

from utils.managers.alpha_event_config_manager import load_event_config
from views.alpha.event_regle_view import build_event_regle_view

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /alpha event_regle
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="event_regle", description="⚔️ [M+] Envoie les règles des events Alpha")
async def event_regle(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction): return

    # 🔐 Vérification des permissions.
    if not await check_modo_plus(interaction, "envoyer les **règles** des __events__ M+"): return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_event_regle"): return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_event_regle")

    # 📁 Chargement de la configuration.
    cfg = await load_event_config(interaction.guild_id)
    channel_id = cfg.get("channel_id")

    # 🔎 Vérification qu'un salon est configuré.
    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Salon non configuré.\n"
                "Utilisez `/dev config_alpha` → **Système Events** pour le définir."
            ),
            ephemeral=True,
        )

    # 🔎 Vérification que le salon existe.
    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon introuvable."), ephemeral=True
            )

    # 💻 Création et envoie de la view.
    try:
        await channel.send(view=build_event_regle_view())
    except discord.HTTPException:
        log.exception("[EVENT_REGLE] Erreur | guild=%s", interaction.guild_id)
        return await interaction.followup.send(
            view=error_container("Une **erreur Discord** est survenue."), ephemeral=True
        )

    await interaction.followup.send(
        view=success_container(f"Le règlement des **events M+** a été envoyé dans {channel.mention} !"),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@event_regle.error
async def event_regle_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)