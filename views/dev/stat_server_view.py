from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

GUILDS_PER_PAGE = 10


def build_stat_server_view(bot: discord.Client, page: int = 0) -> LayoutView:
    guilds = sorted(bot.guilds, key=lambda g: g.member_count or 0, reverse=True)

    total_guilds = len(guilds)
    total_members = sum(g.member_count or 0 for g in guilds)
    total_text_channels = sum(len(g.text_channels) for g in guilds)
    total_voice_channels = sum(len(g.voice_channels) for g in guilds)

    total_pages = max(1, (total_guilds + GUILDS_PER_PAGE - 1) // GUILDS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * GUILDS_PER_PAGE
    current = guilds[start : start + GUILDS_PER_PAGE]

    view = LayoutView(timeout=180)

    # ── Header : stats globales ──────────────────────────────
    c_header = Container()
    c_header.add_item(TextDisplay("# 📊 Statistiques GuideOn"))
    c_header.add_item(Separator())
    c_header.add_item(TextDisplay(
        f"**🌐 Serveurs :** `{total_guilds}`\n"
        f"**👥 Membres (cumulés) :** `{total_members}`\n"
        f"**💬 Salons texte :** `{total_text_channels}`\n"
        f"**🔊 Salons vocaux :** `{total_voice_channels}`"
    ))
    view.add_item(c_header)

    # ── Liste des serveurs ────────────────────────────────────
    c_list = Container()
    c_list.add_item(TextDisplay("## 🗂️ Liste des serveurs"))
    c_list.add_item(Separator())

    if not current:
        c_list.add_item(TextDisplay("*Aucun serveur.*"))
    else:
        lines = []
        for g in current:
            owner = f"<@{g.owner_id}>" if g.owner_id else "*Inconnu*"
            lines.append(
                f"**{g.name}**\n"
                f"-# ID : `{g.id}` · 👥 `{g.member_count}` · Owner : {owner}"
            )
        c_list.add_item(TextDisplay("\n\n".join(lines)))

    c_list.add_item(Separator())
    c_list.add_item(TextDisplay(f"-# Page {page + 1} / {total_pages}"))

    # ── Navigation ─────────────────────────────────────────────
    btn_prev = Button(emoji="◀️", style=ButtonStyle.secondary, custom_id="ss_prev", disabled=(page <= 0))
    btn_next = Button(emoji="▶️", style=ButtonStyle.secondary, custom_id="ss_next", disabled=(page >= total_pages - 1))

    async def prev_cb(interaction: Interaction) -> None:
        await interaction.response.edit_message(view=build_stat_server_view(interaction.client, page - 1))

    async def next_cb(interaction: Interaction) -> None:
        await interaction.response.edit_message(view=build_stat_server_view(interaction.client, page + 1))

    btn_prev.callback = prev_cb
    btn_next.callback = next_cb

    c_list.add_item(ActionRow(btn_prev, btn_next))
    c_list.add_item(Separator())
    c_list.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c_list)

    return view