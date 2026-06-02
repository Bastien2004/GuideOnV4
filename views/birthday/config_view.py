"""
views/birthday/config_view.py — Panneau /birthday config.

Pattern identique à views/invite/config_view.py et views/bienvenue/config_view.py :
- fonction create_birthday_view(guild_id, bot, author_id) qui construit un LayoutView
- _guard(author_id) vérifie auteur + admin
- callbacks fermés _cb_*(...) ; helper _rerender

Contenu du panneau :
- État du système (toggle ON/OFF) avec diagnostic
- Salon d'annonce (ChannelSelect ephemeral)
- Rôle anniversaire (RoleSelect ephemeral, garde-fous, bouton retirer)
- Voir toutes les dates enregistrées (ouvre une sous-vue paginée)
- Supprimer la date d'un membre (UserSelect ephemeral + confirm)
- Bouton Réinitialiser
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.birthday_manager import (
    delete_user_birthday,
    get_all_for_guild,
    get_user_birthday,
    load_birthday_config,
    reset_birthday_config,
    save_birthday_config,
)
from views._components.channel_select import ChannelSelect
from views._components.paginated_view import PaginatedView
from views._components.role_select import RoleSelect
from views._components.user_select import UserSelect

log = logging.getLogger(__name__)


# ======================================================
# =================== UI HELPERS =======================
# ======================================================

def _state_btn(active: bool) -> Button:
    return Button(
        label="Activé" if active else "Désactivé",
        style=ButtonStyle.success if active else ButtonStyle.danger,
        emoji="🟢" if active else "🔴",
    )


def _channel_label(channel_id: Optional[int], guild: discord.Guild) -> str:
    if channel_id is None:
        return "`aucun salon`"
    ch = guild.get_channel(channel_id)
    return ch.mention if ch is not None else f"`ID {channel_id} (salon introuvable)`"


def _role_label(role_id: Optional[int], guild: discord.Guild) -> str:
    if role_id is None:
        return "`aucun rôle`"
    role = guild.get_role(role_id)
    return role.mention if role is not None else f"`ID {role_id} (rôle introuvable)`"


# ======================================================
# =============== CONSTRUCTION DE LA VUE ===============
# ======================================================

async def create_birthday_view(
    guild_id: int, bot, author_id: Optional[int] = None
) -> Optional[LayoutView]:
    """Construit l'interface /birthday config. None si guild introuvable."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("Guild %s introuvable dans le cache", guild_id)
        return None

    cfg = await load_birthday_config(guild_id)
    enabled = cfg.get("enabled", False)
    channel_id = cfg.get("channel_id")
    role_id = cfg.get("role_id")

    # Diagnostic
    issues: list[str] = []
    if enabled:
        if channel_id is None:
            issues.append("aucun salon configuré")
        elif guild.get_channel(channel_id) is None:
            issues.append("salon introuvable")
    if not enabled:
        etat = "-# ⚪ Système **désactivé**"
    elif issues:
        etat = "-# ⚠️ Actif mais incomplet : " + ", ".join(issues)
    else:
        etat = "-# ✅ Système **opérationnel**"

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(f"# 🎂 Configuration · Anniversaires\n{etat}"))
    container.add_item(Separator())

    # --- État du système ---
    btn_sys = _state_btn(enabled)
    btn_sys.callback = _cb_toggle(guild_id, bot, author_id)
    container.add_item(Section(TextDisplay("**État du système**"), accessory=btn_sys))
    container.add_item(Separator())

    # --- Salon d'annonce ---
    btn_pick_ch = Button(label="Choisir un salon", style=ButtonStyle.secondary, emoji="📢")
    btn_pick_ch.callback = _cb_pick_channel(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"### 📢 Salon d'annonce\n-# Salon où les vœux sont postés à 7h00.\n"
            f"-# Actuel : {_channel_label(channel_id, guild)}"
        ),
        accessory=btn_pick_ch,
    ))
    if channel_id is not None:
        btn_clear_ch = Button(label="Retirer le salon", style=ButtonStyle.danger, emoji="🗑️")
        btn_clear_ch.callback = _cb_clear_channel(guild_id, bot, author_id)
        container.add_item(ActionRow(btn_clear_ch))
    container.add_item(Separator())

    # --- Rôle anniversaire ---
    btn_pick_role = Button(label="Choisir un rôle", style=ButtonStyle.secondary, emoji="🎈")
    btn_pick_role.callback = _cb_pick_role(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"### 🎈 Rôle anniversaire\n-# Attribué de **7h00** à **00h00** le jour J.\n"
            f"-# Actuel : {_role_label(role_id, guild)}"
        ),
        accessory=btn_pick_role,
    ))
    if role_id is not None:
        btn_clear_role = Button(label="Retirer le rôle", style=ButtonStyle.danger, emoji="🗑️")
        btn_clear_role.callback = _cb_clear_role(guild_id, bot, author_id)
        container.add_item(ActionRow(btn_clear_role))
    container.add_item(Separator())

    # --- Actions admin (voir / supprimer) ---
    btn_view = Button(label="Voir les dates", style=ButtonStyle.secondary, emoji="📋")
    btn_view.callback = _cb_view_all(guild_id, bot, author_id)
    btn_del = Button(label="Supprimer une date", style=ButtonStyle.secondary, emoji="🗑️")
    btn_del.callback = _cb_delete_user(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay("### 🗂️ Gestion des dates\n-# Consulte ou supprime les anniversaires enregistrés."),
        accessory=btn_view,
    ))
    container.add_item(ActionRow(btn_del))
    container.add_item(Separator())

    # --- Reset ---
    btn_reset = Button(label="Réinitialiser", style=ButtonStyle.danger, emoji="♻️")
    btn_reset.callback = _cb_reset(guild_id, bot, author_id)
    container.add_item(ActionRow(btn_reset))

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
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_birthday_config(guild_id)).get("enabled", False)
        await save_birthday_config(guild_id, {"enabled": not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_reset(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await reset_birthday_config(guild_id)
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_channel(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_birthday_config(guild_id, {"channel_id": None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_role(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_birthday_config(guild_id, {"role_id": None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_pick_channel(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def on_select(sel: Interaction, channel_id: int):
            ch = sel.guild.get_channel(channel_id)
            if ch is None:
                await sel.response.send_message(
                    view=error_container("Salon **introuvable**."),
                    ephemeral=True,
                )
                return
            me = sel.guild.me
            if me is not None:
                perms = ch.permissions_for(me)
                if not perms.send_messages:
                    await sel.response.send_message(
                        view=error_container(
                            f"Je n'ai **pas la permission** d'écrire dans {ch.mention}."
                        ),
                        ephemeral=True,
                    )
                    return
            await save_birthday_config(guild_id, {"channel_id": channel_id})
            # Retour direct à la vue principale (qui affichera le nouveau salon)
            new_view = await create_birthday_view(guild_id, bot, author_id)
            await sel.response.edit_message(view=new_view)

        async def on_cancel(cancel_inter: Interaction):
            new_view = await create_birthday_view(guild_id, bot, author_id)
            await cancel_inter.response.edit_message(view=new_view)

        select = ChannelSelect(
            placeholder="Sélectionner un salon",
            on_select=on_select,
            channel_types=[discord.ChannelType.text],
        )
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
        btn_cancel.callback = on_cancel

        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay("# 📢 Choisir le salon d'annonce"))
        c.add_item(TextDisplay("-# Sélectionne le salon où les vœux seront postés à 7h00."))
        c.add_item(Separator())
        c.add_item(ActionRow(select))
        c.add_item(Separator())
        c.add_item(ActionRow(btn_cancel))
        temp.add_item(c)

        # ÉDITE le message parent au lieu d'en ouvrir un nouveau
        await interaction.response.edit_message(view=temp)
    return cb


def _cb_pick_role(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def on_select(sel: Interaction, role_ids: list[int]):
            if not role_ids:
                return
            role_id = role_ids[0]
            role = sel.guild.get_role(role_id)
            if role is None:
                await sel.response.send_message(
                    view=error_container("Rôle **introuvable**."),
                    ephemeral=True,
                )
                return
            if role.is_default():
                await sel.response.send_message(
                    view=error_container("Le rôle **@everyone** ne peut pas être utilisé."),
                    ephemeral=True,
                )
                return
            if role.managed:
                await sel.response.send_message(
                    view=error_container(
                        "Ce rôle est **géré** par une intégration et ne peut pas être attribué."
                    ),
                    ephemeral=True,
                )
                return
            me = sel.guild.me
            if me is not None and role >= me.top_role:
                await sel.response.send_message(
                    view=error_container(
                        f"Je ne peux pas attribuer {role.mention} : son rang est "
                        f"**supérieur ou égal** au mien."
                    ),
                    ephemeral=True,
                )
                return

            await save_birthday_config(guild_id, {"role_id": role_id})
            new_view = await create_birthday_view(guild_id, bot, author_id)
            await sel.response.edit_message(view=new_view)

        async def on_cancel(cancel_inter: Interaction):
            new_view = await create_birthday_view(guild_id, bot, author_id)
            await cancel_inter.response.edit_message(view=new_view)

        select = RoleSelect(
            placeholder="Sélectionner un rôle",
            on_select=on_select,
            min_values=1,
            max_values=1,
        )
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
        btn_cancel.callback = on_cancel

        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay("# 🎈 Choisir le rôle anniversaire"))
        c.add_item(TextDisplay("-# Attribué de 7h00 à 00h00 le jour J."))
        c.add_item(Separator())
        c.add_item(ActionRow(select))
        c.add_item(Separator())
        c.add_item(ActionRow(btn_cancel))
        temp.add_item(c)

        await interaction.response.edit_message(view=temp)
    return cb


def _cb_view_all(guild_id, bot, author_id):
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

        # Bouton de retour à la vue principale
        async def on_back(back_inter: Interaction):
            new_view = await create_birthday_view(guild_id, bot, author_id)
            await back_inter.response.edit_message(view=new_view)
        btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="↩️")
        btn_back.callback = on_back

        if not users:
            # Vue minimale avec juste un message + bouton retour
            empty_view = LayoutView(timeout=300)
            c = Container()
            c.add_item(TextDisplay("# 📋 Dates enregistrées"))
            c.add_item(Separator())
            c.add_item(TextDisplay("-# Aucune date d'anniversaire enregistrée sur ce serveur."))
            c.add_item(Separator())
            c.add_item(ActionRow(btn_back))
            empty_view.add_item(c)
            await interaction.response.edit_message(view=empty_view)
            return

        # Tri stable par (mois, jour)
        users_sorted = sorted(users, key=lambda u: (u["month"], u["day"]))
        view = _BirthdayAdminListView(
            users_sorted, guild=guild, owner_id=author_id or interaction.user.id,
            back_button=btn_back,
        )
        await interaction.response.edit_message(view=view)
    return cb


def _cb_delete_user(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def back_to_main(inter: Interaction):
            new_view = await create_birthday_view(guild_id, bot, author_id)
            await inter.response.edit_message(view=new_view)

        async def on_select(sel: Interaction, user_ids: list[int]):
            if not user_ids:
                return
            uid = user_ids[0]
            existing = await get_user_birthday(guild_id, uid)

            if existing is None:
                # Pas de date → message d'info dans la vue + retour
                empty = LayoutView(timeout=120)
                c = Container()
                c.add_item(TextDisplay("# 🗑️ Suppression"))
                c.add_item(Separator())
                c.add_item(TextDisplay(
                    f"-# ℹ️ <@{uid}> n'a **aucune date** enregistrée."
                ))
                c.add_item(Separator())
                btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="↩️")
                btn_back.callback = back_to_main
                c.add_item(ActionRow(btn_back))
                empty.add_item(c)
                await sel.response.edit_message(view=empty)
                return

            # Vue de confirmation INTÉGRÉE (pas de ConfirmView séparé)
            async def on_confirm(conf_inter: Interaction):
                await delete_user_birthday(guild_id, uid)
                new_view = await create_birthday_view(guild_id, bot, author_id)
                await conf_inter.response.edit_message(view=new_view)

            year_txt = f"/{existing['year']}" if existing.get("year") else ""
            confirm_view = LayoutView(timeout=120)
            c = Container()
            c.add_item(TextDisplay("# 🗑️ Confirmer la suppression"))
            c.add_item(Separator())
            c.add_item(TextDisplay(
                f"-# Tu vas supprimer la date d'anniversaire de <@{uid}>\n"
                f"-# Date enregistrée : **{existing['day']:02d}/{existing['month']:02d}{year_txt}**"
            ))
            c.add_item(Separator())
            btn_confirm = Button(label="Supprimer", style=ButtonStyle.danger, emoji="🗑️")
            btn_confirm.callback = on_confirm
            btn_cancel_inner = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
            btn_cancel_inner.callback = back_to_main
            c.add_item(ActionRow(btn_confirm, btn_cancel_inner))
            confirm_view.add_item(c)
            await sel.response.edit_message(view=confirm_view)

        select = UserSelect(
            placeholder="Sélectionner un membre",
            on_select=on_select,
            min_values=1,
            max_values=1,
        )
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
        btn_cancel.callback = back_to_main

        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay("# 🗑️ Supprimer une date"))
        c.add_item(TextDisplay("-# Sélectionne le membre dont supprimer la date."))
        c.add_item(Separator())
        c.add_item(ActionRow(select))
        c.add_item(Separator())
        c.add_item(ActionRow(btn_cancel))
        temp.add_item(c)

        await interaction.response.edit_message(view=temp)
    return cb


# ======================================================
# ====== SOUS-VUE : liste paginée des dates admin ======
# ======================================================

class _BirthdayAdminListView(PaginatedView):
    """Liste paginée de TOUTES les dates enregistrées (vue admin)."""

    def __init__(
        self, users: list[dict], *, guild: discord.Guild, owner_id: int,
        back_button: Optional[Button] = None,
    ):
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

        # Bouton retour si fourni (en plus des contrôles de pagination héritée)
        if self.back_button is not None:
            container.add_item(Separator())
            container.add_item(ActionRow(self.back_button))

        return container


# ======================================================
# ========= COMPAT COMMANDE : BirthdayConfigView =======
# ======================================================

class BirthdayConfigView:
    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot) -> LayoutView:
        view = await create_birthday_view(guild_id, bot, author_id)
        if view is None:
            return error_container(
                "**Impossible** de charger la __configuration__ (serveur introuvable)."
            )
        return view