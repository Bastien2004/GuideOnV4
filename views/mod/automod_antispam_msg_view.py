"""
views/mod/automod_antispam_msg_view.py — Interface de configuration du système Anti Spam Message.

Même structure qu'automod_antifullcaps_view.py : toggle + deux paramètres
numériques modifiables via TextModal (fenêtre en secondes, nombre de
messages identiques déclenchant l'infraction).
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_antispam_msg_manager as mgr
from utils.settings import settings
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

WINDOW_MIN, WINDOW_MAX = 2, 120
MAX_MESSAGES_MIN, MAX_MESSAGES_MAX = 2, 20


# ============================================================
# 🧩 Construction de la view
# ============================================================

async def create_automod_antispam_msg_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[LayoutView]:
    """Construction de la view de configuration Anti Spam Message."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await mgr.load_config(guild_id)
    enabled = cfg.get("enabled", False)
    window_seconds = cfg.get("window_seconds", 10)
    max_messages = cfg.get("max_messages", 3)

    view = LayoutView(timeout=600)
    c = Container()

    c.add_item(TextDisplay("# <:protect_config:1539608365704028340> Système Anti Spam Message"))
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
            "-# Bloque un même message répété, même à travers plusieurs salons."
        ),
        accessory=toggle_btn,
    ))
    c.add_item(Separator())

    # Fenêtre d'observation
    btn_window = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_window.callback = _cb_edit_window(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**⏱️ Fenêtre d'observation**\n"
            f"-# Analyse les messages envoyés dans les `{window_seconds}` dernières secondes."
        ),
        accessory=btn_window,
    ))
    c.add_item(Separator())

    # Seuil de déclenchement
    btn_max = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_max.callback = _cb_edit_max(guild_id, bot, author_id)
    c.add_item(Section(
        TextDisplay(
            "**🔁 Seuil de déclenchement**\n"
            f"-# À partir de `{max_messages}` messages identiques (tous salons confondus)."
        ),
        accessory=btn_max,
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
    new_view = await create_automod_antispam_msg_view(guild_id, bot, author_id)
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


def _cb_edit_window(guild_id, bot, author_id):
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
            if n < WINDOW_MIN or n > WINDOW_MAX:
                await i.response.send_message(
                    view=warning_container(
                        f"La fenêtre doit être entre **{WINDOW_MIN}** et **{WINDOW_MAX}** secondes."
                    ),
                    ephemeral=True,
                )
                return
            await mgr.save_config(guild_id, window_seconds=n)
            await _rerender(i, guild_id, bot, author_id)

        current = (await mgr.load_config(guild_id)).get("window_seconds", 10)
        await inter.response.send_modal(TextModal(
            title="Fenêtre d'observation", label="Durée en secondes",
            placeholder="Ex : 10", default=str(current), required=True, max_length=3, on_submit=submit,
        ))
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
                    view=warning_container("La valeur doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n < MAX_MESSAGES_MIN or n > MAX_MESSAGES_MAX:
                await i.response.send_message(
                    view=warning_container(
                        f"Le seuil doit être entre **{MAX_MESSAGES_MIN}** et **{MAX_MESSAGES_MAX}**."
                    ),
                    ephemeral=True,
                )
                return
            await mgr.save_config(guild_id, max_messages=n)
            await _rerender(i, guild_id, bot, author_id)

        current = (await mgr.load_config(guild_id)).get("max_messages", 3)
        await inter.response.send_modal(TextModal(
            title="Seuil de déclenchement", label="Nombre de messages identiques",
            placeholder="Ex : 3", default=str(current), required=True, max_length=2, on_submit=submit,
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