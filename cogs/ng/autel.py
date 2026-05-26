"""
Commande /ng autel — Affiche les coordonnées des autels Edora.
"""

import discord
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
# 📦 Fonctions utilitaires
# ============================================================

def load_coords():
    """Charge le JSON contenant les coordonnées."""
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def format_coords(coords_dict: dict) -> str:
    """Formate les coordonnées en texte lisible."""
    try:
        return "\n".join(
            f"**`N°{num}`** = {coords_dict[num]}"
            for num in sorted(coords_dict, key=lambda x: int(x))
        )
    except Exception:
        return None


def build_image_block(container: Container):
    """Ajoute l'image si disponible, sinon un message d'erreur."""
    if not os.path.exists(IMAGE_PATH):
        container.add_item(Separator())
        container.add_item(TextDisplay(
            "⚠️ **Aucune image disponible** pour les autels.\n"
            "Veuillez **contacter** un __développeur GuideOn Studio__."
        ))
        return None

    try:
        file = discord.File(IMAGE_PATH, filename="autel_edora.webp")

        container.add_item(Separator())
        container.add_item(
            MediaGallery(
                MediaGalleryItem("attachment://autel_edora.webp")
            )
        )
        return file

    except Exception:
        container.add_item(Separator())
        container.add_item(TextDisplay(
            "⚠️ **Impossible de charger l’image** des autels.\n"
            "Le fichier semble __corrompu__ ou __inaccessible__."
        ))
        return None


def build_view(version: str, coords_text: str):
    """Construit la LayoutView complète."""
    view = LayoutView(timeout=600)
    c = Container()

    # Header
    c.add_item(TextDisplay(f"# ⛪ Autels Edora — Version **{version.capitalize()}**"))
    c.add_item(Separator())

    # Coordonnées
    c.add_item(TextDisplay(f"## 📍 Coordonnées des autels\n\n{coords_text}\n"))
    c.add_item(Separator())

    # Informations
    c.add_item(TextDisplay(
        "## <:information:1495446355395612794> Fonctionnement des autels\n\n"
        "Il existe **10 ruines** réparties sur Edora.\n"
        "Votre objectif est de capturer ces 10 autels en moins d'une heure\n"
        "pour invoquer **le Voriak**, maître d’Edora.\n\n"
        "⚠️ **Zone extrêmement hostile.** ⚠️"
    ))

    # Image
    file = build_image_block(c)

    # Footer
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view, file


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

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ng_autel"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ng_autel")


    # 📁 Chargement JSON.
    data = load_coords()
    if data is None:
        return await interaction.followup.send(
            view=error_container("Impossible de **charger** les __coordonnées des autels__."),
            ephemeral=True
        )

    coords_dict = data.get(version, {}).get("coords", {})
    if not coords_dict:
        return await interaction.followup.send(
            view=error_container("**Aucune donnée** trouvée pour cette version."),
            ephemeral=True
        )

    # ✏️ Formatage
    coords_text = format_coords(coords_dict)
    if coords_text is None:
        return await interaction.followup.send(
            view=error_container("**Erreur** dans le format du JSON."),
            ephemeral=True
        )

    # 🧩 Construction de la View
    view, file = build_view(version, coords_text)

    # ✉️ Envoi final
    await interaction.followup.send(view=view, file=file)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@autel.error
async def autel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)