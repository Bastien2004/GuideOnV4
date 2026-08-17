"""
cogs/ngstaff/ngstaff_stafflist.py — /ngstaff stafflist : crée ou met à jour
la liste du staff, généralisée multi-serveurs (refonte multi-serveurs,
phase 12, §13 du prompt).

Réplique de cogs/alpha/stafflist.py (la commande, pas le helper
refresh_staff_message — déjà multi-serveurs depuis ce même phase via son
kwarg `server`, importé et réutilisé tel quel ici plutôt que dupliqué).
Différence : flow require_ng_server + has_grade_check dynamique au lieu de
check_op_alpha (RBAC legacy, propre à Alpha).

Note : contrairement à refresh_staff_message (silencieuse, appelée par
d'autres flows), cette commande répond à l'utilisateur — la logique
d'édition/création du message est donc reprise ici plutôt que déléguée,
pour conserver les messages de confirmation ephémères.
"""

from __future__ import annotations

import logging

import discord
from discord import Interaction, app_commands

from utils.container_universel import error_container, success_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.alpha_message_manager import clear_alpha_message, get_alpha_message, upsert_alpha_message
from utils.managers.ng_rank_config_manager import load_rank_config
from utils.managers.ng_staff_manager import list_staff
from utils.ng_server_check import require_ng_server
from utils.perm_check import has_grade_check
from utils.track_commande import tracker_commande
from views.alpha.stafflist_view import build_stafflist_view

log = logging.getLogger(__name__)

MESSAGE_KEY = "stafflist"


# ============================================================
# 🧭 Commande : /ngstaff stafflist
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="stafflist", description="📋 [OP] Crée ou met à jour la liste du staff")
async def ngstaff_stafflist(interaction: Interaction) -> None:

    # 🌐 Vérification "Discord NG" (résout le serveur, sinon message + return).
    server = await require_ng_server(interaction)
    if server is None:
        return

    # 🔐 Vérification RBAC dynamique, propre au serveur détecté.
    if not await has_grade_check(interaction, f"staff_{server.name}.op"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ngstaff_stafflist"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ngstaff_stafflist")

    # 📋 Récupération de la configuration.
    rank_cfg = await load_rank_config(server.name)
    channel_id = rank_cfg.get("content_stafflist_channel_id")
    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Le salon n'est pas configuré.\n"
                "Utilisez `/ngstaff config` → **Système Rank / Derank** pour le définir."
            ),
            ephemeral=True,
        )

    # 💻 Récupération du salon
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
    members = await list_staff(server.name)
    view = build_stafflist_view(members)

    # 🔍 Récupération message existant
    msg_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    existing: discord.Message | None = None

    if msg_cfg and msg_cfg.message_id:
        try:
            existing = await channel.fetch_message(msg_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    # 🚀 Édition ou création
    try:
        if existing:
            await existing.edit(view=view)
            return await interaction.followup.send(
                view=success_container(f"Liste du staff **mise à jour** dans {channel.mention} !"),
                ephemeral=True,
            )

        sent = await channel.send(view=view)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)
        return await interaction.followup.send(
            view=success_container(f"Liste du staff **créée** dans {channel.mention} !"),
            ephemeral=True,
        )

    except discord.HTTPException:
        log.exception("[STAFFLIST NGSTAFF] Erreur /ngstaff stafflist | guild=%s server=%s", guild_id, server.name)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@ngstaff_stafflist.error
async def ngstaff_stafflist_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)