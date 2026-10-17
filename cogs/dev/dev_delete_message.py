"""
cogs/dev/delete_message.py — Supprime un message de GuideOn donné.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container, warning_container
from utils.error_handler import handle_app_command_error
from utils.perm_check import has_grade_check

from utils.dev_delete_message import DeleteMessageError, delete_bot_message

# ============================================================
# 🧭 Commande : /dev delete_message
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="delete_message", description="🗑️ [DEV] Supprime un message envoyé par GuideOn")
@app_commands.describe(id_salon="ID du salon contenant le message", id_message="ID du message à supprimer")
async def delete_message(interaction: Interaction, id_salon: str, id_message: str) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "**supprimer** un message du bot"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "dev_delete_message"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_delete_message")

    # 🔎 Vérification des IDs.
    try:
        channel_id = int(id_salon)
        message_id = int(id_message)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_salon` et `id_message` doivent être des **identifiants numériques**."),
            ephemeral=True,
        )

    # 🚀 Gestion de la suppression.
    try:
        info = await delete_bot_message(interaction.client, channel_id, message_id, interaction.user.id)
    except DeleteMessageError as e:
        view = warning_container(e.message) if e.warning else error_container(e.message)
        return await interaction.followup.send(view=view, ephemeral=True)

    # ✉️ Envoi de la confirmation de suppression.
    await interaction.followup.send(
        view=success_container(
            f"Message supprimé correctement.\n\n"
            f"**Serveur :** {info.guild_name}\n"
            f"**Salon :** #{info.channel_name} (`{info.channel_id}`)\n"
            f"**Aperçu :** {info.content_preview}"
        ),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@delete_message.error
async def delete_message_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)