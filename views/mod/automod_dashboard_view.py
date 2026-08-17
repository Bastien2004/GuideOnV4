"""
views/mod/automod_dashboard_view.py — Dashboard central /mod config (v3).

Menu compact style config autorole : header + Section paramètres généraux
+ liste des systèmes en Sections. Chaque Section a un bouton accessoire
"Configurer" (systèmes disponibles) ou "Bientôt" désactivé (systèmes à venir).

Refactoré au factory pattern `create_automod_dashboard_view` (async) pour
suivre la convention autorole/config_view.
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers import (
    mod_automod_antifullcaps_manager as antifullcaps_mgr,
    mod_automod_antispam_emoji_manager as antispam_emoji_mgr,
    mod_automod_antispam_mention_manager as antispam_mention_mgr,
    mod_automod_banword_manager as banword_mgr,
    mod_automod_general_manager as general_mgr,
)
from utils.settings import settings

log = logging.getLogger(__name__)

# ============================================================
# 🔩 Registre des systèmes
# ============================================================

_SYSTEMS: list[dict] = [
    {"key": "banword", "emoji": "🚫", "name": "Ban Word",
     "desc": "Liste de mots interdits avec anti-contournement.", "available": True},
    {"key": "antifullcaps", "emoji": "🔠", "name": "Anti Full Maj",
     "desc": "Bloque les messages majoritairement en MAJUSCULES.", "available": True},
    {"key": "antispam_mention", "emoji": "📣", "name": "Anti Spam Mention",
     "desc": "Limite le nombre de mentions par message.", "available": True},
    {"key": "antispam_emoji", "emoji": "😀", "name": "Anti Spam Emoji",
     "desc": "Limite le nombre d'emojis par message.", "available": True},
    {"key": "nolink", "emoji": "🔗", "name": "No Link",
     "desc": "Bloque les liens sauf dans la whitelist de salons.", "available": False},
    {"key": "antilink", "emoji": "☠️", "name": "Anti Link",
     "desc": "Bloque les extensions dangereuses (.exe, .zip…).", "available": False},
    {"key": "antispam_msg", "emoji": "💬", "name": "Anti Spam Message",
     "desc": "Détecte les messages répétés (inter-salons).", "available": False},
    {"key": "antiflood", "emoji": "🌊", "name": "Anti Flood",
     "desc": "Détecte les messages incohérents (voyelle/consonne).", "available": False},
]


# ============================================================
# 🧩 Factory principale
# ============================================================

async def create_automod_dashboard_view(
    guild_id: int, bot, author_id: Optional[int] = None,
) -> Optional[LayoutView]:
    """Construit la vue dashboard automod (style compact autorole)."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    general = await general_mgr.load_general(guild_id)
    statuses = {
        "banword": (await banword_mgr.load_config(guild_id))["enabled"],
        "antifullcaps": (await antifullcaps_mgr.load_config(guild_id))["enabled"],
        "antispam_mention": (await antispam_mention_mgr.load_config(guild_id))["enabled"],
        "antispam_emoji": (await antispam_emoji_mgr.load_config(guild_id))["enabled"],
    }

    view = LayoutView(timeout=600)
    container = Container()

    # ── Header ──
    container.add_item(TextDisplay("# 🛡️ Configuration Auto-modération"))
    container.add_item(Separator())

    # ── Paramètres généraux ──
    alert_ch_id = general.get("alert_channel_id")
    alert_ch_line = f"<#{alert_ch_id}>" if alert_ch_id else "`Non configuré`"
    staff_role_id = general.get("staff_role_id")
    staff_role_line = f"<@&{staff_role_id}>" if staff_role_id else "`Non configuré`"
    notify = general.get("notify_in_channel", True)
    window = general.get("notification_window_seconds", 60)

    general_btn = Button(label="Configurer", style=ButtonStyle.primary, emoji="⚙️")
    general_btn.callback = _cb_open_general(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            "**⚙️ Paramètres généraux**\n"
            f"-# Salon d'alerte : {alert_ch_line}\n"
            f"-# Rôle staff à ping : {staff_role_line}\n"
            f"-# Fenêtre de récidive : **{window}s** · Notifs salon : "
            f"{'✅' if notify else '❌'}"
        ),
        accessory=general_btn,
    ))
    container.add_item(Separator())

    # ── Systèmes ──
    for sys in _SYSTEMS:
        if sys["available"]:
            enabled = statuses.get(sys["key"], False)
            dot = "🟢" if enabled else "🔴"
            state = "Activé" if enabled else "Désactivé"
            btn = Button(label="Configurer", style=ButtonStyle.primary, emoji="⚙️")
            btn.callback = _cb_open_system(guild_id, bot, author_id, sys["key"])
        else:
            dot = "⚪"
            state = "À venir"
            btn = Button(label="Bientôt", style=ButtonStyle.secondary, emoji="🚧", disabled=True)

        container.add_item(Section(
            TextDisplay(
                f"**{sys['emoji']} {sys['name']}** · {dot} {state}\n"
                f"-# {sys['desc']}"
            ),
            accessory=btn,
        ))

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
    """Reconstruit + réédite le dashboard (helper exporté aux vues enfants)."""
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


def _cb_open_system(guild_id, bot, author_id, key):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        if key == "banword":
            from views.mod.automod_banword_view import create_automod_banword_view
            new_view = await create_automod_banword_view(guild_id, bot, author_id)
        elif key == "antifullcaps":
            from views.mod.automod_antifullcaps_view import create_automod_antifullcaps_view
            new_view = await create_automod_antifullcaps_view(guild_id, bot, author_id)
        elif key == "antispam_mention":
            from views.mod.automod_antispam_mention_view import create_automod_antispam_mention_view
            new_view = await create_automod_antispam_mention_view(guild_id, bot, author_id)
        elif key == "antispam_emoji":
            from views.mod.automod_antispam_emoji_view import create_automod_antispam_emoji_view
            new_view = await create_automod_antispam_emoji_view(guild_id, bot, author_id)
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

# Le cog cogs/mod/mod_config.py appelle AutomodDashboardView.build(guild, owner_id)
# Alias pour ne pas devoir toucher au cog.
class AutomodDashboardView:
    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int):
        # Wrapper : appelle la nouvelle factory. Retourne le LayoutView directement,
        # ce qui est compatible avec le followup.send(view=...) du cog.
        # bot est récupéré via guild._state._get_client — hack acceptable en compat.
        bot = guild._state._get_client()
        return await create_automod_dashboard_view(guild.id, bot, owner_id)