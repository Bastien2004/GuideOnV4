"""
cogs/dev/command_visibility.py — Diagnostique pourquoi une commande
guild-scoped (ngstaff, iris, alpha, dev...) n'est plus visible pour un
membre sur un serveur précis.

Contexte : ngstaff/iris/alpha/dev sont synchronisées serveur par serveur
(bot.py::_sync_commands), sans aucun default_member_permissions fixé dans
le code. Si une commande fonctionne sur un serveur mais plus sur un autre
pour le même membre, la cause ne peut donc venir que d'un overwrite de
permission configuré manuellement sur CE serveur (Server Settings →
Intégrations → GuideOn) — voir utils/discord_command_permissions.py.
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
    id_serveur="ID du serveur à analyser (ex : l'ID d'Iris)",
    id_utilisateur="ID du membre à analyser (par défaut : vous)",
    commandes="Noms de commandes à filtrer, séparés par des virgules (ex : ngstaff,iris) — vide = toutes",
)
async def command_visibility(
    interaction: Interaction,
    id_serveur: str,
    id_utilisateur: str | None = None,
    commandes: str | None = None,
) -> None:

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

    # 🚀 Scan et envoi du diagnostic.
    try:
        report = await scan_command_permissions(
            interaction.client, guild, member, command_filter=command_filter,
        )
    except discord.HTTPException:
        log.exception("[DEV COMMAND_VISIBILITY] Erreur scan permissions")
        return await interaction.followup.send(
            view=error_container(
                "Impossible de récupérer les **permissions de commande** Discord — le bot a-t-il bien "
                "le scope `applications.commands` sur ce serveur ?"
            ),
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