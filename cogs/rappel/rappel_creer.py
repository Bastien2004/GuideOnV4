"""
cogs/rappel/rappel_creer.py — Commande /rappel créer <temps> <message> [destination].
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container, success_container
from utils.control_admin import verifier_commande
from utils.datetime_utils import now_utc, parse_duration
from utils.error_handler import handle_app_command_error
from utils.managers.reminder_manager import ReminderLimitError, create_reminder
from utils.track_commande import tracker_commande

log = logging.getLogger(__name__)

MIN_REMINDER_SECONDS = 10
MAX_REMINDER_SECONDS = 31_536_000  # 1 an — même plafond de bon sens que les sanctions temporaires.
MAX_MESSAGE_LENGTH = 500

DESTINATION_CHOICES: list[app_commands.Choice[str]] = [
    app_commands.Choice(name="📩 Message privé", value="mp"),
    app_commands.Choice(name="💬 Ce salon", value="salon"),
]


# ============================================================
# ⏰ Commande : /rappel créer
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="créer", description="⏰ Crée un rappel personnel ponctuel")
@app_commands.describe(
    temps="Dans combien de temps (ex: 10m, 2h, 1d2h30m)",
    message="Le texte du rappel",
    destination="Où recevoir le rappel (MP par défaut)",
)
@app_commands.choices(destination=DESTINATION_CHOICES)
async def rappel_creer(
    interaction: discord.Interaction,
    temps: str,
    message: str,
    destination: str = "mp",
) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer (éphémère : réclamation personnelle).
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "rappel_creer"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "rappel_creer")

    # 📏 Validation du message.
    message = message.strip()
    if not message:
        await interaction.followup.send(
            view=error_container("Le **message** du rappel ne peut pas être vide."),
            ephemeral=True,
        )
        return
    if len(message) > MAX_MESSAGE_LENGTH:
        await interaction.followup.send(
            view=error_container(f"Le **message** ne peut pas dépasser **{MAX_MESSAGE_LENGTH}** caractères."),
            ephemeral=True,
        )
        return

    # ⏳ Validation de la durée.
    try:
        delta = parse_duration(temps)
        duration_seconds = int(delta.total_seconds())
    except ValueError:
        await interaction.followup.send(
            view=error_container(
                "Format de durée invalide. Exemples valides : `10m`, `2h`, `1d2h30m`."
            ),
            ephemeral=True,
        )
        return

    if duration_seconds < MIN_REMINDER_SECONDS:
        await interaction.followup.send(
            view=error_container(f"Le rappel doit être dans au moins **{MIN_REMINDER_SECONDS} secondes**."),
            ephemeral=True,
        )
        return
    if duration_seconds > MAX_REMINDER_SECONDS:
        await interaction.followup.send(
            view=error_container("Le rappel ne peut pas être programmé à plus d'**1 an**."),
            ephemeral=True,
        )
        return

    due_at = now_utc() + delta

    try:
        reminder = await create_reminder(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            destination=destination,
            message=message,
            due_at=due_at,
        )
        due_ts = int(reminder["due_at"].timestamp())
        await interaction.followup.send(
            view=success_container(
                f"Rappel **#{reminder['id']}** programmé pour <t:{due_ts}:f> (<t:{due_ts}:R>).\n"
                f"-# ➥ Envoyé en {'MP' if destination == 'mp' else 'salon'}."
            ),
            ephemeral=True,
        )

    except ReminderLimitError as exc:
        await interaction.followup.send(
            view=error_container(
                f"Tu as déjà **{exc.limit} rappels** en attente — annule-en un avec `/rappel annuler` avant d'en créer un nouveau."
            ),
            ephemeral=True,
        )

    except Exception:
        log.exception(
            "[RAPPEL CRÉER] Échec de création (guild=%s, user=%s)",
            interaction.guild.id, interaction.user.id,
        )
        await interaction.followup.send(
            view=error_container("Impossible de créer ce **rappel**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@rappel_creer.error
async def rappel_creer_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
