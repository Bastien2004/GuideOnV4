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
"""
from __future__ import annotations

import discord


def render_template(template: str, *, member: discord.Member, guild: discord.Guild) -> str:
    """Remplace les variables du template par les valeurs réelles de member/guild."""
    return (
        (template or "")
        .replace("{user}", member.display_name)
        .replace("{mention}", member.mention)
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count or 0))
    )