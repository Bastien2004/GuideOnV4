"""
cogs/alpha/index.py — Commande /alpha index.

Envoie (ou met à jour) le message d'index du serveur Alpha.
Le salon et l'emoji sont chargés depuis AlphaRankConfig (configurable via /dev config_alpha).
Le message_id est persisté en DB via AlphaMessageConfig pour permettre l'édition.
Réservé aux OP Alpha et supérieurs.
"""
from __future__ import annotations

import logging
import os

import discord
from discord import app_commands, Interaction, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_alpha import check_op_alpha
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.managers.alpha_rank_config_manager import load_rank_config
from utils.managers.alpha_message_manager import (
    get_alpha_message, upsert_alpha_message, clear_alpha_message,
)

log = logging.getLogger(__name__)

MESSAGE_KEY = "index"

_IMAGES = [
    ("source/alpha_affiche.png",          "alpha_affiche.png"),
    ("source/tableau_sanction_alpha.png",  "tableau_sanction_alpha.png"),
    ("source/npc_alpha_all.png",           "npc_alpha_all.png"),
]


def _get_fresh_files() -> list[discord.File]:
    return [
        discord.File(path, filename=fn)
        for path, fn in _IMAGES if os.path.exists(path)
    ]


def _has(files: list[discord.File], name: str) -> bool:
    return any(f.filename == name for f in files)


def build_index_view(files: list[discord.File]) -> LayoutView:
    view = LayoutView(timeout=None)

    c1 = Container()
    c1.add_item(TextDisplay("# <:alpha:1496906799612428368> Index du Alpha"))
    c1.add_item(Separator())
    if _has(files, "alpha_affiche.png"):
        c1.add_item(MediaGallery(MediaGalleryItem("attachment://alpha_affiche.png")))
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
        "📱 N'hésite pas à __visiter__ nos **réseaux sociaux** pour rester __informé__ des **dernières actualités** !"
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
        "- 📻 NG-Radio : https://discord.gg/cxMZqCNKvD\n\n"
        "**🎮 __Bedrock__**\n"
        "- <:Alpha:1500414179650048070> Alpha : https://discord.gg/KxC9E2VPeX\n"
        "- <:Sigma:1500414355773329548> Sigma : https://discord.gg/RcJeepJB2V\n"
        "- <:Omega:1500414132560723978> Oméga : https://discord.gg/cy48ux3Bk2\n\n"
        "**💻 __Java__**\n"
        "- <:Blue:1500415616744685648> Blue : https://discord.gg/wQgpfTzAwp\n"
        "- <:Orange:1500414101493387354> Orange : https://discord.gg/HtET56bBQs\n"
        "- <:Yellow:1500414000859447408> Yellow : https://discord.gg/z8bBMnwTCW"
    ))
    view.add_item(c5)

    c6 = Container()
    c6.add_item(TextDisplay("## ⚖️ __Tableau des Sanctions__ :"))
    c6.add_item(Separator())
    if _has(files, "tableau_sanction_alpha.png"):
        c6.add_item(MediaGallery(MediaGalleryItem("attachment://tableau_sanction_alpha.png")))
    view.add_item(c6)

    c7 = Container()
    c7.add_item(TextDisplay("## 👥 __NPCs du Alpha__ :"))
    c7.add_item(Separator())
    if _has(files, "npc_alpha_all.png"):
        c7.add_item(MediaGallery(MediaGalleryItem("attachment://npc_alpha_all.png")))
    c7.add_item(Separator())
    c7.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c7)

    return view


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="index", description="📋 Envoie ou met à jour l'index du serveur Alpha")
async def index(interaction: Interaction) -> None:

    if not await verifier_ban_utilisateur(interaction):
        return
    if not await check_op_alpha(interaction, "gérer l'index"):
        return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "alpha_index"):
        return
    await tracker_commande(interaction, "alpha_index")

    # 📋 Config
    cfg = await load_rank_config(interaction.guild_id)
    channel_id = cfg.get("content_index_channel_id")
    emoji_id   = cfg.get("content_index_emoji_id")
    guild_id   = interaction.guild_id

    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Le salon n'est pas configuré.\n"
                "Utilisez `/dev config_alpha` → **Contenu Discord** pour le définir."
            ),
            ephemeral=True,
        )

    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon introuvable (ID invalide ou bot sans accès)."),
                ephemeral=True,
            )

    fresh_files = _get_fresh_files()
    view = build_index_view(fresh_files)

    # Message existant en DB ?
    existing_msg: discord.Message | None = None
    db_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    if db_cfg and db_cfg.message_id:
        try:
            existing_msg = await channel.fetch_message(db_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing_msg = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    try:
        if existing_msg:
            await existing_msg.edit(view=view, attachments=fresh_files)
            return await interaction.followup.send(
                view=success_container(f"Index mis à jour dans {channel.mention} !"),
                ephemeral=True,
            )

        kwargs: dict = {"view": view}
        if fresh_files:
            kwargs["files"] = fresh_files
        sent = await channel.send(**kwargs)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)

        # Réaction emoji
        if emoji_id:
            try:
                emoji = interaction.guild.get_emoji(emoji_id)
                if emoji:
                    await sent.add_reaction(emoji)
            except discord.HTTPException:
                log.warning("Impossible d'ajouter la réaction | guild=%s", guild_id)

        return await interaction.followup.send(
            view=success_container(f"Index créé dans {channel.mention} !"),
            ephemeral=True,
        )

    except discord.HTTPException:
        log.exception("Erreur /alpha index | guild=%s", guild_id)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue."),
            ephemeral=True,
        )


@index.error
async def index_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)