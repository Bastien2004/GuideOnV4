"""
views/dev/join_serv_view.py — Vue de confirmation d'invitation créée,
extraite de cogs/dev/join_serv.py — même traitement que
views/dev/guild_info_view.py.

Reste en LayoutView simple, PAS BaseLayoutView : réponse éphémère one-shot
sans aucun composant interactif.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

# ============================================================
# 🧩 Construction de la vue
# ============================================================

def build_invite_view(guild: discord.Guild, invite: discord.Invite, channel: discord.TextChannel) -> LayoutView:
    """Construit la view d'invitation."""

    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# <:valider:1495444292867723284> Invitation créée"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"⇝ **Serveur :** {guild.name}\n"
        f"⇝ **ID :** `{guild.id}`\n"
        f"⇝ **Salon :** {channel.mention}\n"
        f"⇝ **Expire dans :** 24h\n"
        f"⇝ **Usages :** Illimités\n\n"
        f"**Lien :** {invite.url}"
    ))

    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)

    return view