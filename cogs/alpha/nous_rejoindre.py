"""
cogs/alpha/nous_rejoindre.py — Gestion de l'interface nous_rejoindre.
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
from utils.perm_alpha import check_op_alpha

from utils.managers.alpha_rank_config_manager import load_rank_config
from utils.managers.alpha_message_manager import get_alpha_message, upsert_alpha_message, clear_alpha_message

from views.alpha.nous_rejoindre_view import build_nous_rejoindre_view, get_fresh_files

log = logging.getLogger(__name__)

MESSAGE_KEY = "nous_rejoindre"


# ============================================================
# 🚪 Commande : /alpha nous_rejoindre
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 20)
@app_commands.command(name="nous_rejoindre", description="🚪 [OP] Envoi ou met à jour le tutoriel pour rejoindre le serveur Alpha")
async def nous_rejoindre(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Opérateur.
    if not await check_op_alpha(interaction, "envoyer le tutoriel"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_nous_rejoindre"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_nous_rejoindre")

    # 🧩 Récupération de la configuration.
    cfg = await load_rank_config(interaction.guild_id)
    channel_id = cfg.get("content_nous_rejoindre_channel_id")
    ping_id = cfg.get("content_nous_rejoindre_ping_id")
    emoji_str = cfg.get("content_nous_rejoindre_emoji")

    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Le salon n'est pas **configuré**.\n"
                "Utilisez `/dev config_alpha` pour le définir."
            ),
            ephemeral=True,
        )

    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon **introuvable** (ID invalide ou bot sans accès)."),
                ephemeral=True,
            )

    fresh_files = get_fresh_files()
    view = build_nous_rejoindre_view(fresh_files, ping_id)
    kwargs: dict = {"view": view}
    if fresh_files:
        kwargs["files"] = fresh_files

    guild_id = interaction.guild_id

    # 🔍 Vérification si le message existe.
    msg_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    existing: discord.Message | None = None
    if msg_cfg and msg_cfg.message_id:
        try:
            existing = await channel.fetch_message(msg_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    try:
        if existing:
            await existing.edit(view=view, attachments=fresh_files)
            return await interaction.followup.send(
                view=success_container(f"**Tutoriel** mis à jour dans {channel.mention} !"),
                ephemeral=True,
            )

        sent = await channel.send(**kwargs)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)

        if emoji_str:
            try:
                await sent.add_reaction(emoji_str)
            except discord.HTTPException:
                log.warning("[NOUS REJOINDRE ALPHA] Impossible d'ajouter la réaction | guild=%s", guild_id)

        return await interaction.followup.send(
            view=success_container(f"Le **Tutoriel** a été envoyé dans {channel.mention} !"),
            ephemeral=True,
        )

    except discord.HTTPException:
        log.exception("[NOUS REJOINDRE ALPHA] Erreur | guild=%s", guild_id)
        return await interaction.followup.send(
            view=error_container("Une **erreur** Discord est survenue lors de l'envoi."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@nous_rejoindre.error
async def nous_rejoindre_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)