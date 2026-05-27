"""
Commande /ng serveur_stat — Statistiques des serveurs NationsGlory.
"""
from __future__ import annotations

import io
import json
import logging

import aiohttp
import discord
import matplotlib.pyplot as plt
from discord import app_commands, Interaction, ButtonStyle, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Separator, Section, Button, MediaGallery

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 1000

with open("config.json", "r", encoding="utf-8") as _f:
    _cfg = json.load(_f)
    API_KEY = _cfg.get("NG_API_KEY", "MISSING")

API_URL          = "https://publicapi.nationsglory.fr/playercount"
API_HEADERS      = {"accept": "application/json", "Authorization": f"Bearer {API_KEY}"}

SERVEURS_JAVA    = ["white", "red", "black", "mocha", "blue", "yellow", "orange", "lime", "coral", "cyan", "jade"]
SERVEURS_BEDROCK = ["alpha", "sigma", "omega", "delta", "epsilon"]
SERVEURS_EXCLUS  = {"hub", "hubbe", "java_hub", "bedrock_hub", "accueil", "dev5", "build"}

COULEURS_SERVEUR = {
    "white":   "#D8D9E1",
    "red":     "#F4264A",
    "black":   "#21212E",
    "mocha":   "#823D14",
    "blue":    "#3B49C2",
    "yellow":  "#F6C004",
    "orange":  "#FF922C",
    "lime":    "#7AC95F",
    "coral":   "#FC5C65",
    "cyan":    "#6EC0EE",
    "jade":    "#00BC7D",
    "alpha":   "#F4264A",
    "sigma":   "#21212E",
    "omega":   "#828294",
    "delta":   "#F6C004",
    "epsilon": "#3B49C2",
}

GRAPH_BG = "#23272a"


# ============================================================
# 🌐 API NationsGlory
# ============================================================

async def fetch_playercount() -> dict:
    """Récupère les stats de joueurs connectés via l'API NG."""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            API_URL,
            headers=API_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            r.raise_for_status()
            return await r.json()


# ============================================================
# 📦 Fonctions utilitaires
# ============================================================

def get_server_color(nom: str) -> str:
    return COULEURS_SERVEUR.get(nom.lower(), "#EF5DA8")


def parse_servers(data: dict) -> tuple[list[dict], list[dict]]:
    """Filtre et trie les serveurs Java et Bedrock depuis la réponse API."""
    java    = []
    bedrock = []

    for nom, info in data.items():
        if nom in SERVEURS_EXCLUS or not isinstance(info, dict) or "players" not in info:
            continue
        srv = {"server": nom, "players": info.get("players", 0), "online": info.get("online", False)}
        if nom in SERVEURS_JAVA:
            java.append(srv)
        elif nom in SERVEURS_BEDROCK:
            bedrock.append(srv)

    java.sort(key=lambda s: SERVEURS_JAVA.index(s["server"]))
    bedrock.sort(key=lambda s: SERVEURS_BEDROCK.index(s["server"]))

    return java, bedrock


def generate_graph(serveurs_java: list[dict], serveurs_bedrock: list[dict]) -> discord.File:
    """Génère le graphique en barres et retourne le fichier Discord."""
    all_srv  = serveurs_java + serveurs_bedrock
    noms     = [s["server"].capitalize() for s in all_srv]
    joueurs  = [s["players"] for s in all_srv]
    couleurs = [get_server_color(s["server"]) for s in all_srv]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(range(len(noms)), joueurs, color=couleurs, edgecolor="white", linewidth=0.8)

    fig.patch.set_facecolor(GRAPH_BG)
    ax.set_facecolor(GRAPH_BG)
    ax.tick_params(colors="white")
    ax.set_xticks(range(len(noms)))
    ax.set_xticklabels(noms, rotation=45, color="white", fontweight="bold")

    if serveurs_java and serveurs_bedrock:
        ax.axvline(x=len(serveurs_java) - 0.5, color="white", linestyle="--", alpha=0.6)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)

    return discord.File(buf, filename="stat_graph.png")


# ============================================================
# 🧩 Construction views
# ============================================================

def build_detail_view(serveurs_java: list[dict], serveurs_bedrock: list[dict]) -> LayoutView:
    """Construit la view de détail par serveur."""
    view      = LayoutView(timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay("# <:lister:1495445288364675192> Détails des Serveurs"))
    container.add_item(Separator())

    if serveurs_java:
        txt_java = "**💻 JAVA**\n"
        for s in serveurs_java:
            statut    = "🟢" if s["online"] else "🔴"
            txt_java += f"- {statut} **{s['server'].capitalize()}** : `{s['players']}` joueurs\n"
        container.add_item(TextDisplay(txt_java))

    container.add_item(Separator())

    if serveurs_bedrock:
        txt_bed = "**🎮 BEDROCK**\n"
        for s in serveurs_bedrock:
            statut   = "🟢" if s["online"] else "🔴"
            txt_bed += f"- {statut} **{s['server'].capitalize()}** : `{s['players']}` joueurs\n"
        container.add_item(TextDisplay(txt_bed))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(container)

    return view


def build_stat_view(
    serveurs_java: list[dict],
    serveurs_bedrock: list[dict],
) -> tuple[LayoutView, discord.File]:
    """Construit la view principale avec le graphique."""
    total_java    = sum(s["players"] for s in serveurs_java)
    total_bedrock = sum(s["players"] for s in serveurs_bedrock)
    file          = generate_graph(serveurs_java, serveurs_bedrock)

    view      = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# <:logo_nationglory:1495443853686079488> Statistiques NationsGlory"))
    container.add_item(TextDisplay(
        f"__**Statistiques globales**__ :\n"
        f"💻 Java : `{total_java}`  •  🎮 Bedrock : `{total_bedrock}`\n"
        f"➡️ Total : **`{total_java + total_bedrock}`**"
    ))
    container.add_item(Separator())
    container.add_item(MediaGallery(MediaGalleryItem("attachment://stat_graph.png")))
    container.add_item(Separator())

    detail_btn = Button(
        label="Liste détaillée",
        style=ButtonStyle.secondary,
        emoji="<:lister:1495445288364675192>",
    )

    async def detail_callback(inter: Interaction) -> None:
        detail_view = build_detail_view(serveurs_java, serveurs_bedrock)
        await inter.response.send_message(view=detail_view, ephemeral=True)

    detail_btn.callback = detail_callback

    container.add_item(Section(
        TextDisplay("**Détails par serveur**\n-# Voir l'état de chaque serveur."),
        accessory=detail_btn,
    ))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(container)

    return view, file


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="serveur_stat", description="📊 Statistiques des serveurs NationsGlory")
async def serveur_stat(interaction: Interaction):

    # 🛡️ Vérification ban
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification activation
    if not await verifier_commande(interaction, "ng_serveur_stat"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "ng_serveur_stat")

    # 📦 Récupération + construction view
    try:
        data                       = await fetch_playercount()
        serveurs_java, serveurs_bedrock = parse_servers(data)
        view, file                 = build_stat_view(serveurs_java, serveurs_bedrock)

        await interaction.followup.send(file=file, view=view)

    except Exception:
        log.exception("Erreur commande /ng serveur_stat")
        await interaction.followup.send(
            view=error_container("Une erreur est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@serveur_stat.error
async def serveur_stat_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)