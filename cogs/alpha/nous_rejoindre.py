"""
cogs/alpha/nous_rejoindre.py — Gestion de l'interface nous_rejoindre.
"""

from __future__ import annotations

import logging
import os

import discord
from discord import app_commands, Interaction, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery, ActionRow

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.perm_alpha import check_op_alpha

from utils.managers.alpha_rank_config_manager import load_rank_config
from utils.managers.alpha_message_manager import get_alpha_message, upsert_alpha_message, clear_alpha_message

log = logging.getLogger(__name__)

MESSAGE_KEY = "nous_rejoindre"


# ============================================================
# 📁  Fonctions utilitaires
# ============================================================

_IMAGES = [
    ("source/join_alpha.webp",        "join_alpha.webp"),
    ("source/version_obsolete.webp",  "version_obsolete.webp"),
    ("source/wl.webp",                "wl.webp"),
]


def _get_fresh_files() -> list[discord.File]:
    return [
        discord.File(path, filename=fn)
        for path, fn in _IMAGES if os.path.exists(path)
    ]


def _has(files: list[discord.File], name: str) -> bool:
    return any(f.filename == name for f in files)


def build_nous_rejoindre_view(files: list[discord.File], role_to_ping: int | None) -> LayoutView:
    ping_str = f" | <@&{role_to_ping}>" if role_to_ping else ""
    view = LayoutView(timeout=None)

    c1 = Container()
    c1.add_item(TextDisplay(f"# <:alpha:1496906799612428368> Nous rejoindre — Serveur Alpha{ping_str}"))
    c1.add_item(Separator())

    c1.add_item(TextDisplay(
        "## 🎮 Bienvenue sur NationsGlory Alpha\n\n"
        "Voici un guide simple pour **rejoindre** le serveur __Alpha NationsGlory Bedrock__.\n"
        "Lis attentivement chaque étape pour éviter les erreurs. 📒"
    ))
    c1.add_item(Separator())

    if _has(files, "join_alpha.webp"):
        c1.add_item(MediaGallery(MediaGalleryItem("attachment://join_alpha.webp")))
    view.add_item(c1)

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

    if _has(files, "version_obsolete.webp"):
        c4.add_item(MediaGallery(MediaGalleryItem("attachment://version_obsolete.webp")))
    c4.add_item(Separator())

    c4.add_item(TextDisplay(
        "2️⃣ __**Erreur : 'Liste blanche'**__\n\n"
        "Si tu reçois le **message d'erreur** t'expliquant que le serveur est en **liste blanche**, "
        "cela signifie que l'__accès au serveur__ est **restreint** temporairement. "
        "Ce système est déclenché lorsqu'un **problème technique prioritaire** est remonté. "
        "Son objectif est de __garantir__ la **meilleure expérience** de jeu pour les joueurs !\n\n"
        "Si cela t'arrive, il faut **patienter** et rester **informé** par les __canaux officiels de NationsGlory__."
    ))

    if _has(files, "wl.webp"):
        c4.add_item(MediaGallery(MediaGalleryItem("attachment://wl.webp")))
    c4.add_item(Separator())

    c4.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c4)

    return view


# ============================================================
# 🚪 Commande : /alpha nous_rejoindre
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 20)
@app_commands.command(name="nous_rejoindre", description="🚪 [OP] Envoi ou mise à jour du tutoriel pour rejoindre le serveur Alpha")
async def nous_rejoindre(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Vérification Opérateur.
    if not await check_op_alpha(interaction, "envoyer le tutoriel"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_nous_rejoindre"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_nous_rejoindre")

    # 🧩 Récupération de la configuration.
    cfg = await load_rank_config(interaction.guild_id)
    channel_id  = cfg.get("content_nous_rejoindre_channel_id")
    ping_id     = cfg.get("content_nous_rejoindre_ping_id")
    emoji_str   = cfg.get("content_nous_rejoindre_emoji")

    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Le salon n'est pas **configuré**.\n"
                "Utilisez `/dev config_alpha` pour le définir."
            ),
            ephemeral=True,
        )

    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon **introuvable** (ID invalide ou bot sans accès)."),
                ephemeral=True,
            )

    fresh_files = _get_fresh_files()
    view = build_nous_rejoindre_view(fresh_files, ping_id)
    kwargs: dict = {"view": view}
    if fresh_files:
        kwargs["files"] = fresh_files

    guild_id = interaction.guild_id

    # 🔍 Message existant en DB ?
    msg_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    existing: discord.Message | None = None
    if msg_cfg and msg_cfg.message_id:
        try:
            existing = await channel.fetch_message(msg_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    try:
        if existing:
            await existing.edit(view=view, attachments=fresh_files)
            return await interaction.followup.send(
                view=success_container(f"**Tutoriel** mis à jour dans {channel.mention} !"),
                ephemeral=True,
            )

        sent = await channel.send(**kwargs)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)

        if emoji_str:
            try:
                await sent.add_reaction(emoji_str)
            except discord.HTTPException:
                log.warning("[NOUS REJOINDRE ALPHA] Impossible d'ajouter la réaction | guild=%s", guild_id)

        return await interaction.followup.send(
            view=success_container(f"**Tutoriel** envoyé dans {channel.mention} !"),
            ephemeral=True,
        )

    except discord.HTTPException:
        log.exception("[NOUS REJOINDRE ALPHA] Erreur | guild=%s", guild_id)
        
        return await interaction.followup.send(
            view=error_container("Une **erreur** Discord est survenue lors de l'envoi."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@nous_rejoindre.error
async def nous_rejoindre_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)