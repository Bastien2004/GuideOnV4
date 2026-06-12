"""
cogs/alpha/event_regle.py — /alpha event_regle

Envoie les règles des events Alpha dans le salon configuré (ou en réponse éphémère).
Texto statique — à remplacer par les vraies règles quand dispo.
Accessible Modo+ et supérieurs.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_alpha import check_modo_plus
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.managers.alpha_event_config_manager import load_event_config

log = logging.getLogger(__name__)

# ── Règles (placeholders — à remplacer) ──────────────────────

EVENT_RULES = [
    "Respectez les consignes et décisions du staff organisateur en tout temps.",
    "Les insultes, provocations et comportements toxiques envers les autres participants sont interdits.",
    "Tout comportement visant à tricher, exploiter des bugs ou obtenir un avantage déloyal entraîne une disqualification immédiate.",
    "Rejoignez l'event uniquement lorsque le staff vous y invite. Ne tentez pas d'accéder à la zone avant le signal.",
    "Une fois éliminé, quittez la zone de jeu sans perturber le déroulement de la partie.",
    "Le staff Alpha se réserve le droit de sanctionner tout joueur ne respectant pas ces règles.",
]


def build_event_regle_view() -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# ⚔️ Règles des Events Alpha"))
    c.add_item(Separator())
    rules_txt = "\n".join(f"**{i+1}.** {r}" for i, r in enumerate(EVENT_RULES))
    c.add_item(TextDisplay(rules_txt))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="event_regle", description="⚔️ Envoie les règles des events Alpha")
async def event_regle(interaction: Interaction) -> None:

    if not await verifier_ban_utilisateur(interaction): return
    if not await check_modo_plus(interaction, "envoyer les règles des events"): return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "alpha_event_regle"): return
    await tracker_commande(interaction, "alpha_event_regle")

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
                view=error_container("Salon introuvable."), ephemeral=True
            )

    try:
        await channel.send(view=build_event_regle_view())
    except discord.HTTPException:
        log.exception("[EVENT_REGLE] Erreur | guild=%s", interaction.guild_id)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue."), ephemeral=True
        )

    await interaction.followup.send(
        view=success_container(f"Règles des events envoyées dans {channel.mention} !"),
        ephemeral=True,
    )


@event_regle.error
async def event_regle_error(i: discord.Interaction, e: app_commands.AppCommandError):
    await handle_app_command_error(i, e)