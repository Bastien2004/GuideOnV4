"""
utils/boutique/vip_manager.py — Helpers métier VIP (compat V3).

L'API publique ne change PAS par rapport à la V3 :
    is_vip(user_id) -> bool          (SYNC, instantané, lit le cache)
    await send_vip_error(interaction)

La seule différence : la source de vérité n'est plus le JSON mais la DB,
via le cache du boutique_manager. Tout le code appelant reste identique.
"""
from __future__ import annotations

import discord
from discord.ui import Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.managers.boutique_manager import is_vip_id
from utils.settings import settings


def is_vip(user_id: int) -> bool:
    """True si l'utilisateur est VIP. Lecture sync via le cache boutique."""
    return is_vip_id(user_id)


async def send_vip_error(interaction: discord.Interaction) -> None:
    """Message d'erreur éphémère « accès réservé VIP »."""
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# 🔒 Accès réservé aux utilisateurs VIP"))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        "➤ Cette commande est __réservée__ aux utilisateurs **VIP**.\n"
        "*Votre compte n'est actuellement **pas abonné***.\n\n"
        "__**L'abonnement VIP débloque**__ :\n"
        "• Des commandes exclusives\n"
        "• Des bonus en boutique\n"
        "• Des outils avancés\n"
        "• Un support prioritaire\n"
        "• Des avantages uniques sur tout GuideOn"
    ))
    container.add_item(Separator())

    boutique_btn = Button(
        label="Voir la boutique",
        style=discord.ButtonStyle.link,
        url=settings.website_url,
        emoji="🛒",
    )
    container.add_item(Section(
        TextDisplay("🌟 **Passez VIP pour débloquer cette commande !**"),
        accessory=boutique_btn,
    ))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideON Studio"))

    view.add_item(container)

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(view=view, ephemeral=True)
        else:
            await interaction.followup.send(view=view, ephemeral=True)
    except (discord.HTTPException, discord.InteractionResponded):
        pass