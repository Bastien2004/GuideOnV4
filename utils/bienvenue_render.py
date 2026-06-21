"""
utils/bienvenue_render.py — Rendu des templates de message bienvenue/départ.

Partagé entre views/bienvenue/config_view.py (aperçu avec guild.me comme
membre fictif) et cogs/events/bienvenue_listener.py (rendu réel avec le
membre qui vient d'arriver/partir) — un seul point de vérité pour les
variables supportées, pour que l'aperçu en config corresponde exactement
au message réellement envoyé.

Variables supportées :
    {user}          — nom d'affichage du membre
    {mention}        — mention du membre
    {server}         — nom du serveur
    {member_count}   — nombre de membres du serveur

⚠️ EXCEPTION CONVENTION ZÉRO-EMBED : build_bienvenue_embed() ci-dessous
utilise délibérément discord.Embed (et non Components V2), sur demande
explicite pour le système bienvenue/départ UNIQUEMENT — décision prise le
20/06/2026, ne pas reproduire ce pattern ailleurs dans le projet sans
validation explicite. Le reste du bot reste 100% Components V2.
"""
from __future__ import annotations

import os

import discord

WELCOME_IMAGE_PATH = os.path.join("source", "bvn_bot.webp")
WELCOME_IMAGE_FILENAME = "bvn_bot.webp"

_EMBED_COLOR = discord.Color.blurple()


def render_template(template: str, *, member: discord.Member, guild: discord.Guild) -> str:
    """Remplace les variables du template par les valeurs réelles de member/guild."""
    return (
        (template or "")
        .replace("{user}", member.display_name)
        .replace("{mention}", member.mention)
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count or 0))
    )


def build_bienvenue_embed(rendered: str, *, kind: str) -> tuple[discord.Embed, discord.File | None]:
    """
    Construit l'embed bienvenue/départ (style banner + footer), ainsi que
    le discord.File de la bannière à joindre (None si l'image est absente
    du disque — l'embed reste valide sans image dans ce cas).

    kind : "arrivee" ou "depart" — change uniquement le titre affiché.
    """
    title = "👋 Bienvenue" if kind == "arrivee" else "👋 Au revoir"

    embed = discord.Embed(
        title=title,
        description=rendered or "_(message vide)_",
        color=_EMBED_COLOR,
    )
    embed.set_footer(text="GuideON Studio")

    file: discord.File | None = None
    if os.path.exists(WELCOME_IMAGE_PATH):
        file = discord.File(WELCOME_IMAGE_PATH, filename=WELCOME_IMAGE_FILENAME)
        embed.set_image(url=f"attachment://{WELCOME_IMAGE_FILENAME}")

    return embed, file