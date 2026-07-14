"""
views/invite/config_view.py — Interface de configuration du système d'invitations.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.invite_manager import load_invite_config, save_invite_config

from views._components.base_view import BaseLayoutView
from views._components.select_page import SelectPageView
from views._components.text_modal import TextModal
from utils.settings import settings

log = logging.getLogger(__name__)


# ============================================================
# 📑 Fonctions (UI)
# ============================================================

def _state_btn(active: bool) -> Button:
    """Gestion bouton d'état ON/OFF."""
    return Button(
        label="Activé" if active else "Désactivé",
        style=ButtonStyle.success if active else ButtonStyle.danger,
        emoji="<:valider:1495444292867723284>" if active else "<:annuler:1495444256754761979>",
    )


def _role_label(role_id: Optional[int], guild: discord.Guild) -> str:
    """Gestion affichage du rôle."""
    if role_id is None:
        return "`Non configuré`"
    role = guild.get_role(role_id)
    return role.mention if role is not None else f"`Rôle supprimé (ID {role_id})`"


# ============================================================
# 🧩 Construction de l'interface
# ============================================================

async def create_invite_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[BaseLayoutView]:
    """Construit l'interface de configuration."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[Invite] Guild %s introuvable dans le cache", guild_id)
        return None

    cfg = await load_invite_config(guild_id)
    enabled = cfg.get("enabled", False)
    reward_role_id = cfg.get("reward_role_id")
    threshold = cfg.get("reward_threshold", 10)

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    container.add_item(TextDisplay(f"# 📨 Configuration Invitations"))
    container.add_item(Separator())

    btn_sys = _state_btn(enabled)
    btn_sys.callback = _cb_toggle(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay("**🔘 Statut du système**\n-# Active ou désactive le suivi des invitations."),
        accessory=btn_sys,
    ))
    container.add_item(Separator())

    if reward_role_id is not None:
        role_btn = Button(label="Retirer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
        role_btn.callback = _cb_clear_role(guild_id, bot, author_id)
    else:
        role_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
        role_btn.callback = _cb_pick_role(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"**🎁 Rôle-récompense**\n-# Attribué automatiquement au seuil d'invitations.\n"
            f"-# Actuel : {_role_label(reward_role_id, guild)}"
        ),
        accessory=role_btn,
    ))
    container.add_item(Separator())

    btn_threshold = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_threshold.callback = _cb_edit_threshold(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"**🎯 Seuil requis**\n-# Seuil d'invitations obtenir le rôle.\n"
            f"-# Actuel : **{threshold}**"
        ),
        accessory=btn_threshold,
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
    new_view = await create_invite_view(guild_id, bot, author_id)
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
        current = (await load_invite_config(guild_id)).get("enabled", False)
        await save_invite_config(guild_id, {"enabled": not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_role(guild_id, bot, author_id):
    """Gère le bouton de suppression de rôle."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_invite_config(guild_id, {"reward_role_id": None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


async def _validate_role_for_invite(interaction: Interaction, role_id: int) -> Optional[str]:
    """Vérification du rôle."""
    guild = interaction.guild
    role = guild.get_role(role_id) if guild else None
    if role is None:
        return "Rôle introuvable."
    if role.is_default():
        return "Le rôle **everyone** ne peut pas être utilisé."
    if role.managed:
        return "Ce rôle est **géré** par une intégration et ne peut pas être attribué."
    if guild.me is not None and role.position >= guild.me.top_role.position:
        return (
            f"Je ne peux pas attribuer {role.mention} : son rang est "
            f"**supérieur ou égal** au mien.\n-# Placez mon rôle plus haut dans la hiérarchie."
        )
    return None


def _cb_pick_role(guild_id, bot, author_id):
    """Gère le bouton du sélection du rôle."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        cfg = await load_invite_config(guild_id)

        async def _on_save(role_id: int) -> None:
            await save_invite_config(guild_id, {"reward_role_id": role_id})

        async def _build_return_view():
            return await create_invite_view(guild_id, bot, author_id)

        await interaction.response.edit_message(
            view=SelectPageView(
                kind="role",
                title="🎁 Rôle-récompense",
                description="-# Attribué automatiquement au seuil d'invitations.",
                current_value=cfg.get("reward_role_id"),
                owner_id=author_id,
                on_save=_on_save,
                build_return_view=_build_return_view,
                validate=_validate_role_for_invite,
            )
        )
    return cb


def _cb_edit_threshold(guild_id, bot, author_id):
    """Gère le bouton d'édition du nombre seuil."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        current = (await load_invite_config(guild_id)).get("reward_threshold", 10)

        async def on_submit(inter: Interaction, value: str):
            value = value.strip()
            try:
                n = int(value)
            except ValueError:
                await inter.response.send_message(
                    view=error_container("Le seuil doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n <= 0:
                await inter.response.send_message(
                    view=error_container("Le seuil doit être **supérieur à 0**."),
                    ephemeral=True,
                )
                return
            if n > 10_000:
                await inter.response.send_message(
                    view=error_container("Le seuil doit être **inférieur ou égal à 10 000**."),
                    ephemeral=True,
                )
                return
            await save_invite_config(guild_id, {"reward_threshold": n})
            await _rerender(inter, guild_id, bot, author_id)

        modal = TextModal(
            title="🎯 Modifier le seuil",
            label="Nombre d'invitations requis",
            placeholder="Ex : 10",
            default=str(current),
            min_length=1,
            max_length=6,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


# ============================================================
# 📑 CallBack
# ============================================================

class InviteConfigView:
    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot):
        view = await create_invite_view(guild_id, bot, author_id)
        
        if view is None:
            return error_container("**Impossible** de charger la __configuration__ (serveur introuvable).")
        return view