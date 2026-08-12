"""
cogs/alpha/event_start.py — Annonce de début d'event M+ Alpha.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from discord import app_commands, Interaction

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.perm_alpha import check_modo_plus, require_alpha_guild
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

from utils.managers.alpha_event_config_manager import load_event_config
from utils.events_alpha import load_events, get_event, STATUS_EMOJIS, STATUS_LABELS
from views.alpha.event_start_view import build_start_event_view

log = logging.getLogger(__name__)


# ============================================================
# 🔎 Autocomplete
# ============================================================

async def _event_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Gère l'auto-complétion des events."""
    events = load_events()
    matches = [e for e in events if current.lower() in e["name"].lower()]
    return [
        app_commands.Choice(
            name=f"{STATUS_EMOJIS.get(e['status'], '?')} {e['name']}",
            value=str(e["id"]),
        )
        for e in matches
    ][:25]


# ============================================================
# 🧭 Commande : /alpha event_start
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="event_start", description="🎮 [M+] Annonce le début d'un event Alpha")
@app_commands.describe(event="Nom de l'event à annoncer")
@app_commands.autocomplete(event=_event_autocomplete)
async def event_start(interaction: Interaction, event: str) -> None:

    # 🌐 Vérification "Discord Alpha" (défense en profondeur, phase 13).
    if not await require_alpha_guild(interaction): return

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction): return

    # 🔐 Vérification des permissions.
    if not await check_modo_plus(interaction, "annoncer un event"): return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_event_start"): return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_event_start")

    # 🔎 Récupération de l'event.
    try:
        event_id = int(event)
        event_data = get_event(event_id)
    except (ValueError, TypeError):
        event_data = None

    if event_data is None:
        return await interaction.followup.send(
            view=error_container("Cet événement est **introuvable**."),
            ephemeral=True,
        )

    # 📁 Chargement de la configuration.
    cfg = await load_event_config(interaction.guild_id)
    channel_id = cfg.get("channel_id")

    # 🔎 Vérification qu'un salon est configuré.
    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Salon non configuré.\n"
                "Utilisez `/dev config_alpha` → **Système Events** pour le définir."
            ),
            ephemeral=True,
        )

    # 🔎 Vérification que le salon existe.
    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon introuvable (ID invalide ou bot sans accès)."),
                ephemeral=True,
            )

    # 🖼️ Préparation de l'image.
    image_path = event_data.get("image", "")
    image_file: discord.File | None = None
    if image_path and os.path.exists(image_path):
        image_file = discord.File(image_path, filename=Path(image_path).name)

    # 💻 Création et envoie de la view.
    view = build_start_event_view(
        event_data,
        cfg.get("ping_role_id"),
        has_image=bool(image_file),
    )

    try:
        kwargs: dict = {"view": view}
        if image_file:
            kwargs["files"] = [image_file]
        await channel.send(**kwargs)
    except discord.HTTPException:
        log.exception("[EVENT_START] Erreur envoi | guild=%s", interaction.guild_id)
        return await interaction.followup.send(
            view=error_container("Une **erreur Discord** est survenue."), ephemeral=True
        )

    # ✅ Confirmation éphémère.
    status_warn = (
        f"\n<:erreur:1495443907281031359> Cet event est en **{STATUS_LABELS.get(event_data['status'], event_data['status'])}**."
        if event_data["status"] != "fonctionne" else ""
    )
    await interaction.followup.send(
        view=success_container(
            f"**{event_data['name']}** annoncé dans {channel.mention} !{status_warn}"
        ),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@event_start.error
async def event_start_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)