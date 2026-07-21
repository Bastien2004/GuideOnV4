"""
views/exp/gestion_view.py — Interface de gestion de l'EXP d'un membre.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.exp_manager import add_exp, get_user_exp, level_progress, remove_exp, reset_exp, text_progress_bar

from views._components.base_view import BaseLayoutView
from views._components.confirm_view import ConfirmView
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

MIN_EXP_EDIT = 1
MAX_EXP_EDIT = 1_000_000


# ============================================================
# 🧩 Construction de l'interface
# ============================================================

async def create_gestion_view(guild_id: int, target_id: int, bot, author_id: Optional[int] = None) -> Optional[BaseLayoutView]:
    """Construit l'interface de gestion de l'EXP d'un membre."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[EXP] Guild %s introuvable dans le cache", guild_id)
        return None

    target = guild.get_member(target_id)
    target_display = target.mention if target else f"`utilisateur {target_id}`"

    total_exp = await get_user_exp(guild_id, target_id)
    stats = level_progress(total_exp)
    bar = text_progress_bar(stats["progress_ratio"])

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    container.add_item(TextDisplay("# 🧩 Gestion Expérience"))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        f"👤 **Membre :** {target_display}\n"
        f"🏅 **Niveau :** {stats['level']} ({stats['tier']})\n"
        f"✨ **EXP :** {stats['current_exp']} / {stats['next_level_exp']}\n"
        f"{bar}"
    ))
    container.add_item(Separator())

    btn_add = Button(label="Ajouter", style=ButtonStyle.success, emoji="<:plus:1495444111505752154>")
    btn_add.callback = _cb_modify(guild_id, target_id, bot, author_id, add=True)

    btn_remove = Button(label="Retirer", style=ButtonStyle.secondary, emoji="<:moins:1508532114465882285>")
    btn_remove.callback = _cb_modify(guild_id, target_id, bot, author_id, add=False)

    btn_reset = Button(label="Réinitialiser", style=ButtonStyle.danger, emoji="<:recharger:1495444327629852703>")
    btn_reset.callback = _cb_reset(guild_id, target_id, bot, author_id)

    container.add_item(ActionRow(btn_add, btn_remove, btn_reset))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📑 CallBacks
# ============================================================

def _guard(author_id: Optional[int]):
    """Vérification de l'interaction (auteur de la commande + admin)."""

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


async def _rerender(interaction: Interaction, guild_id: int, target_id: int, bot, author_id):
    """Met à jour l'interface après une mutation."""
    new_view = await create_gestion_view(guild_id, target_id, bot, author_id)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur **introuvable**."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_modify(guild_id, target_id, bot, author_id, *, add: bool):
    """Gère les boutons d'ajout et de retrait d'EXP."""

    check = _guard(author_id)
    action_label = "Ajouter" if add else "Retirer"

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def on_submit(inter: Interaction, value: str):
            value = value.strip()
            if not value.isdigit():
                await inter.response.send_message(
                    view=error_container("La __quantité__ doit être un **nombre entier positif**."),
                    ephemeral=True,
                )
                return

            amount = int(value)
            if amount < MIN_EXP_EDIT or amount > MAX_EXP_EDIT:
                await inter.response.send_message(
                    view=error_container(
                        f"La quantité doit être entre **{MIN_EXP_EDIT}** et **{MAX_EXP_EDIT:,}**."
                    ),
                    ephemeral=True,
                )
                return

            if add:
                await add_exp(guild_id, target_id, amount)
            else:
                await remove_exp(guild_id, target_id, amount)
            await _rerender(inter, guild_id, target_id, bot, author_id)

        modal = TextModal(
            title=f"{action_label} de l'EXP",
            label="Quantité d'EXP",
            placeholder=f"Entre {MIN_EXP_EDIT} et {MAX_EXP_EDIT:,}",
            max_length=7,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_reset(guild_id, target_id, bot, author_id):
    """Gère le bouton de reset de l'EXP."""

    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        confirm = ConfirmView(
            owner_id=author_id or interaction.user.id,
            question="Réinitialiser l'**EXP** de ce membre à zéro ?",
            confirm_label="Réinitialiser",
            cancel_label="Annuler",
            confirm_style=ButtonStyle.danger,
        )
        await interaction.response.send_message(view=confirm, ephemeral=True)
        await confirm.wait()

        if not confirm.confirmed:
            return

        await reset_exp(guild_id, target_id)
        new_view = await create_gestion_view(guild_id, target_id, bot, author_id)
        if new_view is None:
            return
        try:
            await interaction.edit_original_response(view=new_view)
        except (discord.NotFound, discord.HTTPException):
            log.warning("[EXP] Mise à jour de l'interface impossible (message introuvable)")
    return cb


# ============================================================
# 🧩 Classe principale
# ============================================================

class ExpGestionView:

    @classmethod
    async def create(cls, guild_id: int, target_id: int, author_id: int, bot) -> BaseLayoutView:
        view = await create_gestion_view(guild_id, target_id, bot, author_id)

        if view is None:
            return error_container("**Impossible** de charger l'interface de __gestion__.")
        return view
