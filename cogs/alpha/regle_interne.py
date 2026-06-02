"""
cogs/alpha/regle_interne.py — Commande /alpha regle_interne.

Envoie les règles internes du serveur Alpha dans un salon cible.
Réservé aux Modérateurs+ et supérieurs.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_alpha import check_modo_plus
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

log = logging.getLogger(__name__)

# ============================================================
# 📁 Constantes
# ============================================================

TARGET_CHANNEL_ID = 1496770597101764688


# ============================================================
# 🧱 View
# ============================================================

def build_regle_interne_view() -> LayoutView:
    view = LayoutView(timeout=None)

    c = Container()
    c.add_item(TextDisplay("# <:Alpha:1500414179650048070> Les Règles Internes du Alpha"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        "●  Règles **spécifiques** du Alpha : 📙 [Consulter](https://nationsglory.fr/forums/thread/les-regles-diverses.77236).\n"
        "●  Règles sur les **Unescos** : 🏦 [Consulter](https://nationsglory.fr/forums/thread/les-regles-sur-les-unesco.77231).\n"
        "●  Règles sur le **Full-build** : 🏗️ [Consulter](https://nationsglory.fr/forums/thread/les-regles-sur-les-full-build.77232).\n"
        "●  Règles sur les **Assauts** : 🪖 [Consulter](https://nationsglory.fr/forums/thread/les-regles-sur-les-assauts.77234).\n"
        "●  Règles sur l'**Architecture** : 🧱 [Consulter](https://nationsglory.fr/forums/thread/les-regles-sur-l039architecture.77233)."
    ))

    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view


# ============================================================
# 🧭 Commande
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="regle_interne", description="⚖️ Envoie les règles internes du Alpha")
async def regle_interne(interaction: Interaction) -> None:

    # 🛡️ Ban bot
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Permission Modo+
    if not await check_modo_plus(interaction, "envoyer les règles internes"):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande
    if not await verifier_commande(interaction, "alpha_regle_interne"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "alpha_regle_interne")

    # 💻 Récupération salon
    channel = interaction.client.get_channel(TARGET_CHANNEL_ID)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(TARGET_CHANNEL_ID)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon introuvable."),
                ephemeral=True,
            )

    # 🚀 Envoi
    try:
        await channel.send(view=build_regle_interne_view())
    except discord.HTTPException:
        log.exception("Erreur /alpha regle_interne | guild=%s", interaction.guild_id)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue."),
            ephemeral=True,
        )

    await interaction.followup.send(
        view=success_container(f"Règles internes envoyées dans {channel.mention} !"),
        ephemeral=True,
    )


# ============================================================
# ❌ Erreurs
# ============================================================

@regle_interne.error
async def regle_interne_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)