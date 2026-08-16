"""
cogs/alpha/regle_interne.py — Gestion de l'interface des règles internes du Alpha.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.perm_alpha import require_alpha_guild
from utils.perm_check import has_grade_check

from utils.managers.ng_rank_config_manager import load_rank_config
from utils.managers.alpha_message_manager import get_alpha_message, upsert_alpha_message, clear_alpha_message

from views.alpha.regle_interne_view import build_regle_interne_view

log = logging.getLogger(__name__)

MESSAGE_KEY = "regle_interne"


# ============================================================
# 🧭 Commande : /alpha regle_interne
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 20)
@app_commands.command(name="regle_interne", description="⚖️ [OP] Envoie ou mise à jour des règles internes du Alpha")
async def regle_interne(interaction: Interaction) -> None:

    # 🌐 Vérification "Discord Alpha" (défense en profondeur, phase 13).
    if not await require_alpha_guild(interaction):
        return

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "staff_alpha.moderateur_plus"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_regle_interne"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_regle_interne")

    # 📋 Récupération des données.
    cfg = await load_rank_config("alpha")
    channel_id = cfg.get("content_regle_interne_channel_id")
    emoji_str = cfg.get("content_regle_interne_emoji")

    # 🔎 Vérification que le salon de règle interne est configuré.
    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Le salon n'est pas configuré.\n"
                "Utilisez `/dev config_alpha` → **Contenu Discord** pour le définir."
            ),
            ephemeral=True,
        )

    # ✉️ Envoi du message dans le salon dédié.
    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon **introuvable** (ID invalide ou bot sans accès)."),
                ephemeral=True,
            )

    guild_id = interaction.guild_id

    # 🔍 Message existant en DB ?
    msg_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    existing: discord.Message | None = None
    if msg_cfg and msg_cfg.message_id:
        try:
            existing = await channel.fetch_message(msg_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    built_view = build_regle_interne_view()

    try:
        if existing:
            await existing.edit(view=built_view)
            return await interaction.followup.send(
                view=success_container(f"Règles internes **mises à jour** dans {channel.mention} !"),
                ephemeral=True,
            )

        sent = await channel.send(view=built_view)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)

        if emoji_str:
            try:
                await sent.add_reaction(emoji_str)
            except discord.HTTPException:
                log.warning("[REGLE_INTERNE ALPHA] Impossible d'ajouter la réaction | guild=%s", guild_id)

        return await interaction.followup.send(
            view=success_container(f"Règles internes envoyées dans {channel.mention} !"),
            ephemeral=True,
        )

    except discord.HTTPException:
        log.exception("[REGLE_INTERNE ALPHA] Erreur | guild=%s", guild_id)
        return await interaction.followup.send(
            view=error_container("Une erreur **Discord** est survenue lors de l'envoi."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@regle_interne.error
async def regle_interne_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
