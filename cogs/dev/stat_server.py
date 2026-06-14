"""
cogs/dev/stat_server.py — /dev stat_server

Affiche les statistiques globales du bot (nb serveurs, membres, salons) et
la liste paginée de tous les serveurs où GuideOn est présent (nom + ID).

Accessible : DEV uniquement.
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, app_commands, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

log = logging.getLogger(__name__)

GUILDS_PER_PAGE = 10


# ════════════════════════════════════════════════════════════
# 🧱 Vue
# ════════════════════════════════════════════════════════════

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


# ════════════════════════════════════════════════════════════
# 🧭 Commande
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="stat_server", description="📊 [DEV] Affiche les statistiques et la liste des serveurs")
async def stat_server(interaction: Interaction) -> None:

    if not await check_dev(interaction, "consulter les statistiques serveurs"):
        return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "dev_stat_server"):
        return
    await tracker_commande(interaction, "dev_stat_server")

    await interaction.followup.send(
        view=build_stat_server_view(interaction.client, page=0),
        ephemeral=True,
    )


@stat_server.error
async def stat_server_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)