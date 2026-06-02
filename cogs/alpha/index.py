"""
cogs/alpha/index.py — Commande /alpha index.

Envoie (ou met à jour) le message d'index du serveur Alpha dans un salon cible.
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
from utils.managers.alpha_message_manager import get_alpha_message, upsert_alpha_message, clear_alpha_message

log = logging.getLogger(__name__)

# ============================================================
# 📁 Constantes
# ============================================================

TARGET_CHANNEL_ID = 1496770680874729573
MESSAGE_KEY       = "index"          # clé DB pour ce message

_IMAGES = [
    ("source/alpha_affiche.png",           "alpha_affiche.png"),
    ("source/tableau_sanction_alpha.png",  "tableau_sanction_alpha.png"),
    ("source/npc_alpha_all.png",           "npc_alpha_all.png"),
]


# ============================================================
# 🖼️ Helpers fichiers
# ============================================================

def _get_fresh_files() -> list[discord.File]:
    files = []
    for path, filename in _IMAGES:
        if os.path.exists(path):
            files.append(discord.File(path, filename=filename))
    return files


def _has(files: list[discord.File], name: str) -> bool:
    return any(f.filename == name for f in files)


# ============================================================
# 🧱 Containers — un par section
# ============================================================

def _c1_header(files: list[discord.File]) -> Container:
    c = Container()
    c.add_item(TextDisplay("# <:alpha:1496906799612428368> Index du Alpha"))
    c.add_item(Separator())
    if _has(files, "alpha_affiche.png"):
        c.add_item(MediaGallery(MediaGalleryItem("attachment://alpha_affiche.png")))
    return c


def _c2_reglement() -> Container:
    c = Container()
    c.add_item(TextDisplay("## 📖 __Règlement du Serveur__ :"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "● **Codex** de NationsGlory : [Cliquer ici](https://wiki.nationsglory.fr/fr/article/le-reglement-bedrock-codex-1ssj6k9/) 📖\n"
        "● **Règles internes** du Alpha : [Cliquer ici](https://wiki.nationsglory.fr/fr/article/le-reglement-bedrock-codex-1ssj6k9/) 🧾\n"
        "● **Sanctions** du Alpha : [Cliquer ici](https://wiki.nationsglory.fr/fr/article/le-reglement-bedrock-codex-1ssj6k9/) ⚖️\n"
    ))
    c.add_item(Separator())
    return c


def _c3_plateformes() -> Container:
    c = Container()
    c.add_item(TextDisplay("## 🎥 __Plateforme de NationsGlory__ :"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "● <:website:1490331146775560212> **Site Web** : [Visiter](https://nationsglory.fr).\n"
        "● <:Discord:1500400336739766302> Serveur **Discord** : [Rejoindre](https://discord.gg/nationsglory).\n"
        "● <:Youtube:1500400294243205210> Chaîne **Youtube** : [Visiter](https://www.youtube.com/@NationsGlory).\n"
        "● <:Twitch:1500400202195140618> Chaîne **Twitch** : [Visiter](https://www.twitch.tv/nationsgloryfr).\n"
        "● <:X_:1500400261502603387> Compte **X** : [Visiter](https://x.com/NationsGlory).\n"
        "● <:Instagram:1500400141272748082> Compte **Instagram** : [Visiter](https://www.instagram.com/nationsgloryfr/?hl=fr).\n"
        "● <:Tiktok:1500400096033112175> Compte **TikTok** : [Visiter](https://www.tiktok.com/@nationsgloryfr?lang=fr)"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "📱 N'hésite pas à __visiter__ nos **réseaux sociaux** pour rester __informé__ des **dernières actualités** !"
    ))
    return c


def _c4_recrutement() -> Container:
    c = Container()
    c.add_item(TextDisplay("## 🤝 __Recrutement du Alpha__ :"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "● <:Builder_2:1500406243955703848> La **Team Builder** → [Candidater](https://nationsglory.fr/forums/category/recrutement-builder.288).\n"
        "● <:Journaliste_2:1500406193724854302> La **Team Journal** → [Candidater](https://nationsglory.fr/forums/category/recrutement-builder.288).\n"
        "● <:Guide_2:1500406282631385158> L'**équipe des Guides** → [Candidater](https://nationsglory.fr/forums/category/recrutement-builder.288).\n"
        "● <:Modo_2:1500406266231783565> La **Modération** → [Candidater](https://nationsglory.fr/forums/category/recrutement-builder.288)."
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "N'hésitez pas à __rejoindre__ nos **équipes** ! Attention à la **qualité** de votre **candidature** !"
    ))
    return c


def _c5_discords() -> Container:
    c = Container()
    c.add_item(TextDisplay("## 🌐 __Nos Discords Communautaires__ :"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "**🌐 __Global__**\n"
        "- <:NationsGlory:1500414113384366261> NationsGlory : https://discord.gg/nationsglory\n"
        "- 📻 NG-Radio : https://discord.gg/cxMZqCNKvD\n"
        "- <:NG_US:1500414650909724834> NG US : https://discord.gg/QpA7XmEngG **(fermé)**\n\n"

        "**🎮 __Bedrock__**\n"
        "- <:Alpha:1500414179650048070> Alpha : https://discord.gg/KxC9E2VPeX\n"
        "- <:Sigma:1500414355773329548> Sigma : https://discord.gg/RcJeepJB2V\n"
        "- <:Omega:1500414132560723978> Oméga : https://discord.gg/cy48ux3Bk2\n"
        "- <:Delta:1500414247098650725> Delta : https://discord.gg/nationsglory-delta-948880111753625642\n"
        "- <:Epsilon:1500414274999418970> Epsilon : https://discord.gg/SAjHxuJTQY\n\n"

        "**💻 __Java__**\n"
        "- <:Blue:1500415616744685648> Blue : https://discord.gg/wQgpfTzAwp\n"
        "- <:Orange:1500414101493387354> Orange : https://discord.gg/HtET56bBQs\n"
        "- <:Yellow:1500414000859447408> Yellow : https://discord.gg/z8bBMnwTCW\n"
        "- <:White:1500414056710799380> White : https://discord.gg/bf6bNkt2SM\n"
        "- <:Black:1500415629621067826> Black : https://discord.gg/Ck9s96FDCe\n"
        "- <:Cyan:1500415587669643294> Cyan : https://discord.gg/RxAjxtuE2U\n"
        "- <:Lime:1500415534771212439> Lime : https://discord.gg/h54m7VqmWY\n"
        "- <:Coral:1500415601300996226> Coral : https://discord.gg/mZx4CdqngA\n"
        "- <:RED:1500410048273322035> Red : https://discord.gg/rYGPtgKkpt\n"
        "- <:Mocha:1500415522192228453> Mocha : https://discord.gg/zbTkjGFMZB\n"
        "- <:Jade:1500415549727838238> Jade : https://discord.gg/fphbKQSrH9"
    ))
    return c


def _c6_sanctions(files: list[discord.File]) -> Container:
    c = Container()
    c.add_item(TextDisplay("## ⚖️ __Tableau des Sanctions__ :"))
    c.add_item(Separator())
    if _has(files, "tableau_sanction_alpha.png"):
        c.add_item(MediaGallery(MediaGalleryItem("attachment://tableau_sanction_alpha.png")))
    return c


def _c7_npc(files: list[discord.File]) -> Container:
    c = Container()
    c.add_item(TextDisplay("## 👥 __NPCs du Alpha__ :"))
    c.add_item(Separator())
    if _has(files, "npc_alpha_all.png"):
        c.add_item(MediaGallery(MediaGalleryItem("attachment://npc_alpha_all.png")))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    return c


def build_index_view(files: list[discord.File]) -> LayoutView:
    view = LayoutView(timeout=None)
    for container in (
        _c1_header(files),
        _c2_reglement(),
        _c3_plateformes(),
        _c4_recrutement(),
        _c5_discords(),
        _c6_sanctions(files),
        _c7_npc(files),
    ):
        view.add_item(container)
    return view


# ============================================================
# 🧭 Commande
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="index", description="📋 Envoie ou met à jour l'index du serveur Alpha")
async def index(interaction: Interaction) -> None:

    # 🛡️ Ban bot
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Permission OP Alpha
    if not await check_op_alpha(interaction, "gérer l'index"):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande
    if not await verifier_commande(interaction, "alpha_index"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "alpha_index")

    guild_id = interaction.guild_id

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

    # 📄 Préparation contenu
    fresh_files = _get_fresh_files()
    view = build_index_view(fresh_files)

    # 🔍 Récupération message existant en DB
    existing_msg: discord.Message | None = None
    cfg = await get_alpha_message(guild_id, MESSAGE_KEY)

    if cfg and cfg.message_id:
        try:
            existing_msg = await channel.fetch_message(cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing_msg = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    # 🚀 Édition ou création
    try:
        if existing_msg:
            await existing_msg.edit(view=view, attachments=fresh_files)
            return await interaction.followup.send(
                view=success_container(f"Index mis à jour dans {channel.mention} !"),
                ephemeral=True,
            )

        # Création
        kwargs: dict = {"view": view}
        if fresh_files:
            kwargs["files"] = fresh_files

        sent = await channel.send(**kwargs)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, TARGET_CHANNEL_ID, sent.id)

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


# ============================================================
# ❌ Erreurs
# ============================================================

@index.error
async def index_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)