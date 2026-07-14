"""
views/birthday/config_view.py — Interface de configuration du système d'anniversaire.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.birthday_manager import (
    delete_user_birthday,
    get_all_for_guild,
    get_user_birthday,
    load_birthday_config,
    reset_birthday_config,
    save_birthday_config,
)
from views._components.base_view import BaseLayoutView
from views._components.paginated_view import PaginatedView
from views._components.select_page import SelectPageView
from utils.settings import settings

log = logging.getLogger(__name__)


# ============================================================
# 💻 Fonctions (UI)
# ============================================================

def _state_btn(active: bool) -> Button:
    """Bouton d'état ON/OFF."""
    return Button(
        label="Activé" if active else "Désactivé",
        style=ButtonStyle.success if active else ButtonStyle.danger,
        emoji="<:valider:1495444292867723284>" if active else "<:annuler:1495444256754761979>",
    )


def _channel_label(channel_id: Optional[int], guild: discord.Guild) -> str:
    """Affichage du salon."""
    if channel_id is None:
        return "`Non configuré`"
    ch = guild.get_channel(channel_id)
    return ch.mention if ch is not None else f"`Salon supprimé (ID {channel_id})`"


def _role_label(role_id: Optional[int], guild: discord.Guild) -> str:
    """Affichage du rôle."""
    if role_id is None:
        return "`Non configuré`"
    role = guild.get_role(role_id)
    return role.mention if role is not None else f"`Rôle supprimé (ID {role_id})`"


# ============================================================
# 🧩 Construction de la view 
# ============================================================

async def create_birthday_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[BaseLayoutView]:
    """Construction de l'interface principale."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[Birthday] Guild %s introuvable dans le cache", guild_id)
        return None

    cfg = await load_birthday_config(guild_id)
    enabled = cfg.get("enabled", False)
    channel_id = cfg.get("channel_id")
    role_id = cfg.get("role_id")

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    container.add_item(TextDisplay(f"# 🎂 Configuration Anniversaires"))
    container.add_item(Separator())

    btn_sys = _state_btn(enabled)
    btn_sys.callback = _cb_toggle(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay("**🔘 Statut du système**\n-# Active ou désactive le système d'anniversaire."),
        accessory=btn_sys,
    ))
    container.add_item(Separator())

    if channel_id is not None:
        ch_btn = Button(label="Retirer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
        ch_btn.callback = _cb_clear_channel(guild_id, bot, author_id)
    else:
        ch_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
        ch_btn.callback = _cb_pick_channel(guild_id, bot, author_id)

    container.add_item(Section(
        TextDisplay(
            f"**📢 Salon d'annonce**\n-# Salon où les vœux sont postés à 7h00.\n"
            f"-# Actuel : {_channel_label(channel_id, guild)}"
        ),
        accessory=ch_btn,
    ))
    container.add_item(Separator())

    if role_id is not None:
        role_btn = Button(label="Retirer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
        role_btn.callback = _cb_clear_role(guild_id, bot, author_id)
    else:
        role_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
        role_btn.callback = _cb_pick_role(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"**🎈 Rôle anniversaire**\n-# Attribué de **7h00** à **23h59** le jour J.\n"
            f"-# Actuel : {_role_label(role_id, guild)}"
        ),
        accessory=role_btn,
    ))
    container.add_item(Separator())

    container.add_item(TextDisplay("### 🗂️ Gestion des dates"))

    btn_view = Button(label="Voir", style=ButtonStyle.secondary, emoji="<:info:1495443961144152094>")
    btn_view.callback = _cb_view_all(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay("**📋 Dates enregistrées**\n-# Consulte la liste des anniversaires du serveur."),
        accessory=btn_view,
    ))
    container.add_item(Separator())

    btn_del = Button(label="Choisir un membre", style=ButtonStyle.secondary, emoji="<:parametre:1495444004328706059>")
    btn_del.callback = _cb_delete_user(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay("**🗑️ Supprimer une date**\n-# Retire la date enregistrée par un membre."),
        accessory=btn_del,
    ))
    container.add_item(Separator())


    btn_reset = Button(label="Réinitialiser", style=ButtonStyle.danger, emoji="<:recharger:1495444327629852703>")
    btn_reset.callback = _cb_reset(guild_id, bot, author_id)
    doc_btn = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
    container.add_item(ActionRow(btn_reset, doc_btn))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🛠️ CallBack
# ============================================================

def _guard(author_id: Optional[int]):
    """Vérification de permissions (auteur & administrateur)."""
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
    """Met à jour l'interface de configuration."""
    new_view = await create_birthday_view(guild_id, bot, author_id)
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
    """Gère le bouton d'activation ON/OFF."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_birthday_config(guild_id)).get("enabled", False)
        await save_birthday_config(guild_id, {"enabled": not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_channel(guild_id, bot, author_id):
    """Gère le bouton de suppression de salon."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_birthday_config(guild_id, {"channel_id": None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_role(guild_id, bot, author_id):
    """Gère le bouton de suppression de rôle."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_birthday_config(guild_id, {"role_id": None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


async def _validate_channel_for_birthday(interaction: Interaction, channel_id: int) -> Optional[str]:
    """Vérification des permissions dans le salon d'annonce."""
    channel = interaction.guild.get_channel(channel_id) if interaction.guild else None
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return "Salon texte introuvable."
    me = interaction.guild.me
    if me is not None:
        perms = channel.permissions_for(me)
        if not (perms.send_messages and perms.view_channel):
            return f"Je n'ai pas la permission d'écrire dans {channel.mention}."
    return None


def _cb_pick_channel(guild_id, bot, author_id):
    """Gère le menu de sélection du salon d'annonce"""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        cfg = await load_birthday_config(guild_id)

        async def _on_save(channel_id: int) -> None:
            await save_birthday_config(guild_id, {"channel_id": channel_id})

        async def _build_return_view():
            return await create_birthday_view(guild_id, bot, author_id)

        await interaction.response.edit_message(
            view=SelectPageView(
                kind="channel",
                title="📢 Salon d'annonce",
                description="-# Sélectionne le salon où les vœux seront postés à 7h00.",
                current_value=cfg.get("channel_id"),
                owner_id=author_id,
                on_save=_on_save,
                build_return_view=_build_return_view,
                validate=_validate_channel_for_birthday,
            )
        )
    return cb


async def _validate_role_for_birthday(interaction: Interaction, role_id: int) -> Optional[str]:
    """Vérification de la validité du rôle anniversaire."""

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
    """Gère le menu de sélection du rôle anniversaire."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        cfg = await load_birthday_config(guild_id)

        async def _on_save(role_id: int) -> None:
            await save_birthday_config(guild_id, {"role_id": role_id})

        async def _build_return_view():
            return await create_birthday_view(guild_id, bot, author_id)

        await interaction.response.edit_message(
            view=SelectPageView(
                kind="role",
                title="🎈 Rôle anniversaire",
                description="-# Attribué automatiquement de 7h00 à 00h00 le jour J.",
                current_value=cfg.get("role_id"),
                owner_id=author_id,
                on_save=_on_save,
                build_return_view=_build_return_view,
                validate=_validate_role_for_birthday,
            )
        )
    return cb


def _cb_view_all(guild_id, bot, author_id):
    """Gestion de la liste des dates d'anniversaire."""

    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        guild = bot.get_guild(guild_id)
        if guild is None:
            await interaction.response.send_message(
                view=error_container("Serveur **introuvable**."), ephemeral=True
            )
            return
        users = await get_all_for_guild(guild_id)

        async def on_back(back_inter: Interaction):
            await _rerender(back_inter, guild_id, bot, author_id)
        btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
        btn_back.callback = on_back

        if not users:
            empty_view = BaseLayoutView(owner_id=author_id, timeout=300)
            c = Container()
            c.add_item(TextDisplay("# 📋 Dates enregistrées"))
            c.add_item(Separator())
            c.add_item(TextDisplay("-# Aucune date d'anniversaire enregistrée sur ce serveur."))
            c.add_item(Separator())
            c.add_item(ActionRow(btn_back))
            c.add_item(Separator())
            c.add_item(TextDisplay("-# GuideOn Studio"))
            empty_view.add_item(c)
            await interaction.response.edit_message(view=empty_view)
            return

        users_sorted = sorted(users, key=lambda u: (u["month"], u["day"]))
        view = _BirthdayAdminListView(
            users_sorted, guild=guild, owner_id=author_id or interaction.user.id,
            back_button=btn_back,
        )
        await interaction.response.edit_message(view=view)
    return cb


def _build_delete_confirm_view(guild_id, bot, author_id, uid: int, existing: dict) -> BaseLayoutView:
    """Page de confirmation avant suppression."""

    async def _on_confirm(interaction: Interaction):
        await delete_user_birthday(guild_id, uid)
        await _rerender(interaction, guild_id, bot, author_id)

    async def _on_cancel(interaction: Interaction):
        await _rerender(interaction, guild_id, bot, author_id)

    year_txt = f"/{existing['year']}" if existing.get("year") else ""

    view = BaseLayoutView(owner_id=author_id, timeout=180)
    c = Container()
    c.add_item(TextDisplay("# <:supprimer:1495444051623809075> Confirmer la suppression"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"-# Tu vas supprimer la date d'anniversaire de <@{uid}>\n"
        f"-# Date enregistrée : **{existing['day']:02d}/{existing['month']:02d}{year_txt}**"
    ))
    c.add_item(Separator())

    btn_confirm = Button(label="Supprimer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
    btn_confirm.callback = _on_confirm
    btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="<:annuler:1495444256754761979>")
    btn_cancel.callback = _on_cancel
    c.add_item(ActionRow(btn_confirm, btn_cancel))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view


def _cb_delete_user(guild_id, bot, author_id):
    """Gère le bouton de suppression de la date d'un utilisateur."""

    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        picked: dict[str, int] = {}

        async def _validate_user(inter: Interaction, uid: int) -> Optional[str]:
            existing = await get_user_birthday(guild_id, uid)
            if existing is None:
                return f"<@{uid}> n'a **aucune date** enregistrée."
            return None

        async def _on_save(uid: int) -> None:
            picked["uid"] = uid

        async def _build_return_view():
            uid = picked.get("uid")
            if uid is None:
                return await create_birthday_view(guild_id, bot, author_id)
            existing = await get_user_birthday(guild_id, uid)
            if existing is None:
                return await create_birthday_view(guild_id, bot, author_id)
            return _build_delete_confirm_view(guild_id, bot, author_id, uid, existing)

        await interaction.response.edit_message(
            view=SelectPageView(
                kind="user",
                title="🗑️ Supprimer une date",
                description="-# Sélectionne le membre dont supprimer la date enregistrée.",
                owner_id=author_id,
                on_save=_on_save,
                build_return_view=_build_return_view,
                validate=_validate_user,
            )
        )
    return cb


def _cb_reset(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def _on_confirm(inter: Interaction):
            await reset_birthday_config(guild_id)
            await _rerender(inter, guild_id, bot, author_id)

        async def _on_cancel(inter: Interaction):
            await _rerender(inter, guild_id, bot, author_id)

        view = BaseLayoutView(owner_id=author_id, timeout=120)
        c = Container()
        c.add_item(TextDisplay("# <:recharger:1495444327629852703> Réinitialiser"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "-# Cette action désactive le système et retire le salon et le rôle configurés.\n"
            "-# Les dates déjà enregistrées par les membres ne sont **pas supprimées**."
        ))
        c.add_item(Separator())
        btn_confirm = Button(label="Réinitialiser", style=ButtonStyle.danger, emoji="<:recharger:1495444327629852703>")
        btn_confirm.callback = _on_confirm
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="<:annuler:1495444256754761979>")
        btn_cancel.callback = _on_cancel
        c.add_item(ActionRow(btn_confirm, btn_cancel))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        view.add_item(c)

        await interaction.response.edit_message(view=view)
    return cb


# ============================================================
# 📋 Liste des dates
# ============================================================

class _BirthdayAdminListView(PaginatedView):
    """Liste de toutes les dates enregistrées."""

    def __init__(self, users: list[dict], *, guild: discord.Guild, owner_id: int, back_button: Optional[Button] = None):
        self.guild = guild
        self.back_button = back_button
        super().__init__(users, per_page=15, owner_id=owner_id)

    def build_page_container(self, page_items: list) -> Container:
        container = Container()
        container.add_item(TextDisplay(f"# 📋 Dates enregistrées · {self.guild.name}"))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# Aucune date enregistrée."))
        else:
            lines: list[str] = []
            for u in page_items:
                member = self.guild.get_member(u["user_id"])
                display = member.mention if member else f"`utilisateur {u['user_id']} (parti)`"
                year_txt = f"/{u['year']}" if u.get("year") else ""
                lines.append(
                    f"-# 🎂 {display} — **{u['day']:02d}/{u['month']:02d}{year_txt}**"
                )
            container.add_item(TextDisplay("\n".join(lines)))

        if self.back_button is not None:
            container.add_item(Separator())
            container.add_item(ActionRow(self.back_button))

        return container


# ============================================================
# 📑 Class principale
# ============================================================

class BirthdayConfigView:
    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot):
        view = await create_birthday_view(guild_id, bot, author_id)
        if view is None:
            return error_container(
                "**Impossible** de charger la __configuration__ (serveur introuvable)."
            )
        return view