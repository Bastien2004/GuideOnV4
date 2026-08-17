"""
views/mod/automod_antispam_emoji_view.py — Config Anti Spam Emoji (v2).
Style compact autorole. Toggle + max_emoji.
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_antispam_emoji_manager as mgr
from utils.settings import settings
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_MIN, MAX_MAX = 1, 100


async def create_automod_antispam_emoji_view(
    guild_id: int, bot, author_id: Optional[int] = None,
) -> Optional[LayoutView]:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await mgr.load_config(guild_id)
    enabled = cfg.get("enabled", False)
    max_emoji = cfg.get("max_emoji", 10)

    view = LayoutView(timeout=600)
    c = Container()

    dot = "🟢" if enabled else "🔴"
    state = "Activé" if enabled else "Désactivé"
    c.add_item(TextDisplay(f"# 😀 Anti Spam Emoji · {dot} {state}"))
    c.add_item(Separator())

    toggle_btn = Button(
        label="✅ Activé" if enabled else "❌ Désactivé",
        style=ButtonStyle.success if enabled else ButtonStyle.danger,
    )
    toggle_btn.callback = _cb_toggle(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**🔘 Statut du système**\n"
            "-# Limite le nombre d'emojis (Unicode + custom Discord) par message."
        ),
        accessory=toggle_btn,
    ))
    c.add_item(Separator())

    btn_max = Button(label="Modifier", style=ButtonStyle.secondary, emoji="✏️")
    btn_max.callback = _cb_edit_max(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**📊 Seuil de déclenchement**\n"
            f"-# Un message avec plus de **{max_emoji} emojis** est bloqué.\n"
            f"-# Plage : {MAX_MIN} → {MAX_MAX}"
        ),
        accessory=btn_max,
    ))
    c.add_item(Separator())

    btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="↩️")
    btn_back.callback = _cb_back(guild_id, bot, author_id)
    c.add_item(ActionRow(
        btn_back,
        Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚"),
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view


def _guard(author_id: Optional[int]):
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** peut utiliser ce menu."), ephemeral=True,
            )
            return False
        m = interaction.user
        if not isinstance(m, discord.Member) or not m.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur**."), ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction, guild_id, bot, author_id):
    new_view = await create_automod_antispam_emoji_view(guild_id, bot, author_id)
    if new_view is None:
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_toggle(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(inter):
        if not await check(inter):
            return
        current = (await mgr.load_config(guild_id)).get("enabled", False)
        await mgr.set_enabled(guild_id, not current)
        await _rerender(inter, guild_id, bot, author_id)
    return cb


def _cb_edit_max(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(inter):
        if not await check(inter):
            return
        async def submit(i, value):
            try:
                n = int(value.strip())
            except ValueError:
                await i.response.send_message(
                    view=warning_container("La valeur doit être un **nombre entier**."), ephemeral=True,
                )
                return
            if n < MAX_MIN or n > MAX_MAX:
                await i.response.send_message(
                    view=warning_container(f"La valeur doit être entre **{MAX_MIN}** et **{MAX_MAX}**."),
                    ephemeral=True,
                )
                return
            await mgr.save_config(guild_id, max_emoji=n)
            await _rerender(i, guild_id, bot, author_id)

        current = (await mgr.load_config(guild_id)).get("max_emoji", 10)
        await inter.response.send_modal(TextModal(
            title="Nombre max d'emojis", label="Nombre max autorisé", placeholder="Ex : 10",
            default=str(current), required=True, max_length=3, on_submit=submit,
        ))
    return cb


def _cb_back(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(inter):
        if not await check(inter):
            return
        from views.mod.automod_dashboard_view import create_automod_dashboard_view
        new_view = await create_automod_dashboard_view(guild_id, bot, author_id)
        if new_view is None:
            return
        await inter.response.edit_message(view=new_view)
    return cb