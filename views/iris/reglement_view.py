"""
views/iris/reglement_view.py — Contenu du règlement Iris, posté/édité par
/iris reglement (cogs/iris/reglement.py).

LayoutView simple, PAS BaseLayoutView : ce message n'a aucun composant
interactif (aucun bouton, aucun select) et est posté/édité publiquement
dans un salon pour tout le monde, avec timeout=None (persiste indéfiniment,
volontairement) — même traitement que views/alpha/nous_rejoindre_view.py.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

IMAGE_PATH = "source/reglement_iris.webp"
IMAGE_FILENAME = "reglement_iris.webp"

# (emoji, titre, texte) — dans l'ordre d'affichage.
_RULES: list[tuple[str, str, str]] = [
    ("🤝", "Respect",
     "Le respect entre les membres est primordial. Les insultes, provocations, "
     "moqueries répétées, harcèlement ou comportements visant à créer des "
     "conflits ne sont pas autorisés."),
    ("💬", "Salons",
     "Merci d'utiliser les salons prévus pour chaque sujet et de respecter leur "
     "utilisation. Évitez également le spam, le flood et les messages répétitifs."),
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
    """
    Reconstruit le(s) discord.File à chaque appel de la commande : un objet
    discord.File est consommé après un seul envoi/edit, il ne doit jamais
    être mis en cache au niveau module (même principe que
    views/alpha/nous_rejoindre_view.py).

    Retourne une liste vide si l'image est introuvable sur disque, plutôt
    que de faire planter toute la commande — le règlement texte reste
    envoyé/mis à jour sans l'image dans ce cas.
    """
    try:
        return [discord.File(IMAGE_PATH, filename=IMAGE_FILENAME)]
    except FileNotFoundError:
        return []


# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_reglement_view(fresh_files: list[discord.File]) -> LayoutView:
    """
    Construit le règlement Iris. `fresh_files` : sortie de get_fresh_files()
    pour CET appel — référencée ici via `attachment://{filename}` pour que
    l'image apparaisse intégrée dans le container (pas comme une pièce
    jointe séparée sous le message).
    """
    view = LayoutView(timeout=None)

    c = Container()
    c.add_item(TextDisplay(
        "# 📜 Règlement Iris\n"
        "Bienvenue sur **Iris** !\n"
        "Afin de garder une bonne ambiance et un serveur agréable pour tout "
        "le monde, merci de prendre quelques minutes pour lire et respecter "
        "ce règlement."
    ))
    c.add_item(Separator())

    for i, (emoji, title, body) in enumerate(_RULES, start=1):
        c.add_item(TextDisplay(f"**{i}. {emoji}・{title}**\n{body}"))
        c.add_item(Separator())

    if fresh_files:
        c.add_item(MediaGallery(discord.MediaGalleryItem(media=f"attachment://{IMAGE_FILENAME}")))
        c.add_item(Separator())

    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view