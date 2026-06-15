"""
Commande /ng sanction — Affiche le tableau des sanctions d'un serveur NationsGlory.
"""
from __future__ import annotations

import logging
import os

import discord
from discord import app_commands, Interaction, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery
from PIL import Image

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

VIEW_TIMEOUT   = 1000
IMAGES_DIR     = "Source"
SERVEURS_SANS_TABLEAU = {"jade"}


# ============================================================
# 📦 Fonctions utilitaires
# ============================================================

def load_sanction_file(serveur: str) -> tuple[str, str]:
    """Vérifie et retourne le chemin + nom du fichier image. Lève ValueError si invalide."""
    filename = f"tableau_sanction_{serveur}.png"
    chemin   = os.path.join(IMAGES_DIR, filename)

    if not os.path.exists(chemin):
        raise ValueError(f"Le tableau pour **{serveur.capitalize()}** est introuvable.")

    try:
        with Image.open(chemin) as img:
            img.verify()
    except Exception:
        raise ValueError("Le fichier image est corrompu ou illisible.")

    return chemin, filename


def build_sanction_view(serveur: str, chemin: str, filename: str) -> tuple[LayoutView, discord.File]:
    """Construit la view et le fichier image."""
    view      = LayoutView(timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay(f"# <:sanctionner:1495444382587949086> Tableau des sanctions : {serveur.capitalize()}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(
        f"Voici le tableau __officiel__ des sanctions en vigueur sur le **serveur {serveur.capitalize()}**.\n"
        f"-# Ces tableaux ne sont pas définitifs et des modifications peuvent être apportées par le staff."
    ))
    container.add_item(Separator())
    container.add_item(MediaGallery(MediaGalleryItem(f"attachment://{filename}")))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)

    file = discord.File(chemin, filename=filename)
    return view, file


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="sanction", description="📋 Affiche le tableau des sanctions d'un serveur NationsGlory")
@app_commands.describe(serveur="Le serveur NationsGlory dont afficher le tableau")
@app_commands.choices(serveur=SERVER_CHOICES)
async def sanction(interaction: Interaction, serveur: str):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_sanction"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_sanction")

    # ⚠️ Serveurs sans tableau
    if serveur in SERVEURS_SANS_TABLEAU:
        await interaction.followup.send(
            view=error_container(f"Le serveur **{serveur.capitalize()}** ne possède pas encore de tableau des sanctions."),
            ephemeral=True,
        )
        return

    # 🧩 Construction view
    try:
        chemin, filename = load_sanction_file(serveur)
        view, file       = build_sanction_view(serveur, chemin, filename)
        await interaction.followup.send(file=file, view=view)

    except ValueError as e:
        await interaction.followup.send(
            view=error_container(str(e)),
            ephemeral=True,
        )

    except Exception:
        log.exception("Erreur commande /ng sanction")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@sanction.error
async def sanction_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)