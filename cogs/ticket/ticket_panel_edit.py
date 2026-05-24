"""
Commande /ticket panel_edit — Permet de modifier un panel de ticket existant.
"""

from __future__ import annotations

import logging
import re

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.perm_admin import check_admin
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from utils.managers import ticket_manager as tm
from views.ticket.panel_setup_view import build_setup_view

log = logging.getLogger(__name__)

_MESSAGE_ID_RE = re.compile(r"/(\d+)$")


# ============================================================
# 🧭 Commande principale : /ticket panel_edit
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="panel_edit", description="✏️ Modifier un panel de tickets existant")
@app_commands.describe(lien_panel="Lien du message panel (clic droit → Copier le lien)")
async def ticket_panel_edit(interaction: discord.Interaction, lien_panel: str) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Vérification administrateur.
    if not await check_admin(interaction, "**modifier** un __panel de tickets__"):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_panel_edit"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_panel_edit")


    # 📦 Récupération des données.
    guild_id = interaction.guild_id

    # 🔍 Extraction de l'ID du message depuis le lien.
    match = _MESSAGE_ID_RE.search(lien_panel.strip())
    if not match:
        return await interaction.followup.send(
            view=error_container(
                "__Lien__ de message **invalide**. Copiez le lien **direct** du panel "
                "(clic droit sur le message → Copier le lien)."
            ),
            ephemeral=True,
        )
    message_id = int(match.group(1))

    # 📁 Récupérer le panel par son message.
    panel = await tm.get_panel_by_message(guild_id, message_id)
    if not panel:
        return await interaction.followup.send(
            view=error_container("**Aucun panel** ne __correspond__ à ce message."),
            ephemeral=True,
        )

    # 🏗️ Pré-remplissage de la configuration.
    ctx = {
        "panel_id": panel["panel_id"],
        "channel_id": panel["channel_id"],
        "message_id": panel["message_id"],
        "title": panel["title"],
        "panel_message": panel["panel_message"],
        "ticket_category_id": panel["ticket_category_id"],
        "transcript_channel_id": panel["transcript_channel_id"],
        "closed_category_id": panel.get("closed_category_id"),
        "ping_role_id": panel.get("ping_role_id"),
        "role_ban_ticket_id": panel.get("role_ban_ticket_id"),
        "staff_roles": list(panel.get("staff_roles", [])),
        "counter": panel.get("counter", 1),
    }

    # 🏗️ Construction et envoie de la view.
    try:
        view = build_setup_view(interaction.guild, ctx)
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("**Ouverture** interface `panel_edit` échouée (guild=%s)", guild_id)
        await interaction.followup.send(
            view=error_container("**Impossible** d'ouvrir l'__interface d'édition__."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_panel_edit.error
async def ticket_panel_edit_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)