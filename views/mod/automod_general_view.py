"""
views/mod/automod_general_view.py — Configuration paramètres généraux automod (v2).

4 réglages, style autorole compact :
  - salon d'alerte staff (channel select via modal ID pour rester cohérent
    avec le choix "pas de select" du projet côté /dev permissions ; en
    revanche pour les CHANNELS/ROLES natifs Discord on utilise les select
    natifs car ce sont des ressources du serveur, pas des users)
  - rôle staff à ping sur mute auto
  - notifications dans le salon (toggle)
  - fenêtre de récidive (10s → 180s)
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, RoleSelect, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers import mod_automod_general_manager as mgr
from utils.settings import settings
from views._components.channel_select import ChannelSelect

log = logging.getLogger(__name__)

CHANNEL_TYPES = [discord.ChannelType.text, discord.ChannelType.news]


async def create_automod_general_view(
    guild_id: int, bot, author_id: Optional[int] = None,
) -> Optional[LayoutView]:
    """Construction de la vue paramètres généraux."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await mgr.load_general(guild_id)

    view = LayoutView(timeout=600)
    container = Container()

    container.add_item(TextDisplay("# <:parametre:1495444004328706059> Paramètres Automod"))
    container.add_item(Separator())

    # ── Salon d'alerte staff ──
    alert_ch_id = cfg.get("alert_channel_id")
    alert_ch_line = f"<#{alert_ch_id}>" if alert_ch_id else "`Non configuré`"

    container.add_item(TextDisplay(
        "**📥 Salon d'alerte staff**\n"
        "-# Reçoit les logs détaillés à chaque infraction.\n"
        f"-# Actuel : {alert_ch_line}"
    ))
    ch_select = ChannelSelect(
        placeholder="Choisir un salon d'alerte",
        on_select=_on_channel_select(guild_id, bot, author_id),
        channel_types=CHANNEL_TYPES,
    )
    container.add_item(ActionRow(ch_select))
    if alert_ch_id:
        btn_clear_ch = Button(label="Retirer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
        btn_clear_ch.callback = _cb_clear_channel(guild_id, bot, author_id)
        container.add_item(ActionRow(btn_clear_ch))
    container.add_item(Separator())

    # ── Rôle staff à ping ──
    staff_role_id = cfg.get("staff_role_id")
    staff_role_line = f"<@&{staff_role_id}>" if staff_role_id else "`Non configuré`"

    container.add_item(TextDisplay(
        "**👥 Rôle staff à ping**\n"
        "-# Mentionné dans les alertes de mute auto.\n"
        f"-# Actuel : {staff_role_line}"
    ))
    role_select = RoleSelect(placeholder="Choisir un rôle staff")
    role_select.callback = _on_role_select(guild_id, bot, author_id, role_select)
    container.add_item(ActionRow(role_select))
    if staff_role_id:
        btn_clear_role = Button(label="Retirer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
        btn_clear_role.callback = _cb_clear_role(guild_id, bot, author_id)
        container.add_item(ActionRow(btn_clear_role))
    container.add_item(Separator())

    # ── Toggle notifs salon ──
    notify = cfg.get("notify_in_channel", True)
    toggle_label = "<:valider:1495444292867723284> Activées" if notify else "<:annuler:1495444256754761979> Désactivées"
    toggle_style = ButtonStyle.success if notify else ButtonStyle.danger
    btn_toggle = Button(label=toggle_label, style=toggle_style)
    btn_toggle.callback = _cb_toggle_notify(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            "**🔔 Notifications dans le salon**\n"
            "-# Message envoyé au membre dans le salon d'origine à chaque infraction."
        ),
        accessory=btn_toggle,
    ))
    container.add_item(Separator())

    # ── Retour ──
    btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
    btn_back.callback = _cb_back(guild_id, bot, author_id)
    container.add_item(ActionRow(
        btn_back,
        Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚"),
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📑 Guard
# ============================================================

def _guard(author_id: Optional[int]):
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** de la commande peut utiliser ce __menu__."),
                ephemeral=True,
            )
            return False
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur** pour réaliser cette action."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, bot, author_id):
    new_view = await create_automod_general_view(guild_id, bot, author_id)
    if new_view is None:
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


# ============================================================
# 📑 Callbacks
# ============================================================

def _on_channel_select(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction, channel_id: int):
        if not await check(interaction):
            return
        await mgr.save_general(guild_id, alert_channel_id=channel_id)
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_channel(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await mgr.save_general(guild_id, alert_channel_id=None)
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _on_role_select(guild_id, bot, author_id, select_ref: RoleSelect):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        if not select_ref.values:
            return
        role = select_ref.values[0]
        await mgr.save_general(guild_id, staff_role_id=role.id)
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_role(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await mgr.save_general(guild_id, staff_role_id=None)
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_toggle_notify(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await mgr.load_general(guild_id)).get("notify_in_channel", True)
        await mgr.save_general(guild_id, notify_in_channel=not current)
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_back(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        from views.mod.automod_dashboard_view import create_automod_dashboard_view
        new_view = await create_automod_dashboard_view(guild_id, bot, author_id)
        if new_view is None:
            return
        await interaction.response.edit_message(view=new_view)
    return cb