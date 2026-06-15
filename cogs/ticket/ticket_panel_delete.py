"""
Commande /ticket panel_delete — Permet de supprimer un panel de ticket existant.
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
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

from utils.managers import ticket_manager as tm
from views._components.confirm_view import ConfirmView

log = logging.getLogger(__name__)

_MESSAGE_ID_RE = re.compile(r"/(\d+)$")


# ============================================================
# 🧭 Commande principale : /ticket panel_delete
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="panel_delete", description="🗑️ Supprimer un panel de tickets")
@app_commands.describe(lien_panel="Lien du message panel (clic droit → Copier le lien)")
async def ticket_panel_delete(interaction: discord.Interaction, lien_panel: str) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Vérification administrateur.
    if not await check_admin(interaction, "**supprimer** un __panel de tickets__"):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_panel_delete"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_panel_delete")

    # 📦 Récupération des données.
    guild_id = interaction.guild_id

    # 🔍 Extraction de l'ID du message depuis le lien.
    match = _MESSAGE_ID_RE.search(lien_panel.strip())
    if not match:
        return await interaction.followup.send(
            view=error_container("__Lien de message__ **invalide**. Copiez le lien **direct** du panel."),
            ephemeral=True,
        )
    message_id = int(match.group(1))

    # 🔎 Vérification que le message corresponde à un panel existant.
    panel = await tm.get_panel_by_message(guild_id, message_id)
    if not panel:
        return await interaction.followup.send(
            view=error_container("**Aucun panel** ne __correspond__ à ce message."),
            ephemeral=True,
        )

    # ⚠️ Confirmation
    confirm = ConfirmView(
        owner_id=interaction.user.id,
        question=(
            f"Supprimer le panel **{panel['title']}** ?\n"
            "-# Le panel sera supprimé de notre base de données de façon définitive."
        ),
        confirm_label="Supprimer",
    )
    await interaction.followup.send(view=confirm, ephemeral=True)
    await confirm.wait()

    if not confirm.confirmed:
        return

    # 🗑️ Suppression du message Discord
    channel = interaction.guild.get_channel(panel.get("channel_id", 0))
    if channel:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.delete()
        except (discord.NotFound, discord.HTTPException, discord.Forbidden):
            pass

    # 📂 Suppression DB
    await tm.delete_panel(guild_id, panel["panel_id"])

    await interaction.followup.send(
        view=success_container(f"Le panel **{panel['title']}** a été supprimé."),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_panel_delete.error
async def ticket_panel_delete_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)