"""
Commande /ng autel — Affiche les coordonnées des autels Edora.
"""

import discord
import traceback
import os
import json
from discord import app_commands, Interaction, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery

from utils.control_admin import verifier_commande
from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error


# ============================================================
# 📁 Chemins
# ============================================================

JSON_PATH = os.path.join("data", "ng_json", "ng_coo_autel.json")
IMAGE_PATH = os.path.join("source", "autel_edora.webp")

# ============================================================
# 📦 Chargement JSON
# ============================================================

def load_coords():
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="autel", description="⛪ Affiche les informations sur les autels NationsGlory")
@app_commands.describe(version="Choisis ta version du jeu")
@app_commands.choices(
    version=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock")
    ]
)
async def autel(interaction: Interaction, version: str):

    # 🛡️ Vérification ban utilisateur
    if not await verifier_ban_utilisateur(interaction):
        return

    # ⚙️ Vérification activation commande
    if not await verifier_commande(interaction, "ng_autel"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_autel")

    try:
        await interaction.response.defer(ephemeral=False)
    except discord.NotFound:
        return

    # 📦 Chargement des données
    data = load_coords()
    if data is None:
        return await interaction.followup.send(
            view=error_container("Impossible de charger les coordonnées des autels."),
            ephemeral=True
        )

    coords_dict = data.get(version, {}).get("coords", {})
    if not coords_dict:
        return await interaction.followup.send(
            view=error_container("Aucune donnée trouvée pour cette version."),
            ephemeral=True
        )

    # ============================================================
    # 🧱 Création de la View
    # ============================================================

    view = LayoutView(timeout=600)
    c = Container()

    # 🗒️ Header
    c.add_item(TextDisplay(f"# ⛪ Autels Edora — Version **{version.capitalize()}**"))
    c.add_item(Separator())

    # 🗺️ Coordonnées
    try:
        formatted = "\n".join(
            f"**`N°{num}`** = {coords_dict[num]}"
            for num in sorted(coords_dict, key=lambda x: int(x))
        )
    except Exception:
        return await interaction.followup.send(
            view=error_container("Erreur dans le format du JSON (clés non numériques)."),
            ephemeral=True
        )

    c.add_item(TextDisplay(f"## 📍 Coordonnées des autels\n\n{formatted}\n"))
    c.add_item(Separator())

    # ℹ️ Informations
    c.add_item(TextDisplay(
        "## <:info_1:1490329502771839096> Fonctionnement des autels\n\n"
        "Il existe **10 ruines** réparties sur Edora.\n"
        "Votre objectif est de capturer ces 10 autels en moins d'une heure\n"
        "pour invoquer **le Voriak**, maître d’Edora.\n\n"
        "⚠️ **Zone extrêmement hostile.** ⚠️"
    ))

    # ============================================================
    # 🖼️ IMAGE
    # ============================================================

    file = None

    if os.path.exists(IMAGE_PATH):
        try:
            file = discord.File(IMAGE_PATH, filename="autel_edora.webp")

            c.add_item(Separator())
            c.add_item(
                MediaGallery(
                    MediaGalleryItem("attachment://autel_edora.webp")
                )
            )

        except Exception:
            c.add_item(Separator())
            c.add_item(TextDisplay(
                "⚠️ **Impossible de charger l’image** des autels.\n"
                "Le fichier semble __corrompu__ ou __inaccessible__."
            ))

    else:
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "⚠️ **Aucune image disponible** pour les autels.\n"
            "Veuillez **contacter** un __développeur GuideOn Studio__."
        ))

    # 👣 Footer
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)

    # ✉️ Envoi final
    await interaction.followup.send(view=view, file=file)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@autel.error
async def autel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)