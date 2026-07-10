"""
utils/bienvenue_render.py — Gestion du rendu des templates de message bienvenue/départ.

Variables supportées :
    {user}          — nom d'affichage du membre
    {mention}        — mention du membre
    {server}         — nom du serveur
    {member_count}   — nombre de membres du serveur

⚠️ EXCEPTION CONVENTION ZÉRO-EMBED : build_bienvenue_embed() ci-dessous
utilise délibérément discord.Embed (et non Components V2), sur demande
explicite pour le système bienvenue/départ UNIQUEMENT — décision prise le
20/06/2026, ne pas reproduire ce pattern ailleurs dans le projet sans
validation explicite. Le format "texte" (build_bienvenue_view) reste lui
100% Components V2, conforme à la convention par défaut du reste du bot.

Image personnalisée (Gold+) :
    resolve_image_url(guild_id, custom_url) est LE point de vérité pour la
    dégradation Gold+ → défaut. Elle ne vérifie jamais la DB elle-même
    (is_gold() lit un cache sync, TTL 60s) : un serveur qui perd Gold+ voit
    son image personnalisée automatiquement ignorée au prochain envoi, sans
    tâche de fond ni purge — la valeur reste stockée en DB si le serveur se
    réabonne. Voir utils.boutique.gold_manager.is_gold.
"""
from __future__ import annotations

import os
import re

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.boutique.gold_manager import is_gold

WELCOME_IMAGE_PATH = os.path.join("source", "bvn_bot.webp")
WELCOME_IMAGE_FILENAME = "bvn_bot.webp"

_EMBED_COLOR = discord.Color.blurple()

# Validation d'URL d'image — même règle que views/report/config_view.py
# (http/https + extension image courante, ou CDN Discord/Imgur connu).
_IMG_RE = re.compile(r"^https?://.+\.(png|jpe?g|gif|webp)(\?.*)?$", re.IGNORECASE)
_CDN_HOSTS = ("cdn.discordapp.com", "media.discordapp.net", "imgur.com", "i.imgur.com")


def is_valid_image_url(url: str) -> bool:
    """Valide une URL d'image (utilisée pour l'image personnalisée Gold+)."""
    if not url:
        return False
    if _IMG_RE.match(url):
        return True
    return url.startswith("https://") and any(h in url for h in _CDN_HOSTS)


def render_template(template: str, *, member: discord.Member, guild: discord.Guild) -> str:
    """Remplace les variables du template par les valeurs réelles de member/guild."""
    return (
        (template or "")
        .replace("{user}", member.display_name)
        .replace("{mention}", member.mention)
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count or 0))
    )


def resolve_image_url(guild_id: int, custom_url: str | None) -> str | None:
    """
    Renvoie l'URL personnalisée si le serveur est actuellement Gold+,
    sinon None (le builder retombe alors sur la bannière par défaut).
    Ne touche jamais à la valeur stockée en DB.
    """
    if custom_url and is_gold(guild_id):
        return custom_url
    return None


def build_bienvenue_embed(
    rendered: str, *, kind: str, custom_image_url: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    """
    Construit l'embed bienvenue/départ (style banner + footer), ainsi que
    le discord.File de la bannière par défaut à joindre (None si l'image
    est absente du disque, ou si une image personnalisée est utilisée à
    la place — dans ce cas embed.set_image pointe directement vers l'URL,
    pas de pièce jointe nécessaire).

    kind : "arrivee" ou "depart" — change uniquement le titre affiché.
    custom_image_url : URL déjà résolue via resolve_image_url() — l'appelant
    est responsable de la dégradation Gold+, cette fonction se contente de
    l'utiliser si fournie.
    """
    title = "👋 Bienvenue" if kind == "arrivee" else "👋 Au revoir"

    embed = discord.Embed(
        title=title,
        description=rendered or "_(message vide)_",
        color=_EMBED_COLOR,
    )
    embed.set_footer(text="GuideON Studio")

    file: discord.File | None = None
    if custom_image_url:
        embed.set_image(url=custom_image_url)
    elif os.path.exists(WELCOME_IMAGE_PATH):
        file = discord.File(WELCOME_IMAGE_PATH, filename=WELCOME_IMAGE_FILENAME)
        embed.set_image(url=f"attachment://{WELCOME_IMAGE_FILENAME}")

    return embed, file


def build_bienvenue_view(rendered: str, *, kind: str) -> LayoutView:
    """
    Construit la version Components V2 ("texte brut") du message
    bienvenue/départ — même contenu que build_bienvenue_embed, sans image
    (l'image personnalisée est une fonctionnalité liée au format embed
    uniquement, cf. demande produit).
    """
    title = "👋 Bienvenue" if kind == "arrivee" else "👋 Au revoir"

    view = LayoutView(timeout=None)
    container = Container()
    container.add_item(TextDisplay(f"# {title}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(rendered or "_(message vide)_"))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideON Studio"))
    view.add_item(container)
    return view