"""
cogs/dev/delete_message.py — /dev delete_message

Supprime un message envoyé PAR GUIDEON (et uniquement par lui), dans n'importe
quel salon où le bot a accès (cross-guild).

⚠️ Discord ne permet pas de récupérer un message par son ID seul : il faut
obligatoirement le salon (channel_id) + le message_id. La commande prend
donc les deux IDs.

Accessible : DEV uniquement.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container, success_container, warning_container
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

log = logging.getLogger(__name__)


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(
    name="delete_message",
    description="🗑️ [DEV] Supprime un message envoyé par GuideOn",
)
@app_commands.describe(
    id_salon="ID du salon contenant le message",
    id_message="ID du message à supprimer",
)
async def delete_message(interaction: Interaction, id_salon: str, id_message: str) -> None:

    if not await check_dev(interaction, "supprimer un message du bot"):
        return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "dev_delete_message"):
        return
    await tracker_commande(interaction, "dev_delete_message")

    # 🔢 Parsing des IDs
    try:
        channel_id = int(id_salon)
        message_id = int(id_message)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_salon` et `id_message` doivent être des **identifiants numériques**."),
            ephemeral=True,
        )

    # 💻 Récupération du salon
    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except discord.NotFound:
            return await interaction.followup.send(
                view=error_container("Salon introuvable (ID invalide ou bot non présent sur ce serveur)."),
                ephemeral=True,
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                view=error_container("Le bot n'a pas accès à ce salon."),
                ephemeral=True,
            )
        except discord.HTTPException:
            log.exception("[DELETE_MESSAGE] Erreur fetch_channel %d", channel_id)
            return await interaction.followup.send(
                view=error_container("Une erreur Discord est survenue lors de la récupération du salon."),
                ephemeral=True,
            )

    if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.StageChannel)):
        return await interaction.followup.send(
            view=error_container("Ce type de salon n'est pas supporté."),
            ephemeral=True,
        )

    # 📨 Récupération du message
    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        return await interaction.followup.send(
            view=error_container("Message introuvable dans ce salon."),
            ephemeral=True,
        )
    except discord.Forbidden:
        return await interaction.followup.send(
            view=error_container("Le bot n'a pas la permission de lire ce salon."),
            ephemeral=True,
        )
    except discord.HTTPException:
        log.exception("[DELETE_MESSAGE] Erreur fetch_message %d/%d", channel_id, message_id)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue lors de la récupération du message."),
            ephemeral=True,
        )

    # 🛡️ Vérification : message du bot uniquement
    if message.author.id != interaction.client.user.id:
        return await interaction.followup.send(
            view=warning_container(
                "Ce message n'a **pas été envoyé par GuideOn** — suppression refusée.\n"
                f"Auteur : <@{message.author.id}> (`{message.author.id}`)"
            ),
            ephemeral=True,
        )

    # 📍 Infos pour le message de confirmation (avant suppression)
    guild_name = getattr(channel.guild, "name", "DM") if hasattr(channel, "guild") else "DM"
    channel_name = getattr(channel, "name", str(channel_id))
    content_preview = (message.content or "*[contenu vide / embed / composants]*")[:200]

    # 🗑️ Suppression
    try:
        await message.delete()
    except discord.NotFound:
        return await interaction.followup.send(
            view=warning_container("Le message était déjà supprimé."),
            ephemeral=True,
        )
    except discord.Forbidden:
        return await interaction.followup.send(
            view=error_container("Le bot n'a pas la permission de supprimer ce message."),
            ephemeral=True,
        )
    except discord.HTTPException:
        log.exception("[DELETE_MESSAGE] Erreur suppression %d/%d", channel_id, message_id)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue lors de la suppression."),
            ephemeral=True,
        )

    log.info(
        "[DELETE_MESSAGE] Message %d supprimé par %s | salon=%d (%s) guild=%s",
        message_id, interaction.user.id, channel_id, channel_name, guild_name,
    )

    await interaction.followup.send(
        view=success_container(
            f"Message supprimé avec succès.\n\n"
            f"**Serveur :** {guild_name}\n"
            f"**Salon :** #{channel_name} (`{channel_id}`)\n"
            f"**Aperçu :** {content_preview}"
        ),
        ephemeral=True,
    )


@delete_message.error
async def delete_message_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)