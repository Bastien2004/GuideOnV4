"""
cogs/alpha/regle_interne.py — Gestion de l'interface d'affichage des règles internes du Alpha
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_alpha import check_op_alpha
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.managers.alpha_rank_config_manager import load_rank_config

log = logging.getLogger(__name__)


# ============================================================
#  📁 Fonctions utilitaires
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


# ════════════════════════════════════════════════════════════
# 🧭 Commande : /alpha regle_interne
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="regle_interne", description="⚖️ Envoie les règles internes du Alpha")
async def regle_interne(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Permission OP Alpha.
    if not await check_op_alpha(interaction, "**envoyer** les règles internes"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_regle_interne"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_regle_interne")

    # 📋 Récupération des données.
    cfg = await load_rank_config(interaction.guild_id)
    channel_id = cfg.get("content_regle_interne_channel_id")
    emoji_str  = cfg.get("content_regle_interne_emoji")

    # 🔎 Vérification que le salon de règle interne est configuré.
    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Le salon n'est pas configuré.\n"
                "Utilisez `/dev config_alpha` → **Contenu Discord** pour le définir."
            ),
            ephemeral=True,
        )

    # ✉️ Envoi du message dans le salon dédié.
    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon **introuvable** (ID invalide ou bot sans accès)."),
                ephemeral=True,
            )

    try:
        sent = await channel.send(view=build_regle_interne_view())
    except discord.HTTPException:
        log.exception("[REGLE_INTERNE ALPHA] Erreur /alpha regle_interne | guild=%s", interaction.guild_id)
        return await interaction.followup.send(
            view=error_container("Une erreur **Discord** est survenue lors de l'envoi."),
            ephemeral=True,
        )

    # 🤪 Ajout de l'emoji.
    if emoji_str:
        try:
            await sent.add_reaction(emoji_str)
        except discord.HTTPException:
            log.warning("[REGLE_INTERNE ALPHA] Impossible d'ajouter la réaction | guild=%s", interaction.guild_id)

    await interaction.followup.send(
        view=success_container(f"Règles internes envoyées dans {channel.mention} !"),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@regle_interne.error
async def regle_interne_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)