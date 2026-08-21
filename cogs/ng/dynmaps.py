"""
Commande /ng dynmaps — Affiche le lien vers les dynmaps NG du serveur demandé.
"""
from __future__ import annotations

import logging
import os

import discord
from discord import app_commands, Interaction, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.ng_server_choice import SERVER_CHOICES


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 600
IMAGE_PATH   = os.path.join("source", "map_ng.png")

BEDROCK_SERVERS = {"alpha", "sigma", "omega", "delta", "epsilon"}
JAVA_SERVERS    = {"blue", "orange", "yellow", "white", "black", "cyan", "lime", "coral", "red", "mocha", "jade"}


# ============================================================
# 📦 Fonctions utilitaires
# ============================================================

def build_dynmap_text(serveur_name: str, serveur_value: str) -> str:
    """Retourne le texte selon la plateforme du serveur."""
    if serveur_value in BEDROCK_SERVERS:
        return "⚠️ Les dynmaps sont **indisponibles** sur les serveurs **Bedrock**."

    return (
        f"Voici la dynmap du serveur **{serveur_name}** :\n\n"
        f"👉 https://{serveur_value}.nationsglory.fr/"
    )


def build_dynmap_view(serveur_name: str, serveur_value: str) -> tuple[LayoutView, discord.File | None]:
    """Construit la view et le fichier image."""
    container = Container()

    container.add_item(TextDisplay(f"# 🗺️ Dynmaps — {serveur_name}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(build_dynmap_text(serveur_name, serveur_value)))

    file = None
    if os.path.exists(IMAGE_PATH):
        file = discord.File(IMAGE_PATH, filename="map_ng.png")
        container.add_item(Separator())
        container.add_item(MediaGallery(MediaGalleryItem("attachment://map_ng.png")))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view = LayoutView(timeout=VIEW_TIMEOUT)
    view.add_item(container)

    return view, file


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="dynmaps", description="🗺️ Lien des dynmaps NationsGlory")
@app_commands.choices(serveur=SERVER_CHOICES)
async def dynmaps(interaction: Interaction, serveur: app_commands.Choice[str]):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer()
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_dynmaps"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_dynmaps")

    # 🧩 Construction view
    view, file = build_dynmap_view(serveur.name, serveur.value)

    await interaction.followup.send(view=view, file=file)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@dynmaps.error
async def dynmaps_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)