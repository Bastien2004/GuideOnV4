"""
cogs/alpha/event_start.py — /alpha event_start

Annonce le début d'un event dans le salon configuré avec ping, image, description.
Autocomplete sur tous les events (avec emoji statut). Modo+ minimum.
"""
from __future__ import annotations

import logging, os
from pathlib import Path

import discord
from discord import app_commands, Interaction, MediaGalleryItem
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_alpha import check_modo_plus
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container, success_container, warning_container
from utils.error_handler import handle_app_command_error
from utils.managers.alpha_event_config_manager import load_event_config
from utils.events_alpha import load_events, get_event, STATUS_EMOJIS, STATUS_LABELS

log = logging.getLogger(__name__)


# ── Autocomplete ─────────────────────────────────────────────

async def _event_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    events = load_events()
    matches = [e for e in events if current.lower() in e["name"].lower()]
    return [
        app_commands.Choice(
            name=f"{STATUS_EMOJIS.get(e['status'], '?')} {e['name']}",
            value=str(e["id"]),
        )
        for e in matches
    ][:25]


# ── View annonce ──────────────────────────────────────────────

def build_start_event_view(
    event: dict,
    ping_role_id: int | None,
    has_image: bool,
) -> LayoutView:
    ping = f"<@&{ping_role_id}> " if ping_role_id else ""
    filename = Path(event["image"]).name if event.get("image") else None
    status_emoji = STATUS_EMOJIS.get(event["status"], "")

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"# 🎮 {event['name']}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"## {ping}Nous allons débuter un **{event['name']}** !\n\n"
        f"Rejoignez-nous en jeu via la commande `{event['warp']}`."
    ))

    if has_image and filename:
        c.add_item(Separator())
        c.add_item(MediaGallery(MediaGalleryItem(f"attachment://{filename}")))

    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"### 📋 Règles de l'event\n{event['description']}"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"-# {status_emoji} {STATUS_LABELS.get(event['status'], event['status'])} · GuideOn Studio"))
    view.add_item(c)
    return view


# ── Commande ─────────────────────────────────────────────────

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="start_event", description="🎮 Annonce le début d'un event Alpha")
@app_commands.describe(event="Nom de l'event à annoncer")
@app_commands.autocomplete(event=_event_autocomplete)
async def event_start(interaction: Interaction, event: str) -> None:

    if not await verifier_ban_utilisateur(interaction): return
    if not await check_modo_plus(interaction, "annoncer un event"): return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "alpha_event_start"): return
    await tracker_commande(interaction, "alpha_event_start")

    # Récupération de l'event
    try:
        event_id = int(event)
        event_data = get_event(event_id)
    except (ValueError, TypeError):
        event_data = None

    if event_data is None:
        return await interaction.followup.send(
            view=error_container("Event introuvable. Utilisez l'autocomplete pour choisir."),
            ephemeral=True,
        )

    # Avertissement si pas opérationnel
    if event_data["status"] != "fonctionne":
        status_label = STATUS_LABELS.get(event_data["status"], event_data["status"])

    # Config
    cfg = await load_event_config(interaction.guild_id)
    channel_id = cfg.get("channel_id")
    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Salon non configuré.\n"
                "Utilisez `/dev config_alpha` → **Système Events** pour le définir."
            ),
            ephemeral=True,
        )

    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon introuvable (ID invalide ou bot sans accès)."),
                ephemeral=True,
            )

    # Préparer l'image
    image_path = event_data.get("image", "")
    image_file: discord.File | None = None
    if image_path and os.path.exists(image_path):
        image_file = discord.File(image_path, filename=Path(image_path).name)

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
        log.exception("[START_EVENT] Erreur envoi | guild=%s", interaction.guild_id)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue."), ephemeral=True
        )

    # Confirmation éphémère
    status_warn = (
        f"\n⚠️ Cet event est en **{STATUS_LABELS.get(event_data['status'], event_data['status'])}**."
        if event_data["status"] != "fonctionne" else ""
    )
    await interaction.followup.send(
        view=success_container(
            f"**{event_data['name']}** annoncé dans {channel.mention} !{status_warn}"
        ),
        ephemeral=True,
    )


@event_start.error
async def event_start_error(i: discord.Interaction, e: app_commands.AppCommandError):
    await handle_app_command_error(i, e)