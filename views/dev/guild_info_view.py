"""
views/dev/guild_info_view.py — Vue d'informations serveur, extraite de
cogs/dev/guild_info.py — même traitement que views/dev/debug_cmd_view.py.

Reste en LayoutView simple, PAS BaseLayoutView : réponse éphémère one-shot
sans aucun composant interactif.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.guild_info import GuildInfoData


def _check(ok: bool) -> str:
    return "✓" if ok else "✗"


# ============================================================
# 🧩 Construction de la vue
# ============================================================

def build_guild_info_view(guild: discord.Guild, info: GuildInfoData) -> LayoutView:
    """Construction de la view."""
    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# 🏠 Informations Serveur"))
    c.add_item(Separator())

    owner_mention = f"<@{guild.owner_id}>" if guild.owner_id else "*Inconnu*"

    c.add_item(TextDisplay(
        f"**Nom :**\n{guild.name}\n\n"
        f"**ID :**\n`{guild.id}`\n\n"
        f"**Propriétaire :**\n{owner_mention}\n\n"
        f"**Membres :**\n{guild.member_count or 0}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Créé :**\n{discord.utils.format_dt(guild.created_at, style='D')}\n\n"
        f"**Ajout du bot :**\n{info.bot_joined_at}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Salons :**\n{len(guild.channels)}\n\n"
        f"**Rôles :**\n{len(guild.roles)}\n\n"
        f"**Boost :**\nNiveau {guild.premium_tier} ({guild.premium_subscription_count} boosts)"
    ))
    c.add_item(Separator())

    modules_lines = "\n".join(f"{_check(v)} {name}" for name, v in info.modules.items())
    c.add_item(TextDisplay(f"**Modules :**\n{modules_lines}"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Bot Permissions :**\n{info.bot_perms_label}\n\n"
        f"**Shard :**\n{guild.shard_id if guild.shard_id is not None else 0}"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view