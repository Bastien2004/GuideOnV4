"""
views/iris/reglement_view.py — Gère le règlement du serveur iris.
"""

from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

IMAGE_PATH = "source/reglement_iris.webp"
IMAGE_FILENAME = "reglement_iris.webp"


_RULES: list[tuple[str, str, str]] = [

    ("🤝", "Respect",
     "Le **respect** entre les membres est primordial. Les __insultes__, __provocations__, "
     "__moqueries répétées__, __harcèlement__ ou comportements visant à créer des "
     "__conflits__ ne sont **pas autorisés**."),

    ("💬", "Salons",
     "Afin de garder un **cadre d'échange** __agréable__ : Le **spam** de __message__, de __mention__ ou d'__émoji__ est **interdit**."
     "Tout comme l'**utilisation abusive** de __majuscules__ et le **flood**. De plus, la **seule langue** __autorisé__ est le **français** pour la bonne __compréhension__ de tous. "
     "Veillez également à **respecter** l'__utilisation__ prévue des **salons**."),

    ("🎙️", "Vocal",
     "L'**enregistrement** d'une __conversation vocale__ est **strictement interdit** et passible de **poursuite judiciaire**."
     "La **diffusion** de __musique__, de __cris__, de __screamers__ ou de __sons dérangeants__ " 
     "dans le but de **troller** ou de **perturber** un salon __vocal__ est également sanctionnable."),

    ("🚫", "Contenu illégal",
     "Les propos **racistes**, **homophobes**, **grossophobe**, **antisémithes** ou incitant à la **haine**, "
     "ainsi que tout autres propos __interdit__ par la **loi française** sont **formellement interdit** et feront l'objet de **sanction** __très lourde__. " 
     "De manière générale tout contenus **violent**, **choquant**, **inapproprié** est __formellement interdit__ sur le serveur."),

    ("📢", "Publicité",
     "Toutes **publicitées** __extérieures__ à NationsGlory sont **strictement interdite** sur le serveur Discord, "
     "quelles concernent **Minecraft®** ou non. Le **démarchage** via les __messages privés__ est aussi **prohibé**."),

    ("🔐", "Vie privée (dox)",
     "Le **partage d'informations personnelles** permettant l'**identification** d'une personne, qu'elles soient les __vôtres__ ou celles "
     "d'un __autre membre__, même **consenti** pourra entraîner un __bannissement__ de nos **services**."),

    ("🛡️", "Staff",
     "Les __membres du staff__ sont libres de **choisir** et d'**appliquer** les sanctions qu'ils jugent **appropriées**, "
     "en fonction de la **situation**, des **circonstances** et des **antécédents** du membre."
     "Merci de __respecter__ toutes les **décisions** prises par le staff. Cependant l'erreur reste humaine. "
     "En cas de **désaccord** avec une sanction, vous pouvez __contacter__ un membre du staff afin d'en **discuter calmement**."),

]


# ============================================================
# 📎 Fichiers — image toujours fraîche
# ============================================================

def get_fresh_files() -> list[discord.File]:
    """Gestion de l'image."""
    try:
        return [discord.File(IMAGE_PATH, filename=IMAGE_FILENAME)]
    except FileNotFoundError:
        return []


# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_reglement_view(fresh_files: list[discord.File]) -> LayoutView:
    """Construit le règlement Iris."""

    view = LayoutView(timeout=None)

    c = Container()

    if fresh_files:
        c.add_item(MediaGallery(discord.MediaGalleryItem(media=f"attachment://{IMAGE_FILENAME}")))
        c.add_item(Separator())
    
    c.add_item(TextDisplay(
        "# <:Iris:1540303650575097896> Règlement du serveur Iris\n"
        "❝ Afin de garder une **bonne ambiance** et un serveur **agréable** pour tout "
        "le monde, merci de prendre quelques minutes pour **lire** et **respecter** "
        "ce __règlement__.\n\n"

        "<:erreur:1495443907281031359> Tout manquement à celui-ci, vous exposera à **diverses sanctions**. "
        "Du __rappel à l'odre__ jusqu'au __bannissement définitif__.\n\n"

        "Si vous êtes **victime** ou **témoin** d'une quelconque infraction nuissant à la bonne tenue de ce Discord, "
        "nous vous invitons à **contacter** l'__équipe de modération__ avec le tag suivant :\n"
        "➤ <@&1516427548718792754>.\n"
    ))
    c.add_item(Separator())

    for i, (emoji, title, body) in enumerate(_RULES, start=1):
        c.add_item(TextDisplay(f"**{i}. {emoji}・{title}** {body}\n\n"))
        c.add_item(Separator())
    
    c.add_item(TextDisplay(
            "Le staff se réserve le droit de **modifier** ce règlement à **tout moment**.\n"
            "-# Dernière modification : 22/08/2026"
        ))
    c.add_item(Separator())
    
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view