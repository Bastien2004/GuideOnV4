"""
views/invite/gestion_view.py — Interface de gestion des invitations.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import ActionRow, Button, Container, Select, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.invite_manager import VALID_TYPES, add_invite, get_user_stats, remove_invite, reset_user_stats

from views._components.base_view import BaseLayoutView
from views._components.confirm_view import ConfirmView
from views._components.text_modal import TextModal


log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

TYPE_LABELS = {
    "regular": ("Régulières", "✅"),
    "fake": ("Fausses", "🚫"),
    "bonus": ("Bonus", "🎁"),
    "left": ("Parties", "🍃"),
}

DEFAULT_TYPE = "bonus"


# ============================================================
# 🧩 Constrcution de l'interface
# ============================================================

async def create_gestion_view(guild_id: int, target_id: int, bot, author_id: Optional[int] = None, selected_type: str = DEFAULT_TYPE) -> Optional[BaseLayoutView]:
    """Construction de l'interface de gestion d'invitations des utilisateurs."""

    if selected_type not in VALID_TYPES:
        selected_type = DEFAULT_TYPE

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[INVITE] Guild %s introuvable dans le cache", guild_id)
        return None

    target = guild.get_member(target_id)
    target_display = target.mention if target else f"`utilisateur {target_id}`"

    stats = await get_user_stats(guild_id, target_id)

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    container.add_item(TextDisplay(f"# <:fichier:1495446721520730242> Gestion Invitations"))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        f"### 📊 Statistiques {target_display} :\n"
        f"-# ⇝ Régulières : **{stats['regular']}**\n"
        f"-# ⇝ Fausses : **{stats['fake']}**\n"
        f"-# ⇝ Bonus : **{stats['bonus']}**\n"
        f"-# ⇝ Parties : **{stats['left']}**\n\n"

        f"-# ⇝ Score total : **{stats['total']}**"
    ))
    container.add_item(Separator())


    options = [
        SelectOption(
            label=TYPE_LABELS[t][0],
            value=t,
            emoji=TYPE_LABELS[t][1],
            default=(t == selected_type),
        )
        for t in VALID_TYPES
    ]
    type_select = Select(
        placeholder="Type de valeur à modifier",
        options=options,
        min_values=1,
        max_values=1,
    )
    type_select.callback = _cb_pick_type(guild_id, target_id, bot, author_id)
    container.add_item(TextDisplay(f"### 🎯 Type sélectionné :"))
    container.add_item(ActionRow(type_select))

    btn_add = Button(label="Ajouter", style=ButtonStyle.success, emoji="<:plus:1495444111505752154>")
    btn_add.callback = _cb_modify(guild_id, target_id, bot, author_id, selected_type, add=True)

    btn_remove = Button(label="Retirer", style=ButtonStyle.secondary, emoji="<:moins:1508532114465882285>")
    btn_remove.callback = _cb_modify(guild_id, target_id, bot, author_id, selected_type, add=False)

    btn_reset = Button(label="Réinitialiser", style=ButtonStyle.danger, emoji="<:recharger:1495444327629852703>")
    btn_reset.callback = _cb_reset(guild_id, target_id, bot, author_id)

    container.add_item(ActionRow(btn_add, btn_remove, btn_reset))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📑 CallBack
# ============================================================

def _guard(author_id: Optional[int]):
    """Sécurisation des boutons/menus (auteur + admin)."""
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container(
                    "Seul l'**auteur** de la commande peut utiliser ce __menu__."
                ),
                ephemeral=True,
            )
            return False
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur** pour effectuer cette action."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, target_id: int, bot, author_id, selected_type: str):
    """Mise à jour de l'interface de configuration."""
    new_view = await create_gestion_view(guild_id, target_id, bot, author_id, selected_type)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur **introuvable**."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_pick_type(guild_id, target_id, bot, author_id):
    """Gère le menu du type d'invites (bonus, regulière ...)."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        values = (interaction.data or {}).get("values") or []
        new_type = values[0] if values else DEFAULT_TYPE
        if new_type not in VALID_TYPES:
            new_type = DEFAULT_TYPE
        await _rerender(interaction, guild_id, target_id, bot, author_id, new_type)
    return cb


def _cb_modify(guild_id, target_id, bot, author_id, invite_type: str, *, add: bool):
    """Gère les boutons d'ajout et retrait d'invites."""

    check = _guard(author_id)
    action_label = "Ajouter" if add else "Retirer"

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        type_label = TYPE_LABELS[invite_type][0].lower()

        async def on_submit(inter: Interaction, value: str):
            value = value.strip()
            try:
                n = int(value)
            except ValueError:
                await inter.response.send_message(
                    view=error_container("La __quantité__ doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n <= 0:
                await inter.response.send_message(
                    view=error_container("La quantité doit être **strictement positive**."),
                    ephemeral=True,
                )
                return
            if n > 100_000:
                await inter.response.send_message(
                    view=error_container(
                        "La quantité doit être **inférieure ou égale à 100 000**."
                    ),
                    ephemeral=True,
                )
                return

            if add:
                await add_invite(guild_id, target_id, invite_type, n)
            else:
                await remove_invite(guild_id, target_id, invite_type, n)
            await _rerender(inter, guild_id, target_id, bot, author_id, invite_type)

        modal = TextModal(
            title=f"{action_label} ({type_label})",
            label="Quantité",
            placeholder="Ex : 1",
            default="1",
            min_length=1,
            max_length=6,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


def _cb_reset(guild_id, target_id, bot, author_id):
    """Gère le bouton de reset des invites."""

    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        confirm = ConfirmView(
            owner_id=author_id or interaction.user.id,
            question="Réinitialiser **tous** les compteurs de ce membre ?",
            confirm_label="Réinitialiser",
            cancel_label="Annuler",
            confirm_style=ButtonStyle.danger,
        )
        await interaction.response.send_message(view=confirm, ephemeral=True)
        await confirm.wait()

        if not confirm.confirmed:
            return

        await reset_user_stats(guild_id, target_id)
        new_view = await create_gestion_view(guild_id, target_id, bot, author_id)
        if new_view is None:
            return
        try:
            await interaction.edit_original_response(view=new_view)
        except (discord.NotFound, discord.HTTPException):
            log.warning("[Invite] Mise à jour de l'interface impossible (message introuvable)")
    return cb


# ============================================================
# 🧩 Class principale
# ============================================================

class InviteGestionView:

    @classmethod
    async def create(cls, guild_id: int, target_id: int, author_id: int, bot) -> BaseLayoutView:
        view = await create_gestion_view(guild_id, target_id, bot, author_id)
        
        if view is None:
            return error_container("**Impossible** de charger l'interface de __gestion__.")
        return view