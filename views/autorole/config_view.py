"""
views/autorole/config_view.py — Interface /config autorole.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container
from utils.managers.autorole_manager import load_autorole_config, save_autorole_config
from views._components.select_page import SelectPageView

from utils.settings import settings

log = logging.getLogger(__name__)

SLOT_CONFIG = [
    (1, "🎯", "Rôle automatique 1", False),
    (2, "🎯", "Rôle automatique 2", False),
    (3, "⭐", "Rôle automatique 3", True),
]


# ======================================================
# ==================== BUILDER =========================
# ======================================================

async def create_autorole_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[LayoutView]:
    """Construction de la view de configuration de l'auto-rôle."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await load_autorole_config(guild_id)
    gold = is_gold(guild_id)

    view = LayoutView(timeout=600)
    container = Container()
    container.add_item(TextDisplay("# 🎭 Configuration Auto-rôle"))
    container.add_item(Separator())

    # ── Toggle ON/OFF ──
    enabled = cfg.get("auto_role_active", False)
    toggle_btn = Button(
        label="✅ Activé" if enabled else "❌ Désactivé",
        style=ButtonStyle.success if enabled else ButtonStyle.danger,
    )

    toggle_btn.callback = _cb_toggle(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            "**🔘 Statut du système**\n"
            "-# Active ou désactive le système d'auto-rôle.\n"
        ),
        accessory=toggle_btn,
    ))
    container.add_item(Separator())

    # ── Slots ──
    for slot_num, emoji, label, gold_only in SLOT_CONFIG:
        key = f"role_id_{slot_num}"
        role_id = cfg.get(key)
        role = guild.get_role(role_id) if role_id else None

        if gold_only and not gold:
            lock_btn = Button(label="Gold+ requis", style=ButtonStyle.secondary, emoji="🔒")
            lock_btn.callback = _cb_gold_lock(author_id)
            container.add_item(Section(
                TextDisplay(f"**{emoji} {label}** ✨\n-# Réservé aux serveurs Gold+"),
                accessory=lock_btn,
            ))

        else:
            if role:
                role_display = role.mention
            elif role_id:
                role_display = "`⚠️ Rôle supprimé`"
            else:
                role_display = "`Non configuré`"
            gold_hint = " ✨" if gold_only else ""

            if role_id:
                action_btn = Button(
                    label="Retirer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>"
                )
                action_btn.callback = _cb_remove_role(guild_id, bot, author_id, key)
            else:
                action_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
                action_btn.callback = _cb_set_role(guild_id, bot, author_id, key, emoji, label)

            container.add_item(Section(
                TextDisplay(f"**{emoji} {label}{gold_hint}**\n-# {role_display}"),
                accessory=action_btn,
            ))

        container.add_item(Separator())

    # ── Footer ──
    lien = settings.doc_url

    container.add_item(ActionRow(Button(
        label="Documentation", style=ButtonStyle.link, url=lien, emoji="📚"
    )))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ======================================================
# ===================== CALLBACKS ======================
# ======================================================

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
                view=error_container("Vous devez être **Administrateur**."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, bot, author_id):
    new_view = await create_autorole_view(guild_id, bot, author_id)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur **introuvable**."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_toggle(guild_id, bot, author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_autorole_config(guild_id)).get("auto_role_active", False)
        await save_autorole_config(guild_id, {"auto_role_active": not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_gold_lock(author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await send_gold_error(interaction)
    return cb


async def _validate_role_selection(interaction: Interaction, role_id: int) -> Optional[str]:
    """Vérifs de sécurité avant d'accepter un rôle auto (hiérarchie + type)."""

    guild = interaction.guild
    role = guild.get_role(role_id) if guild else None
    if role is None:
        return "Rôle introuvable sur ce serveur."

    if role.position >= guild.me.top_role.position:
        return (
            "Ce rôle est au-dessus ou au même niveau que mon rôle.\n"
            "-# Placez mon rôle plus haut dans la hiérarchie."
        )

    if role.is_default() or role.is_bot_managed() or role.is_integration():
        return "Ce type de rôle ne peut pas être utilisé (rôle par défaut, bot ou intégration)."

    return None


def _cb_set_role(guild_id, bot, author_id, key, emoji, label):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        cfg = await load_autorole_config(guild_id)

        async def _on_save(role_id: int) -> None:
            await save_autorole_config(guild_id, {key: role_id})

        async def _build_return_view():
            return await create_autorole_view(guild_id, bot, author_id)

        await interaction.response.edit_message(
            view=SelectPageView(
                kind="role",
                title=f"{emoji} {label}",
                current_value=cfg.get(key),
                owner_id=author_id,
                on_save=_on_save,
                build_return_view=_build_return_view,
                validate=_validate_role_selection,
            )
        )
    return cb


def _cb_remove_role(guild_id, bot, author_id, key):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_autorole_config(guild_id, {key: None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb