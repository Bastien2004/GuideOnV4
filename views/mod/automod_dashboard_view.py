"""
views/mod/automod_dashboard_view.py — Centre de configuration de l'automod.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Select, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_general_manager as general_mgr
from utils.settings import settings

log = logging.getLogger(__name__)

# ============================================================
# 🔩 Registre des systèmes
# ============================================================

_SYSTEMS: list[dict] = [
    {"key": "banword", "name": "Ban Word",
     "desc": "↳ Détecte et supprime les mots interdits.", "available": True},

    {"key": "antifullcaps", "name": "Anti Full Maj",
     "desc": "↳ Bloque les messages en majuscule.", "available": True},

    {"key": "antispam_mention", "name": "Anti Spam Mention",
     "desc": "↳ Empêche le spam de mention.", "available": True},

    {"key": "antispam_emoji", "name": "Anti Spam Emoji",
     "desc": "↳ Bloque l'utilisation abusive d'emoji.", "available": True},

    {"key": "nolink", "name": "No Link",
     "desc": "↳ Supprime les liens (salon whitelist).", "available": True},

    {"key": "antilink", "name": "Anti Link",
     "desc": "↳ Bloque les extensions dangereuses (ex : .exe).", "available": True},

    {"key": "antispam_msg", "emoji": "💬", "name": "Anti Spam Message",
     "desc": "↳ Protège du spam de message.", "available": True},

    {"key": "antiflood", "emoji": "🌊", "name": "Anti Flood",
     "desc": "↳ Supprime les messages incohérents et parasite.", "available": True},
]


# ============================================================
# 🧩 Construction de la view
# ============================================================

async def create_automod_dashboard_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[LayoutView]:
    """Construction de la view du centre de configuration."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    general = await general_mgr.load_general(guild_id)

    view = LayoutView(timeout=600)
    container = Container()

    # ── Header ──
    container.add_item(TextDisplay("# <:bouclier:1539013183577133106> Configuration Automod"))
    container.add_item(Separator())

    # ── Paramètres généraux ──
    alert_ch_id = general.get("alert_channel_id")
    alert_ch_line = f"<#{alert_ch_id}>" if alert_ch_id else "`Non configuré`"
    staff_role_id = general.get("staff_role_id")
    staff_role_line = f"<@&{staff_role_id}>" if staff_role_id else "`Non configuré`"
    notify = general.get("notify_in_channel", True)

    general_btn = Button(label="Configurer", style=ButtonStyle.primary, emoji="<:parametre:1495444004328706059>")
    general_btn.callback = _cb_open_general(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            "⚙️ __**Paramètres**__ :\n"
            f"➥ Salon d'alerte : {alert_ch_line}\n"
            f"➥ Rôle staff : {staff_role_line}\n"
            f"➥ Notifs salon : {'`Activé`' if notify else '`Désactivé`'}"
        ),
        accessory=general_btn,
    ))
    container.add_item(Separator())

    # ── Systèmes Select (menu déroulant) ──

    options: list[SelectOption] = []
    for sys in _SYSTEMS:
        if sys["available"]:
            options.append(SelectOption(
                label=sys["name"],
                description=sys["desc"][:100],
                value=sys["key"],
            ))
        else:
            options.append(SelectOption(
                label=sys["name"],
                description=f"{sys['desc']} · Bientôt"[:100],
                value=f"__unavailable__{sys['key']}",
            ))

    if not options:
        options.append(SelectOption(
            label="Aucun système disponible",
            value="__none__",
            emoji="⚠️",
            default=True,
        ))
        select_disabled = True
    else:
        select_disabled = False

    select = Select(
        placeholder="Choisir un système à configurer",
        options=options, min_values=1, max_values=1,
        disabled=select_disabled,
    )

    select.callback = _on_select_system(guild_id, bot, author_id, select)
    container.add_item(ActionRow(select))

    container.add_item(Separator())
    container.add_item(ActionRow(
        Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚"),
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📑 Guard + rerender
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


async def rerender_dashboard(interaction: Interaction, guild_id: int, bot, author_id):
    new_view = await create_automod_dashboard_view(guild_id, bot, author_id)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Le serveur est **introuvable**."), ephemeral=True,
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


# ============================================================
# 📑 Callbacks
# ============================================================

def _cb_open_general(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        from views.mod.automod_general_view import create_automod_general_view
        new_view = await create_automod_general_view(guild_id, bot, author_id)
        if new_view is None:
            await interaction.response.send_message(
                view=error_container("Serveur introuvable."), ephemeral=True,
            )
            return
        await interaction.response.edit_message(view=new_view)
    return cb


def _on_select_system(guild_id, bot, author_id, select_ref: Select):
    """Callback de sélection d'un système dans le menu déroulant."""
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        if not select_ref.values:
            return
        value = select_ref.values[0]

        # Système marqué "bientôt" : message court, pas de changement de vue.
        if value.startswith("__unavailable__"):
            await interaction.response.send_message(
                view=warning_container("🚧 Ce système sera **bientôt disponible**."),
                ephemeral=True,
            )
            return

        # Système disponible : ouverture de la vue de config.
        if value == "banword":
            from views.mod.automod_banword_view import create_automod_banword_view
            new_view = await create_automod_banword_view(guild_id, bot, author_id)
        elif value == "antifullcaps":
            from views.mod.automod_antifullcaps_view import create_automod_antifullcaps_view
            new_view = await create_automod_antifullcaps_view(guild_id, bot, author_id)
        elif value == "antispam_mention":
            from views.mod.automod_antispam_mention_view import create_automod_antispam_mention_view
            new_view = await create_automod_antispam_mention_view(guild_id, bot, author_id)
        elif value == "antispam_emoji":
            from views.mod.automod_antispam_emoji_view import create_automod_antispam_emoji_view
            new_view = await create_automod_antispam_emoji_view(guild_id, bot, author_id)
        elif value == "nolink":
            from views.mod.automod_nolink_view import create_automod_nolink_view
            new_view = await create_automod_nolink_view(guild_id, bot, author_id)
        else:
            return

        if new_view is None:
            await interaction.response.send_message(
                view=error_container("Serveur introuvable."), ephemeral=True,
            )
            return
        await interaction.response.edit_message(view=new_view)
    return cb


# ============================================================
# 🔙 Compat : alias pour /mod config
# ============================================================

class AutomodDashboardView:
    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int):
        bot = guild._state._get_client()
        return await create_automod_dashboard_view(guild.id, bot, owner_id)