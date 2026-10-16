"""
cogs/alpha/index.py — Gère l'interface d'information "Index" du serveur Alpha.
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
from utils.ng_check_discord import require_alpha_guild
from utils.perm_check import has_grade_check

from utils.managers.ng_rank_config_manager import load_rank_config
from utils.managers.alpha_message_manager import get_alpha_message, upsert_alpha_message, clear_alpha_message

from views.alpha.index_view import build_index_view, get_fresh_files

SERVER = "alpha"

log = logging.getLogger(__name__)

MESSAGE_KEY = "index"


# ============================================================
# 📖 Commande : /alpha index
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 20)
@app_commands.command(name="index", description="📋 [OP] Envoie ou met à jour l'interface d'information (index) du serveur Alpha")
async def index(interaction: Interaction) -> None:

    # 🌐 Vérification "Discord Alpha".
    if not await require_alpha_guild(interaction):
        return

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "staff_alpha.op", "gèrer l'**index**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_index"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_index")

    # 🧩 Récupération de la configuration.
    cfg = await load_rank_config(SERVER)
    channel_id = cfg.get("content_index_channel_id")
    emoji_str = cfg.get("content_index_emoji")
    guild_id = interaction.guild_id

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
    view = build_index_view(fresh_files)

    # 🔎 Vérification existence du message.
    existing_msg: discord.Message | None = None
    db_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    if db_cfg and db_cfg.message_id:
        try:
            existing_msg = await channel.fetch_message(db_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing_msg = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    try:
        if existing_msg:
            await existing_msg.edit(view=view, attachments=fresh_files)
            return await interaction.followup.send(
                view=success_container(f"Index mis à jour dans {channel.mention} !"),
                ephemeral=True,
            )

        kwargs: dict = {"view": view}
        if fresh_files:
            kwargs["files"] = fresh_files
        sent = await channel.send(**kwargs)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)

        # 🤪 Ajout de l'emoji.
        if emoji_str:
            try:
                await sent.add_reaction(emoji_str)
            except discord.HTTPException:
                log.warning("[INDEX ALPHA] Impossible d'ajouter la réaction | guild=%s", guild_id)

        return await interaction.followup.send(
            view=success_container(f"**Index** créé dans {channel.mention} !"),
            ephemeral=True,
        )

    except discord.HTTPException:
        log.exception("[INDEX ALPHA] Erreur /alpha index | guild=%s", guild_id)
        return await interaction.followup.send(
            view=error_container("Une **erreur** Discord est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@index.error
async def index_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
