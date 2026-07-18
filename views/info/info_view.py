"""
views/info/info_view.py — Présentation du bot GuideON
"""

from __future__ import annotations

from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.settings import settings

COMMUNITY_INVITE_URL = "https://discord.com/invite/p22xkCPDnq"
LIEN = settings.website_url

# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_info_view() -> LayoutView:
    """Construction de la view."""
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# <:GuideON:1490361480980332676> __GuideOn — Bot Discord__"))
    container.add_item(Separator())

    container.add_item(
        TextDisplay(
            "👋 **Bienvenue !**\n\n"
            "Je suis **GuideOn**, un bot Discord français conçu pour\n"
            "**simplifier, sécuriser et enrichir** la __gestion__ de ton serveur.\n\n"
            "Que tu gères une **communauté classique** ou un serveur\n"
            "**NationsGlory**, je t'accompagne au quotidien."
        )
    )
    container.add_item(Separator())

    container.add_item(
        TextDisplay(
            "⚙️ __**Fonctionnalités principales :**__\n\n"

            "• 🎟️ Système de tickets avancé\n"
            "• 🛡️ Outils de modération & sécurité\n"
            "• 👋 Messages de bienvenue intelligents\n"
            "• 🎭 Outils de gestion de rôle\n"
            "• 🎮 Commandes dédiées à NationsGlory\n"
            "• 🧩 Modules premium & personnalisés\n"
            "• 📦 Et plein d'autres systèmes très cool"
        )
    )
    container.add_item(Separator())

    container.add_item(
        TextDisplay(
            "📚 **__Besoin d'aide__ ?**\n\n"
            "• Consulte toutes les commandes avec **`/wiki`**\n"
            "• Rejoins-nous sur notre serveur Discord\n"
            "• Passe par notre nouveau site"
        )
    )
    container.add_item(Separator())

    site_btn = Button(
        label="🌐 Accéder au site",
        style=ButtonStyle.link,
        url=LIEN,
    )

    discord_btn = Button(
        label="🤝 Nous rejoindre",
        style=ButtonStyle.link,
        url=COMMUNITY_INVITE_URL,
    )

    container.add_item(ActionRow(site_btn, discord_btn))
    container.add_item(Separator())

    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view