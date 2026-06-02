"""
cogs/alpha/nous_rejoindre.py — Commande /alpha nous_rejoindre.

Envoie le tutoriel pour rejoindre le serveur Alpha Bedrock dans un salon cible.
Réservé aux Modérateurs+ et supérieurs.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_alpha import check_modo_plus
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

log = logging.getLogger(__name__)

# ============================================================
# 📁 Constantes
# ============================================================

TARGET_CHANNEL_ID = 1496765741125468180
ROLE_TO_PING      = 1496771752142049351
EMOJI_TO_ADD      = 1496902732316016665

# Chemins des images (fichiers statiques dans source/)
_IMAGES = [
    ("source/join_alpha.png",         "join_alpha.png"),
    ("source/version_obsolete.png",   "version_obsolete.png"),
    ("source/wl.png",                 "wl.png"),
]


# ============================================================
# 🖼️ Helpers fichiers
# ============================================================

def _get_fresh_files() -> list[discord.File]:
    import os
    files = []
    for path, filename in _IMAGES:
        if os.path.exists(path):
            files.append(discord.File(path, filename=filename))
    return files


def _has(files: list[discord.File], name: str) -> bool:
    return any(f.filename == name for f in files)


# ============================================================
# 🧱 View
# ============================================================

def build_nous_rejoindre_view(files: list[discord.File]) -> LayoutView:
    view = LayoutView(timeout=None)

    # ── Container 1 — Introduction ────────────────────────────────────────
    c1 = Container()
    c1.add_item(TextDisplay(
        f"# <:alpha:1496906799612428368> Nous rejoindre — Serveur Alpha | <@&{ROLE_TO_PING}>"
    ))
    c1.add_item(Separator())
    c1.add_item(TextDisplay(
        "## 🎮 Bienvenue sur NationsGlory Alpha\n\n"
        "Voici un guide simple pour **rejoindre** le serveur __Alpha NationsGlory Bedrock__.\n"
        "Lis attentivement chaque étape pour éviter les erreurs. 📒"
    ))
    c1.add_item(Separator())
    if _has(files, "join_alpha.png"):
        c1.add_item(MediaGallery(MediaGalleryItem("attachment://join_alpha.png")))
    view.add_item(c1)

    # ── Container 2 — Console ─────────────────────────────────────────────
    c2 = Container()
    c2.add_item(TextDisplay(
        "## 🧭 __Étapes pour rejoindre le serveur__ :\n\n"
        "### 1. __Joueurs PS/xBox/Switch__ 🎮\n"
        "D'abord tu dois suivre les **obligations** pour pouvoir jouer à Minecraft __en ligne__ ! \n"
        "Ainsi, tu dois évidemment posséder le **jeu** __Minecraft Bedrock__, avoir un **compte Microsoft** valide, "
        "un **abonnement** selon la console (type PS+ pour Playstation) "
        "et un accès stable à **internet**.\n\n"
        "Ensuite, tu as **plusieurs façons** de te __connecter__ sur notre serveur."
    ))
    c2.add_item(Separator())
    c2.add_item(TextDisplay(
        "1️⃣ __**Connexion via bot**__\n\n"
        "Tu devras **ajouter** en ami Minecraft, l'un des comptes suivants :\n"
        "- `BCMain` (*bot principal*).\n"
        "- `BCMain1, BCMain2, BCMain3 ou BCMain4` (*bot de secours anti saturation*).\n\n"
        "**Patiente** jusqu'à ce que tu vois le bot dans ta **liste d'amis**, n'hésite pas à __relancer__ Minecraft.\n"
        "Dès que tu le vois, **rejoins sa partie**, tu arriveras sur une interface où tu devras donner l'__ip__ et le __port__ :\n"
        "- **IP** : `alpha.nationsglory.fr`\n"
        "- **Port** : `19100`\n\n"
        "2️⃣ __**Application externe**__\n\n"
        "Tu peux aussi utiliser une __application externe__ comme **BedrockTogether** ou **MC Server Connector**.\n"
        "Pour cela, **télécharge** l'application sur ton __téléphone__, assure-toi que les appareils soient connectés "
        "sur le **même réseau**.\n"
        "Puis renseigne l'ip du serveur `alpha.nationsglory.fr` et le port `19100`. "
        "Tu recevras ainsi une **invitation** pour rejoindre le serveur sur Minecraft en partie **'LAN'**."
    ))
    c2.add_item(Separator())
    view.add_item(c2)

    # ── Container 3 — PC & Mobile ─────────────────────────────────────────
    c3 = Container()
    c3.add_item(TextDisplay(
        "### 2. __Joueurs PC et Téléphone (iOS & Android)__ 💻\n"
        "Tu devras posséder le jeu **Minecraft Bedrock** ainsi qu'un **compte Microsoft** valide et un accès stable à **internet**. "
        "Il n'est pas possible d'avoir un Minecraft Bedrock dit 'crack'. "
        "De plus le serveur n'est pas accessible depuis **Minecraft Java**.\n\n"
        "Une fois que tu remplis les **prérequis**, lance ton jeu, rejoins l'onglet **'Serveurs'** puis **'Nouveau serveur'** et "
        "remplis les __informations suivantes__ :\n"
        "- **Nom du serveur** : `NationsGlory Alpha`\n"
        "- **Adresse du serveur** : `alpha.nationsglory.fr`\n"
        "- **Port** : `19100`\n\n"
        "Ensuite, clique sur **'Ajouter et jouer'**. Tu peux désormais __profiter__ de ton **expérience NationsGlory** !\n\n"
        "⚠️ Si tu as besoin d'**informations supplémentaires** pour te connecter, "
        "les __staffs__ sont à ta disposition pour t'**aider** !"
    ))
    c3.add_item(Separator())
    view.add_item(c3)

    # ── Container 4 — Erreurs fréquentes ─────────────────────────────────
    c4 = Container()
    c4.add_item(TextDisplay("## 🐛 __Erreurs fréquentes__ :"))
    c4.add_item(Separator())
    c4.add_item(TextDisplay(
        "1️⃣ __**Erreur : 'Version obsolète'**__\n\n"
        "Pour te connecter au serveur **NationsGlory Alpha**, ton jeu doit être sur la **même version** que le serveur. "
        "Si tu as cette __erreur__ c'est que ton jeu n'est **pas sur la même version** que le serveur. "
        "Cela arrive __souvent__ lors d'une **mise à jour de Minecraft**. "
        "Il faut alors **attendre**, parfois __plusieurs jours__, que le serveur soit **mis à jour**.\n\n"
        "Si cela t'arrive, ne t'__inquiète pas__, il est **inutile de surcharger le staff** "
        "qui ne sera de toute façon pas en mesure de t'aider."
    ))
    c4.add_item(Separator())
    if _has(files, "version_obsolete.png"):
        c4.add_item(MediaGallery(MediaGalleryItem("attachment://version_obsolete.png")))
    c4.add_item(Separator())
    c4.add_item(TextDisplay(
        "2️⃣ __**Erreur : 'Liste blanche'**__\n\n"
        "Si tu reçois le **message d'erreur** t'expliquant que le serveur est en **liste blanche**, "
        "cela signifie que l'__accès au serveur__ est **restreint** temporairement. "
        "Ce système est déclenché lorsqu'un **problème technique prioritaire** est remonté. "
        "Son objectif est de __garantir__ la **meilleure expérience** de jeu pour les joueurs !\n\n"
        "Si cela t'arrive, il faut **patienter** et rester **informé** par les __canaux officiels de NationsGlory__."
    ))
    if _has(files, "wl.png"):
        c4.add_item(MediaGallery(MediaGalleryItem("attachment://wl.png")))
    c4.add_item(Separator())
    c4.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c4)

    return view


# ============================================================
# 🧭 Commande
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="nous_rejoindre", description="🚪 Envoie le tutoriel pour rejoindre le serveur Alpha")
async def nous_rejoindre(interaction: Interaction) -> None:

    # 🛡️ Ban bot
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Permission Modo+
    if not await check_modo_plus(interaction, "envoyer le tutoriel"):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande
    if not await verifier_commande(interaction, "alpha_nous_rejoindre"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "alpha_nous_rejoindre")

    # 💻 Récupération salon
    channel = interaction.client.get_channel(TARGET_CHANNEL_ID)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(TARGET_CHANNEL_ID)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon introuvable."),
                ephemeral=True,
            )

    # 🚀 Envoi
    fresh_files = _get_fresh_files()
    view = build_nous_rejoindre_view(fresh_files)
    kwargs: dict = {"view": view}
    if fresh_files:
        kwargs["files"] = fresh_files

    try:
        sent = await channel.send(**kwargs)
    except discord.HTTPException:
        log.exception("Erreur /alpha nous_rejoindre | guild=%s", interaction.guild_id)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue."),
            ephemeral=True,
        )

    # ➕ Réaction
    try:
        emoji = interaction.guild.get_emoji(EMOJI_TO_ADD)
        if emoji:
            await sent.add_reaction(emoji)
    except discord.HTTPException:
        log.warning("Impossible d'ajouter la réaction | guild=%s", interaction.guild_id)

    await interaction.followup.send(
        view=success_container(f"Tutoriel envoyé dans {channel.mention} !"),
        ephemeral=True,
    )


# ============================================================
# ❌ Erreurs
# ============================================================

@nous_rejoindre.error
async def nous_rejoindre_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)