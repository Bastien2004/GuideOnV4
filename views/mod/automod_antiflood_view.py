"""
views/mod/automod_antiflood_view.py — Interface de configuration du système Anti Flood.

Même structure qu'automod_antifullcaps_view.py : toggle + deux paramètres
numériques modifiables via TextModal (longueur minimale analysée, ratio
minimum de voyelles).
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_antiflood_manager as mgr
from utils.settings import settings
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MIN_LENGTH_MIN, MIN_LENGTH_MAX = 5, 500
RATIO_MIN_PCT, RATIO_MAX_PCT = 5, 60


# ============================================================
# 🧩 Construction de la view
# ============================================================

async def create_automod_antiflood_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[LayoutView]:
    """Construction de la view de configuration Anti Flood."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await mgr.load_config(guild_id)
    enabled = cfg.get("enabled", False)
    min_length = cfg.get("min_length", 20)
    ratio_pct = int(round(cfg.get("min_vowel_ratio", 0.2) * 100))

    view = LayoutView(timeout=600)
    c = Container()

    c.add_item(TextDisplay("# <:protect_config:1539608365704028340> Système anti flood"))
    c.add_item(Separator())

    # Toggle activation
    toggle_btn = Button(
        label="Activé" if enabled else "Désactivé",
        emoji="<:valider:1495444292867723284>" if enabled else "<:annuler:1495444256754761979>",
        style=ButtonStyle.success if enabled else ButtonStyle.danger,
        custom_id=f"toggle_{guild_id}"
    )
    toggle_btn.callback = _cb_toggle(guild_id, bot, author_id)

    c.add_item(Section(
        TextDisplay(
            "**🔘 Statut du système**\n"
            "-# Supprime les messages incohérents."
        ),
        accessory=toggle_btn,
    ))
    c.add_item(Separator())

    # Longueur minimum analysée
    btn_min = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_min.callback = _cb_edit_min(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**📏 Longueur minimale analysée**\n"
            f"-# Ignore les messages de moins de `{min_length}` lettres."
        ),
        accessory=btn_min,
    ))
    c.add_item(Separator())

    # Ratio minimum de voyelles
    btn_ratio = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_ratio.callback = _cb_edit_ratio(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**📊 Ratio minimum de voyelles**\n"
            f"-# En-dessous de `{ratio_pct}%` de voyelles, le message est bloqué."
        ),
        accessory=btn_ratio,
    ))
    c.add_item(Separator())

    # Back + doc
    btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
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
    new_view = await create_automod_antiflood_view(guild_id, bot, author_id)
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

        current = (await mgr.load_config(guild_id)).get("min_length", 20)
        await inter.response.send_modal(TextModal(
            title="Longueur minimale analysée", label="Nombre de lettres",
            placeholder="Ex : 20", default=str(current), required=True, max_length=4, on_submit=submit,
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
            await mgr.save_config(guild_id, min_vowel_ratio=pct / 100.0)
            await _rerender(i, guild_id, bot, author_id)

        current_pct = int(round((await mgr.load_config(guild_id)).get("min_vowel_ratio", 0.2) * 100))
        await inter.response.send_modal(TextModal(
            title="Ratio minimum de voyelles", label=f"Pourcentage ({RATIO_MIN_PCT} à {RATIO_MAX_PCT})",
            placeholder="Ex : 20", default=str(current_pct), required=True, max_length=3, on_submit=submit,
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