"""
views/mod/automod_antifullcaps_view.py — Config Anti Full Maj (v2).
Style compact autorole. Toggle + 2 réglages (min_length + ratio).
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_antifullcaps_manager as mgr
from utils.settings import settings
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MIN_LENGTH_MIN, MIN_LENGTH_MAX = 1, 500
RATIO_MIN_PCT, RATIO_MAX_PCT = 10, 100


async def create_automod_antifullcaps_view(
    guild_id: int, bot, author_id: Optional[int] = None,
) -> Optional[LayoutView]:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await mgr.load_config(guild_id)
    enabled = cfg.get("enabled", False)
    min_length = cfg.get("min_length", 10)
    ratio_pct = int(round(cfg.get("ratio_threshold", 0.7) * 100))

    view = LayoutView(timeout=600)
    c = Container()

    dot = "🟢" if enabled else "🔴"
    state = "Activé" if enabled else "Désactivé"
    c.add_item(TextDisplay(f"# 🔠 Anti Full Maj · {dot} {state}"))
    c.add_item(Separator())

    # Toggle
    toggle_btn = Button(
        label="✅ Activé" if enabled else "❌ Désactivé",
        style=ButtonStyle.success if enabled else ButtonStyle.danger,
    )
    toggle_btn.callback = _cb_toggle(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**🔘 Statut du système**\n"
            "-# Bloque les messages majoritairement en MAJUSCULES."
        ),
        accessory=toggle_btn,
    ))
    c.add_item(Separator())

    # Min length
    btn_min = Button(label="Modifier", style=ButtonStyle.secondary, emoji="✏️")
    btn_min.callback = _cb_edit_min(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**📏 Longueur minimale**\n"
            f"-# Ignore les messages de moins de **{min_length} caractères**.\n"
            f"-# Plage : {MIN_LENGTH_MIN} → {MIN_LENGTH_MAX}"
        ),
        accessory=btn_min,
    ))
    c.add_item(Separator())

    # Ratio
    btn_ratio = Button(label="Modifier", style=ButtonStyle.secondary, emoji="✏️")
    btn_ratio.callback = _cb_edit_ratio(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**📊 Seuil de déclenchement**\n"
            f"-# À partir de **{ratio_pct}%** de lettres en MAJUSCULES.\n"
            f"-# Plage : {RATIO_MIN_PCT}% → {RATIO_MAX_PCT}%"
        ),
        accessory=btn_ratio,
    ))
    c.add_item(Separator())

    # Back + doc
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
    new_view = await create_automod_antifullcaps_view(guild_id, bot, author_id)
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


def _cb_edit_min(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(inter):
        if not await check(inter):
            return
        async def submit(i, value):
            try:
                n = int(value.strip())
            except ValueError:
                await i.response.send_message(
                    view=warning_container("La valeur doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n < MIN_LENGTH_MIN or n > MIN_LENGTH_MAX:
                await i.response.send_message(
                    view=warning_container(
                        f"La longueur doit être entre **{MIN_LENGTH_MIN}** et **{MIN_LENGTH_MAX}**."
                    ),
                    ephemeral=True,
                )
                return
            await mgr.save_config(guild_id, min_length=n)
            await _rerender(i, guild_id, bot, author_id)

        current = (await mgr.load_config(guild_id)).get("min_length", 10)
        await inter.response.send_modal(TextModal(
            title="Longueur minimale", label="Nombre de caractères",
            placeholder="Ex : 10", default=str(current), required=True, max_length=4, on_submit=submit,
        ))
    return cb


def _cb_edit_ratio(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(inter):
        if not await check(inter):
            return
        async def submit(i, value):
            raw = value.strip().rstrip("%").strip()
            try:
                pct = int(raw)
            except ValueError:
                await i.response.send_message(
                    view=warning_container("La valeur doit être un **nombre entier** (pourcentage)."),
                    ephemeral=True,
                )
                return
            if pct < RATIO_MIN_PCT or pct > RATIO_MAX_PCT:
                await i.response.send_message(
                    view=warning_container(
                        f"Le pourcentage doit être entre **{RATIO_MIN_PCT}%** et **{RATIO_MAX_PCT}%**."
                    ),
                    ephemeral=True,
                )
                return
            await mgr.save_config(guild_id, ratio_threshold=pct / 100.0)
            await _rerender(i, guild_id, bot, author_id)

        current_pct = int(round((await mgr.load_config(guild_id)).get("ratio_threshold", 0.7) * 100))
        await inter.response.send_modal(TextModal(
            title="Seuil de déclenchement", label=f"Pourcentage ({RATIO_MIN_PCT} à {RATIO_MAX_PCT})",
            placeholder="Ex : 70", default=str(current_pct), required=True, max_length=4, on_submit=submit,
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