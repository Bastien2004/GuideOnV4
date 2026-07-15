"""
views/alpha/index_view.py — Interface d'information "Index" du serveur Alpha.

Extrait de cogs/alpha/index.py, même traitement que event_start, event_regle,
event_list et derank (cog réduit à la commande, la construction de la view
et des fichiers attachés vit ici).

Reste en LayoutView simple, PAS BaseLayoutView : ce message n'a aucun
composant interactif (aucun bouton, aucun select) et est posté/édité
publiquement dans un salon pour tout le monde, avec timeout=None (persiste
indéfiniment, volontairement). BaseLayoutView n'apporterait rien ici — pas
de clic à restreindre, pas de timeout à gérer, pas d'erreur de composant à
capturer. Même cas que views/alpha/event_regle_view.py,
views/alpha/event_start_view.py et views/birthday/next_view.py, déjà laissés
en LayoutView pour exactement la même raison.
"""
from __future__ import annotations

import os

import discord
from discord import MediaGalleryItem
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

# ============================================================
# 📁 Fichiers attachés
# ============================================================

_IMAGES = [
    ("source/alpha_affiche.webp", "alpha_affiche.webp"),
    ("source/tableau_sanction_alpha.webp", "tableau_sanction_alpha.webp"),
    ("source/npc_alpha_all.webp", "npc_alpha_all.webp"),
]


def get_fresh_files() -> list[discord.File]:
    """Recharge les fichiers depuis le disque à chaque envoi/édition (attachments Discord non réutilisables)."""
    return [
        discord.File(path, filename=fn)
        for path, fn in _IMAGES if os.path.exists(path)
    ]


def _has(files: list[discord.File], name: str) -> bool:
    return any(f.filename == name for f in files)


# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_index_view(files: list[discord.File]) -> LayoutView:
    """Construction de la view."""
    view = LayoutView(timeout=None)

    c1 = Container()
    c1.add_item(TextDisplay("# <:alpha:1496906799612428368> Index du Alpha"))
    c1.add_item(Separator())
    if _has(files, "alpha_affiche.webp"):
        c1.add_item(MediaGallery(MediaGalleryItem("attachment://alpha_affiche.webp")))
    view.add_item(c1)

    c2 = Container()
    c2.add_item(TextDisplay("## 📖 __Règlement du Serveur__ :"))
    c2.add_item(Separator())
    c2.add_item(TextDisplay(
        "● **Codex** de NationsGlory : [Cliquer ici](https://wiki.nationsglory.fr/fr/article/le-reglement-bedrock-codex-1ssj6k9/) 📖\n"
        "● **Règles internes** du Alpha : [Cliquer ici](https://wiki.nationsglory.fr/fr/article/le-reglement-bedrock-codex-1ssj6k9/) 🧾\n"
        "● **Sanctions** du Alpha : [Cliquer ici](https://wiki.nationsglory.fr/fr/article/le-reglement-bedrock-codex-1ssj6k9/) ⚖️\n"
    ))
    c2.add_item(Separator())
    view.add_item(c2)

    c3 = Container()
    c3.add_item(TextDisplay("## 🎥 __Plateforme de NationsGlory__ :"))
    c3.add_item(Separator())
    c3.add_item(TextDisplay(
        "● <:website:1490331146775560212> **Site Web** : [Visiter](https://nationsglory.fr).\n"
        "● <:Discord:1500400336739766302> Serveur **Discord** : [Rejoindre](https://discord.gg/nationsglory).\n"
        "● <:Youtube:1500400294243205210> Chaîne **Youtube** : [Visiter](https://www.youtube.com/@NationsGlory).\n"
        "● <:Twitch:1500400202195140618> Chaîne **Twitch** : [Visiter](https://www.twitch.tv/nationsgloryfr).\n"
        "● <:X_:1500400261502603387> Compte **X** : [Visiter](https://x.com/NationsGlory).\n"
        "● <:Instagram:1500400141272748082> Compte **Instagram** : [Visiter](https://www.instagram.com/nationsgloryfr/?hl=fr).\n"
        "● <:Tiktok:1500400096033112175> Compte **TikTok** : [Visiter](https://www.tiktok.com/@nationsgloryfr?lang=fr)"
    ))
    c3.add_item(Separator())
    c3.add_item(TextDisplay(
        "📱 N'hésite pas à __t'abonner__ à nos **réseaux sociaux** pour rester __informé__ des **dernières actualités** !"
    ))
    view.add_item(c3)

    c4 = Container()
    c4.add_item(TextDisplay("## 🤝 __Recrutement du Alpha__ :"))
    c4.add_item(Separator())
    c4.add_item(TextDisplay(
        "● <:Builder_2:1500406243955703848> La **Team Builder** → [Candidater](https://nationsglory.fr/forums/category/recrutement-builder.288).\n"
        "● <:Journaliste_2:1500406193724854302> La **Team Journal** → [Candidater](https://nationsglory.fr/forums/category/recrutement-builder.288).\n"
        "● <:Guide_2:1500406282631385158> L'**équipe des Guides** → [Candidater](https://nationsglory.fr/forums/category/recrutement-builder.288).\n"
        "● <:Modo_2:1500406266231783565> La **Modération** → [Candidater](https://nationsglory.fr/forums/category/recrutement-builder.288)."
    ))
    c4.add_item(Separator())
    c4.add_item(TextDisplay(
        "N'hésitez pas à __rejoindre__ nos **équipes** ! Attention à la **qualité** de votre **candidature** !"
    ))
    view.add_item(c4)

    c5 = Container()
    c5.add_item(TextDisplay("## 🌐 __Nos Discords Communautaires__ :"))
    c5.add_item(Separator())
    c5.add_item(TextDisplay(
        "**🌐 __Global__**\n"
        "- <:NationsGlory:1500414113384366261> NationsGlory : https://discord.gg/nationsglory\n"
        "- 📻 LyxiaRadio (ex. NG Radio) : https://discord.gg/cxMZqCNKvD\n"
        "- ⚒️ Association Helyxia https://discord.gg/hcAPsBbsEp\n\n"

        "**🎮 __Bedrock__**\n"
        "- <:Alpha:1500414179650048070> Alpha : https://discord.gg/KxC9E2VPeX\n"
        "- <:Sigma:1500414355773329548> Sigma : https://discord.gg/RcJeepJB2V\n"
        "- <:Omega:1500414132560723978> Oméga : https://discord.gg/cy48ux3Bk2\n"
        "- <:Delta:1500414247098650725> Delta : https://discord.gg/nationsglory-delta-948880111753625642\n"
        "- <:Epsilon:1500414274999418970> Epsilon : https://discord.gg/SAjHxuJTQY\n\n"

        "**💻 __Java__**\n"
        "- <:Jade:1500415549727838238> Jade : https://discord.gg/fphbKQSrH9\n"
        "- <:Mocha:1500415522192228453> Mocha : https://discord.gg/zbTkjGFMZB\n"
        "- <:Blue:1500415616744685648> Blue : https://discord.gg/wQgpfTzAwp\n"
        "- <:White:1500414056710799380> White : https://discord.gg/bf6bNkt2SM\n"
        "- <:Black:1500415629621067826> Black : https://discord.gg/Ck9s96FDCe\n"
        "- <:Cyan:1500415587669643294> Cyan : https://discord.gg/RxAjxtuE2U\n"
        "- <:Lime:1500415534771212439> Lime : https://discord.gg/h54m7VqmWY\n"
        "- <:Coral:1500415601300996226> Coral : https://discord.gg/mZx4CdqngA\n"
        "- <:Pink:1500414086499008612> Pink : https://discord.gg/WXhRE2AN2Y **(close)**\n"
        "- <:Purple:1500414072250695740> Purple : https://discord.gg/bbgqmJjQSB **(close)**\n"
        "- <:Green:1500415562461872198> Green : https://discord.gg/kQHABDCF3W **(close)**\n"
        "- <:Orange:1500414101493387354> Orange : https://discord.gg/HtET56bBQs **(close)**\n"
        "- <:Yellow:1500414000859447408> Yellow : https://discord.gg/z8bBMnwTCW **(close)**\n"
        "- <:RED:1500410048273322035> Red : https://discord.gg/rYGPtgKkpt **(close)**\n"
        "- <:NG_US:1500414650909724834> Ruby : https://discord.gg/W2qyJ8WNSs **(close)**"
    ))
    view.add_item(c5)

    c6 = Container()
    c6.add_item(TextDisplay("## ⚖️ __Tableau des Sanctions__ :"))
    c6.add_item(Separator())
    if _has(files, "tableau_sanction_alpha.webp"):
        c6.add_item(MediaGallery(MediaGalleryItem("attachment://tableau_sanction_alpha.webp")))
    view.add_item(c6)

    c7 = Container()
    c7.add_item(TextDisplay("## 👥 __NPCs du Alpha__ :"))
    c7.add_item(Separator())
    if _has(files, "npc_alpha_all.webp"):
        c7.add_item(MediaGallery(MediaGalleryItem("attachment://npc_alpha_all.webp")))
    c7.add_item(Separator())
    c7.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c7)

    return view