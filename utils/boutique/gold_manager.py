"""
utils/boutique/gold_manager.py — Helpers métier Gold+ (compat V3).

API publique inchangée vs V3 :
    is_gold(guild_id) -> bool        (SYNC, instantané, lit le cache)
    await send_gold_error(interaction)

Source de vérité = DB via le cache du boutique_manager.
"""
from __future__ import annotations

import discord
from discord.ui import Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.managers.boutique_manager import is_gold_id
from utils.settings import settings


def is_gold(guild_id: int) -> bool:
    """True si le serveur possède l'abonnement Gold+. Lecture sync via cache."""
    return is_gold_id(guild_id)


async def send_gold_error(interaction: discord.Interaction) -> None:
    """Message d'erreur éphémère « fonctionnalité Gold+ »."""
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# ✨ Commande Premium — accès restreint"))
    container.add_item(TextDisplay("### 🔒 Fonctionnalité Gold+"))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        "Cette commande est réservée aux serveurs disposant de l'abonnement **Gold+**.\n"
        "Votre serveur ne possède pas encore cet accès."
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay("### ✨ Avantages Gold+"))
    container.add_item(TextDisplay(
        "• 🚀 Limites étendues.\n"
        "• 🧠 Fonctionnalités avancées.\n"
        "• 🎯 Outils exclusifs.\n"
        "• 💬 Support prioritaire."
    ))
    container.add_item(Separator())

    boutique_btn = Button(
        label="Accéder à la boutique",
        style=discord.ButtonStyle.link,
        url=settings.website_url,
        emoji="🛒",
    )
    container.add_item(Section(
        TextDisplay("## 🎁 Passez à Gold+ dès maintenant"),
        accessory=boutique_btn,
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        "-# 💡 Astuce : améliorez votre serveur avec des fonctionnalités premium"
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# 🔧 GuideOn Studio"))

    view.add_item(container)

    if not interaction.response.is_done():
        await interaction.response.send_message(view=view, ephemeral=True)
    else:
        await interaction.followup.send(view=view, ephemeral=True)