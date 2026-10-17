"""
cogs/dev/dev_command_visibility.py — Diagnostique de la visibilité d'une commande sur un serveur.
"""

from __future__ import annotations

import logging

import discord
from discord import Interaction, app_commands

from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.discord_command_permissions import scan_command_permissions
from utils.error_handler import handle_app_command_error
from utils.perm_check import has_grade_check
from utils.track_commande import tracker_commande
from views.dev.command_visibility_view import build_command_visibility_view

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /dev command_visibility
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="command_visibility", description="🔍 [DEV] Diagnostique la visibilité d'une commande sur un serveur (permissions Discord)")
@app_commands.describe(
    id_serveur="ID du serveur à analyser",
    id_utilisateur="ID du membre à analyser",
    commandes="Noms de commandes à filtrer, séparés par des virgules | vide = toutes",
    id_salon="ID du salon où la commande est testée (optionnel)")

async def command_visibility(interaction: Interaction, id_serveur: str, id_utilisateur: str | None = None,
    commandes: str | None = None, id_salon: str | None = None) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "diagnostiquer la **visibilité** d'une commande"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_command_visibility"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_command_visibility")

    # 🔎 Vérification des IDs.
    try:
        guild_id = int(id_serveur)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_serveur` doit être un **identifiant numérique**."),
            ephemeral=True,
        )

    user_id = interaction.user.id
    if id_utilisateur is not None:
        try:
            user_id = int(id_utilisateur)
        except ValueError:
            return await interaction.followup.send(
                view=error_container("`id_utilisateur` doit être un **identifiant numérique**."),
                ephemeral=True,
            )

    guild = interaction.client.get_guild(guild_id)
    if guild is None:
        return await interaction.followup.send(
            view=error_container("GuideOn n'est présent sur **aucun serveur** avec cet ID."),
            ephemeral=True,
        )

    try:
        member = await guild.fetch_member(user_id)
    except discord.NotFound:
        return await interaction.followup.send(
            view=error_container(f"Aucun membre avec l'ID `{user_id}` sur **{guild.name}**."),
            ephemeral=True,
        )
    except discord.HTTPException:
        log.exception("[DEV COMMAND_VISIBILITY] Erreur fetch_member")
        return await interaction.followup.send(
            view=error_container("Impossible de récupérer ce **membre** — réessaie plus tard."),
            ephemeral=True,
        )

    command_filter = [c.strip() for c in commandes.split(",") if c.strip()] if commandes else None

    channel = None
    if id_salon is not None:
        try:
            channel_id = int(id_salon)
        except ValueError:
            return await interaction.followup.send(
                view=error_container("`id_salon` doit être un **identifiant numérique**."),
                ephemeral=True,
            )
        channel = guild.get_channel(channel_id)
        if channel is None:
            return await interaction.followup.send(
                view=error_container(f"Aucun salon avec l'ID `{channel_id}` sur **{guild.name}**."),
                ephemeral=True,
            )

    # 🚀 Envoi du diagnostic.
    try:
        report = await scan_command_permissions(
            interaction.client, guild, member, command_filter=command_filter, channel=channel,
        )
    except discord.HTTPException:
        log.exception("[DEV COMMAND_VISIBILITY] Erreur scan permissions")
        return await interaction.followup.send(
            view=error_container("Permissions manquantes"),
            ephemeral=True,
        )

    view = build_command_visibility_view(report)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@command_visibility.error
async def command_visibility_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)