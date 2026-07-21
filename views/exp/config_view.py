"""
views/exp/config_view.py — Interface de configuration du système d'EXP.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.exp_manager import load_exp_config, save_exp_config
from utils.settings import settings

from views._components.base_view import BaseLayoutView
from views._components.select_page import SelectPageView
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

MAX_EXP_PER_TICK = 1000
MAX_BOOST_PERCENT = 500


def _state_btn(active: bool) -> Button:
    """Bouton d'état ON/OFF."""
    return Button(
        label="Activé" if active else "Désactivé",
        style=ButtonStyle.success if active else ButtonStyle.danger,
        emoji="<:valider:1495444292867723284>" if active else "<:annuler:1495444256754761979>",
    )


def _role_label(role_id: Optional[int], guild: discord.Guild) -> str:
    """Affichage du rôle boost configuré."""
    if role_id is None:
        return "`Aucun`"
    role = guild.get_role(role_id)
    return role.mention if role is not None else f"`Rôle supprimé (ID {role_id})`"


# ============================================================
# 🧩 Construction de l'interface
# ============================================================

async def create_config_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[BaseLayoutView]:
    """Construit l'interface de configuration du système d'EXP."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[EXP] Guild %s introuvable dans le cache", guild_id)
        return None

    cfg = await load_exp_config(guild_id)
    enabled = cfg.get("enabled", False)
    per_message = cfg.get("exp_per_message", 10)
    per_voice_minute = cfg.get("exp_per_voice_minute", 2)
    boost_role_id = cfg.get("boost_role_id")
    boost_percent = cfg.get("boost_percent", 0)

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    container.add_item(TextDisplay("# 🧩 Configuration Expérience"))
    container.add_item(Separator())

    btn_sys = _state_btn(enabled)
    btn_sys.callback = _cb_toggle(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay("**🔘 Statut du système**\n-# Active ou désactive le gain d'EXP."),
        accessory=btn_sys,
    ))
    container.add_item(Separator())

    btn_per_message = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_per_message.callback = _cb_edit_number(guild_id, bot, author_id, key="exp_per_message", title="💬 EXP par message")
    container.add_item(Section(
        TextDisplay(f"**💬 EXP par message**\n-# Actuel : **{per_message}**"),
        accessory=btn_per_message,
    ))
    container.add_item(Separator())

    btn_per_voice = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_per_voice.callback = _cb_edit_number(guild_id, bot, author_id, key="exp_per_voice_minute", title="🎙️ EXP par minute en vocal")
    container.add_item(Section(
        TextDisplay(f"**🎙️ EXP par minute en vocal**\n-# Actuel : **{per_voice_minute}**"),
        accessory=btn_per_voice,
    ))
    container.add_item(Separator())

    if boost_role_id is not None:
        role_btn = Button(label="Retirer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
        role_btn.callback = _cb_clear_boost_role(guild_id, bot, author_id)
    else:
        role_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
        role_btn.callback = _cb_pick_boost_role(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"**🚀 Rôle boost**\n-# Bonus de gain d'EXP (%).\n"
            f"-# Actuel : {_role_label(boost_role_id, guild)}"
        ),
        accessory=role_btn,
    ))

    btn_percent = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_percent.callback = _cb_edit_number(
        guild_id, bot, author_id, key="boost_percent", title="🚀 Bonus du rôle boost (%)", max_value=MAX_BOOST_PERCENT
    )
    container.add_item(Section(
        TextDisplay(f"**🚀 Bonus du rôle boost**\n-# Actuel : **{boost_percent}%**"),
        accessory=btn_percent,
    ))
    container.add_item(Separator())

    doc_btn = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
    container.add_item(ActionRow(doc_btn))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📑 CallBack
# ============================================================

def _guard(author_id: Optional[int]):
    """Vérification auteur + administrateur."""

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
                view=error_container("Vous devez être **Administrateur** pour effectuer cette **action**."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, bot, author_id):
    """Met à jour l'interface."""
    new_view = await create_config_view(guild_id, bot, author_id)
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
    """Gère le bouton d'activation."""
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_exp_config(guild_id)).get("enabled", False)
        await save_exp_config(guild_id, {"enabled": not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_edit_number(guild_id, bot, author_id, *, key: str, title: str, max_value: int = MAX_EXP_PER_TICK):
    """Gère l'édition d'une valeur numérique de la config (EXP/message, EXP/min vocal, %boost)."""
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        current = (await load_exp_config(guild_id)).get(key, 0)

        async def on_submit(inter: Interaction, value: str):
            value = value.strip()
            if not value.isdigit():
                await inter.response.send_message(
                    view=error_container("La valeur doit être un **nombre entier**."), ephemeral=True
                )
                return
            n = int(value)
            if n < 0 or n > max_value:
                await inter.response.send_message(
                    view=error_container(f"La valeur doit être entre **0** et **{max_value}**."),
                    ephemeral=True,
                )
                return
            await save_exp_config(guild_id, {key: n})
            await _rerender(inter, guild_id, bot, author_id)

        modal = TextModal(
            title=title,
            label="Valeur",
            placeholder=f"Ex : {current}",
            default=str(current),
            max_length=4,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_clear_boost_role(guild_id, bot, author_id):
    """Gère le retrait du rôle boost."""
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_exp_config(guild_id, {"boost_role_id": None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


async def _validate_boost_role(interaction: Interaction, role_id: int) -> Optional[str]:
    """Vérification de sécurité pour le rôle boost."""
    guild = interaction.guild
    role = guild.get_role(role_id) if guild else None
    if role is None:
        return "Rôle introuvable sur ce serveur."
    if role.is_default():
        return "Le rôle **everyone** ne peut pas être utilisé."
    return None


def _cb_pick_boost_role(guild_id, bot, author_id):
    """Gère la sélection du rôle boost."""
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        cfg = await load_exp_config(guild_id)

        async def _on_save(role_id: int) -> None:
            await save_exp_config(guild_id, {"boost_role_id": role_id})

        async def _build_return_view():
            return await create_config_view(guild_id, bot, author_id)

        await interaction.response.edit_message(
            view=SelectPageView(
                kind="role",
                title="🚀 Rôle boost",
                description="-# Rôle bénéficiant d'un boost d'exp.",
                current_value=cfg.get("boost_role_id"),
                owner_id=author_id,
                on_save=_on_save,
                build_return_view=_build_return_view,
                validate=_validate_boost_role,
            )
        )
    return cb


# ============================================================
# 🧩 Classe principale
# ============================================================

class ExpConfigView:
    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot):
        view = await create_config_view(guild_id, bot, author_id)

        if view is None:
            return error_container("**Impossible** de charger la __configuration__ (serveur introuvable).")
        return view
