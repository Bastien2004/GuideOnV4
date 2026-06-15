"""
Commande /ng rd — Affiche les infos d'un palier de R&D NationsGlory.
"""
from __future__ import annotations

import json
import logging

import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

VIEW_TIMEOUT  = 1000
RD_JSON_PATH  = "data/ng_json/rd.json"

try:
    with open(RD_JSON_PATH, "r", encoding="utf-8") as _f:
        RD_DATA: dict = json.load(_f)
except Exception:
    log.exception("Erreur chargement JSON R&D")
    RD_DATA = {}

PALIER_LIMITS = {
    "bedrock": {"GENERAL": 15, "MILITAIRE": 16, "RESSOURCE": 15, "INDUSTRIE": 12, "TECHNOLOGIE": 7},
    "java":    {"GENERAL": 15, "MILITAIRE": 16, "RESSOURCE": 15, "INDUSTRIE": 12, "TECHNOLOGIE": 7},
}


# ============================================================
# 📦 Fonctions utilitaires
# ============================================================

def get_rd_data(version: str, branche: str, palier: int) -> dict:
    """Retourne les données d'un palier R&D, lève ValueError si introuvable."""
    try:
        return RD_DATA[version][branche][str(palier)]
    except KeyError:
        raise ValueError(f"Données introuvables pour `{version}/{branche}/{palier}`.")


def build_rd_view(
    version_name: str,
    branche_name: str,
    palier: int,
    data: dict,
    version_val: str,
) -> LayoutView:
    """Construit la view d'un palier R&D."""
    view      = LayoutView(timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay(f"# <:information:1495446355395612794> R&D {version_name}"))
    container.add_item(TextDisplay(f"**Branche :** `{branche_name}`  •  **Palier :** `{palier}`"))
    container.add_item(Separator())

    conditions = "\n".join(f"• {c}" for c in data.get("condition", [])) or "Aucune condition"
    container.add_item(TextDisplay(f"### ⚖️ Conditions\n{conditions}"))
    container.add_item(Separator())

    recompenses = "\n".join(f"• {r}" for r in data.get("recompense", [])) or "Aucune récompense"
    container.add_item(TextDisplay(f"### 🎁 Récompenses\n{recompenses}"))

    if version_val == "java":
        temps = data.get("temps_recherche", "Inconnu")
        container.add_item(Separator())
        container.add_item(TextDisplay(f"⏳ **Temps de recherche :** `{temps}`"))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="rd", description="📘 Affiche les infos d'un palier de R&D")
@app_commands.describe(
    version="Version du serveur",
    branche="Branche de recherche",
    palier="Numéro du palier",
)
@app_commands.choices(
    version=[
        app_commands.Choice(name="Java",    value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock"),
    ],
    branche=[
        app_commands.Choice(name="Général",      value="GENERAL"),
        app_commands.Choice(name="Militaire",     value="MILITAIRE"),
        app_commands.Choice(name="Ressources",    value="RESSOURCE"),
        app_commands.Choice(name="Industrie",     value="INDUSTRIE"),
        app_commands.Choice(name="Technologie",   value="TECHNOLOGIE"),
    ],
)
async def rd(interaction: Interaction, version: app_commands.Choice[str], branche: app_commands.Choice[str], palier: str):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_rd"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_rd")

    # 🔎 Validation palier
    try:
        palier_int = int(palier)
    except ValueError:
        await interaction.followup.send(
            view=error_container("Le palier doit être un **nombre entier**."),
            ephemeral=True,
        )
        return

    max_palier = PALIER_LIMITS.get(version.value, {}).get(branche.value, 0)
    if palier_int < 1 or palier_int > max_palier:
        await interaction.followup.send(
            view=error_container(
                f"Palier invalide. Pour **{branche.name}** ({version.name}), "
                f"choisissez entre 1 et {max_palier}."
            ),
            ephemeral=True,
        )
        return

    # 🧩 Construction view
    try:
        data = get_rd_data(version.value, branche.value, palier_int)
        view = build_rd_view(version.name, branche.name, palier_int, data, version.value)
        await interaction.followup.send(view=view)

    except ValueError as e:
        await interaction.followup.send(
            view=error_container(str(e)),
            ephemeral=True,
        )

    except Exception:
        log.exception("Erreur commande /ng rd")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@rd.error
async def rd_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)