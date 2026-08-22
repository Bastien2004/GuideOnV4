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
     "Afin de garder un **cadre d'échange** __agréable__ : Le **spam** de __message__, de __mention__ ou d'__émoji_ est **interdit**."
     "Tout comme l'**utilisation abusive** de __majuscules__ et le **flood**. De plus, la **seule langue** __autorisé__ est le **français** pour la bonne __compréhension__ de tous. "
     "Veillez également à **respecter** l'__utilisation__ prévue des **salons**."),

    ("🎙️", "Vocal",
     "L'enregistrement d'une conversation vocale sans le consentement des "
     "personnes présentes est strictement interdit.\n"
     "La diffusion de musique, de cris, de screamers ou de sons volontairement "
     "dérangeants dans le but de troller ou de perturber les autres membres est "
     "également sanctionnable."),

    ("🚫", "Contenu interdit",
     "Tout contenu illégal, pornographique, violent, choquant ou inapproprié "
     "est interdit sur le serveur."),

    ("📢", "Publicité",
     "La publicité, l'auto-promotion, le démarchage ou l'envoi de liens vers "
     "d'autres serveurs hors NationsGlory sans autorisation du staff sont "
     "interdits."),

    ("🔐", "Vie privée (dox)",
     "Le partage d'informations personnelles, que ce soit les vôtres ou celles "
     "d'un autre membre, sans autorisation est interdit."),
    ("🛡️", "Staff",
     
     "Les membres du staff peuvent choisir et appliquer les sanctions qu'ils "
     "jugent appropriées, en fonction de la situation et des circonstances.\n"
     "Merci de respecter les décisions prises par le staff.\n"
     "En cas de désaccord avec une sanction ou une décision, vous pouvez "
     "contacter un membre du staff en privé afin d'en discuter calmement."),

    ("⚠️", "Sanctions",
     "Tout non-respect du règlement peut entraîner une sanction. Celle-ci peut "
     "aller d'un simple avertissement jusqu'au bannissement, selon la gravité "
     "des faits et les antécédents du membre."),
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
        "nous vous invitons à **contacter** l'__équipe de modération__ avec le tag suivant : <@&1516427548718792754>.\n"
    ))
    c.add_item(Separator())

    for i, (emoji, title, body) in enumerate(_RULES, start=1):
        c.add_item(TextDisplay(f"**{i}. {emoji}・{title}** {body}\n\n"))

    c.add_item(Separator())

    c.add_item(TextDisplay(
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        ))
    c.add_item(Separator())

    
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view