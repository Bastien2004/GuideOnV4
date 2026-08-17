"""
utils/bienvenue_render.py — Création des messages de bienvenue/départ.
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
_IMG_RE = re.compile(r"^https?://.+\.(png|jpe?g|gif|webp)(\?.*)?$", re.IGNORECASE)
_CDN_HOSTS = ("cdn.discordapp.com", "media.discordapp.net", "imgur.com", "i.imgur.com")


# ============================================================
# 🔩 Fonctions utilitaires
# ============================================================

def is_valid_image_url(url: str) -> bool:
    """Valide une URL d'image."""
    if not url:
        return False
    if _IMG_RE.match(url):
        return True
    return url.startswith("https://") and any(h in url for h in _CDN_HOSTS)


def render_template(template: str, *, member: discord.Member, guild: discord.Guild) -> str:
    """Remplace les variables du template."""
    return (
        (template or "")
        .replace("{user}", member.display_name)
        .replace("{display_name}", member.display_name)
        .replace("{mention}", member.mention)
        .replace("{id}", str(member.id))
        .replace("{member_created_at}", member.created_at.strftime("%d/%m/%Y"))
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count or 0))
        .replace("{guild_created_at}", guild.created_at.strftime("%d/%m/%Y"))
    )


def resolve_image_url(guild_id: int, custom_url: str | None) -> str | None:
    """Renvoie l'URL le l'image personnalisée si le serveur est Gold+."""
    if custom_url and is_gold(guild_id):
        return custom_url
    return None


def build_bienvenue_embed(rendered: str, *, kind: str, custom_image_url: str | None = None) -> tuple[discord.Embed, discord.File | None]:
    """Construit la version embed d'arrivée/départ."""

    title = "👋 Bienvenue" if kind == "arrivee" else "👋 Au revoir"

    embed = discord.Embed(title=title, description=rendered or "_(message vide)_", color=_EMBED_COLOR)
    embed.set_footer(text="GuideOn Studio")

    file: discord.File | None = None
    if custom_image_url:
        embed.set_image(url=custom_image_url)
    elif os.path.exists(WELCOME_IMAGE_PATH):
        file = discord.File(WELCOME_IMAGE_PATH, filename=WELCOME_IMAGE_FILENAME)
        embed.set_image(url=f"attachment://{WELCOME_IMAGE_FILENAME}")

    return embed, file


def build_bienvenue_view(rendered: str, *, kind: str) -> LayoutView:
    """Construit la version container d'arrivée/départ."""

    title = "👋 Bienvenue" if kind == "arrivee" else "👋 Au revoir"

    view = LayoutView(timeout=None)
    container = Container()
    container.add_item(TextDisplay(f"# {title}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(rendered or "_(message vide)_"))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(container)
    return view