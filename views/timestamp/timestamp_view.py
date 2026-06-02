"""
views/timestamp/timestamp_view.py — Convertisseur de date en timestamp Discord.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Modal, Separator, TextDisplay, TextInput

log = logging.getLogger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")


# ============================================================
# 🧩 Helper pur : parsing + validation
# ============================================================

def parse_date_input(jour: str, mois: str, annee: str, heure: str, minute: str) -> Optional[int]:
    """Coonvertit les champs du modal en timestamp Discord."""
    try:
        dt = datetime(
            year=int(annee),
            month=int(mois),
            day=int(jour),
            hour=int(heure),
            minute=int(minute),
            tzinfo=PARIS_TZ,
        )
        return int(dt.timestamp())
    except (ValueError, OverflowError):
        return None


# ============================================================
# 🎨 View principale
# ============================================================

def build_main_view() -> LayoutView:
    """Construit le panneau d'accueil avec bouton 'Saisir une date'."""

    view = LayoutView(timeout=600)
    container = Container()

    # Header
    container.add_item(TextDisplay("# <:temps:1511260273506259024> __Convertisseur Timestamp__"))
    container.add_item(Separator())

    # Description
    container.add_item(TextDisplay(
        "-# Transforme une **date** en timestamp Discord."
    ))

    # Bouton de saisie
    open_btn = Button(label="📅 Saisir une date", style=ButtonStyle.primary)

    async def open_modal(interaction: Interaction) -> None:
        await interaction.response.send_modal(TimestampModal())

    open_btn.callback = open_modal

    container.add_item(ActionRow(open_btn))
    container.add_item(Separator())

    # Footer
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🎨 View résultat
# ============================================================

def build_result_view(timestamp: int) -> LayoutView:
    """Construit la vue qui affiche les 5 formats Discord + bouton retour."""

    view = LayoutView(timeout=300)
    container = Container()

    # Header
    container.add_item(TextDisplay("# <:temps:1511260273506259024> __Timestamp Discord__"))
    container.add_item(Separator())

    # Timestamp brut + formats
    container.add_item(TextDisplay(
        f"**Timestamp brut :**\n"
        f"`{timestamp}`\n\n"

        f"**Formats Discord :**\n"
        f"`<t:{timestamp}:F>` → <t:{timestamp}:F>\n"
        f"`<t:{timestamp}:f>` → <t:{timestamp}:f>\n"
        f"`<t:{timestamp}:d>` → <t:{timestamp}:d>\n"
        f"`<t:{timestamp}:t>` → <t:{timestamp}:t>\n"
        f"`<t:{timestamp}:R>` → <t:{timestamp}:R>"
    ))

    container.add_item(Separator())

    # Bouton retour
    retour_btn = Button(label="Nouvelle conversion", style=ButtonStyle.secondary, emoji="↩️")

    async def retour_callback(inter: Interaction) -> None:
        await inter.response.edit_message(view=build_main_view())

    retour_btn.callback = retour_callback
    container.add_item(ActionRow(retour_btn))

    # Footer
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📅 Modal de saisie (jour/mois/année/heure/minute)
# ============================================================

class TimestampModal(Modal, title="📅 Conversion en timestamp"):
    """Modal Discord avec 5 champs pour saisir une date."""

    jour = TextInput(label="Jour", placeholder="Ex : 24", max_length=2)
    mois = TextInput(label="Mois", placeholder="Ex : 12", max_length=2)
    annee = TextInput(label="Année", placeholder="Ex : 2025", max_length=4)
    heure = TextInput(label="Heure", placeholder="Ex : 18", max_length=2)
    minute = TextInput(label="Minute", placeholder="Ex : 30", max_length=2)

    async def on_submit(self, interaction: Interaction) -> None:
        timestamp = parse_date_input(
            self.jour.value,
            self.mois.value,
            self.annee.value,
            self.heure.value,
            self.minute.value,
        )

        if timestamp is None:

            from utils.container_universel import error_container
            await interaction.response.send_message(
                view=error_container(
                    "**Date invalide.** Vérifie les valeurs saisies "
                    "(jour 1-31, mois 1-12, heure 0-23, minute 0-59)."
                ),
                ephemeral=True,
            )
            return

        try:
            await interaction.response.edit_message(view=build_result_view(timestamp))

        except (discord.NotFound, discord.HTTPException):
            log.warning("[Timestamp] Édition du message échouée (user=%s)", interaction.user.id)
            await interaction.response.send_message(
                view=build_result_view(timestamp), ephemeral=True
            )