"""
views/mod/permissions_view.py — Dashboard des permissions /mod.

Un menu déroulant liste toutes les clés de permission (actions + panneaux
de config). Sélectionner une clé affiche les rôles actuellement autorisés
et un bouton pour les réassigner via un sélecteur de rôles natif Discord.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import ActionRow, Button, Container, Select, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.mod_permission_manager import (
    PERMISSION_KEYS,
    get_all_for_guild,
    get_permission_key,
    set_roles,
)

from views._components.base_view import BaseLayoutView
from views._components.role_select import RoleSelect

log = logging.getLogger(__name__)

CATEGORY_EMOJIS = {"action": "⚡", "config": "⚙️"}


# ============================================================
# 🧩 Construction de l'interface
# ============================================================

def _build_key_options(selected_key: Optional[str]) -> list[SelectOption]:
    options = []
    for pk in PERMISSION_KEYS:
        emoji = CATEGORY_EMOJIS.get(pk.category, "🔑")
        options.append(SelectOption(
            label=pk.label,
            value=pk.key,
            description=pk.description[:100],
            emoji=emoji,
            default=(pk.key == selected_key),
        ))
    return options


def _roles_display(guild: discord.Guild, role_ids: list[int]) -> str:
    if not role_ids:
        return "`Administrateur uniquement` (aucun rôle assigné)"
    mentions = []
    for role_id in role_ids:
        role = guild.get_role(role_id)
        mentions.append(role.mention if role is not None else f"`Rôle supprimé (ID {role_id})`")
    return " ".join(mentions)


async def create_permissions_view(
    guild_id: int, bot, author_id: Optional[int] = None, selected_key: Optional[str] = None
) -> Optional[BaseLayoutView]:
    """Construit le dashboard de permissions /mod."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[MOD_PERM] Guild %s introuvable dans le cache", guild_id)
        return None

    all_roles = await get_all_for_guild(guild_id)

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    container.add_item(TextDisplay("# 🔐 Permissions /mod"))
    container.add_item(Separator())
    container.add_item(TextDisplay(
        "-# Choisissez une commande ou un panneau de config pour voir/modifier "
        "les rôles autorisés à l'utiliser. Sans rôle assigné, seul un "
        "**Administrateur** peut l'utiliser."
    ))
    container.add_item(Separator())

    key_select = Select(
        placeholder="Choisir une commande / un panneau...",
        options=_build_key_options(selected_key),
        min_values=1,
        max_values=1,
    )
    key_select.callback = _cb_pick_key(guild_id, bot, author_id)
    container.add_item(ActionRow(key_select))

    if selected_key is not None:
        pk = get_permission_key(selected_key)
        if pk is not None:
            container.add_item(Separator())
            container.add_item(TextDisplay(
                f"### {CATEGORY_EMOJIS.get(pk.category, '🔑')} {pk.label}\n"
                f"-# {pk.description}\n\n"
                f"**Rôles autorisés :** {_roles_display(guild, all_roles.get(pk.key, []))}"
            ))

            edit_btn = Button(label="Modifier les rôles", style=ButtonStyle.primary, emoji="<:modifier:1495444144712192003>")
            edit_btn.callback = _cb_edit_roles(guild_id, bot, author_id, pk.key)
            container.add_item(ActionRow(edit_btn))

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


async def _rerender(interaction: Interaction, guild_id: int, bot, author_id, selected_key: Optional[str]):
    """Met à jour l'interface après une sélection ou une mutation."""
    new_view = await create_permissions_view(guild_id, bot, author_id, selected_key)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur **introuvable**."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_pick_key(guild_id, bot, author_id):
    """Gère le menu de sélection de la clé de permission."""
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        values = (interaction.data or {}).get("values") or []
        selected_key = values[0] if values else None
        await _rerender(interaction, guild_id, bot, author_id, selected_key)
    return cb


def _cb_edit_roles(guild_id, bot, author_id, key: str):
    """Ouvre le sélecteur de rôles natif pour réassigner une clé."""
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        pk = get_permission_key(key)
        label = pk.label if pk is not None else key

        role_select = RoleSelect(
            placeholder=f"Rôles autorisés — {label}",
            min_values=0,
            max_values=25,
            on_select=_on_roles_picked(guild_id, bot, author_id, key),
        )

        edit_view = BaseLayoutView(owner_id=author_id, timeout=300)
        edit_container = Container()
        edit_container.add_item(TextDisplay(
            f"### 🔐 {label}\n-# Sélectionnez les rôles autorisés (aucun = Administrateur uniquement)."
        ))
        edit_container.add_item(Separator())
        edit_container.add_item(ActionRow(role_select))
        edit_view.add_item(edit_container)

        await interaction.response.edit_message(view=edit_view)
    return cb


def _on_roles_picked(guild_id, bot, author_id, key: str):
    """Callback du RoleSelect : sauvegarde puis retour au dashboard."""

    async def on_select(interaction: Interaction, role_ids: list[int]) -> None:
        await set_roles(guild_id, key, role_ids)
        await _rerender(interaction, guild_id, bot, author_id, key)
    return on_select


# ============================================================
# 🧩 Classe principale
# ============================================================

class ModPermissionsView:
    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot):
        view = await create_permissions_view(guild_id, bot, author_id)

        if view is None:
            return error_container("**Impossible** de charger le __dashboard__ de permissions.")
        return view
