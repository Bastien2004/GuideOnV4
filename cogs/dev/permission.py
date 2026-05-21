"""
Commande /dev permissions — Gérer les rôles internes (DEV, STAFF, OP_ALPHA, ADMIN).

100% CV2 (LayoutView/Container). Restreinte aux super-admins (utils.super_admins.SUPER_ADMIN_IDS).
Permet de voir la liste par rôle et d'ajouter/retirer des IDs.

Les super-admins ne sont PAS modifiables ici (ils vivent dans .env).
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import (
    ActionRow, Button, Container, LayoutView, Modal, Section, Separator,
    TextDisplay, TextInput,
)

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.managers.permission_manager import (
    PermissionRole, add_entry, list_all, remove_entry, role_from_str,
)

from utils.createur import is_creator
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 300


# ============================================================
# 🔐 Garde super-admin
# ============================================================

def _is_super_admin(interaction: discord.Interaction) -> bool:
    return is_creator(interaction.user.id)


async def _guard_super(interaction: discord.Interaction) -> bool:
    if _is_super_admin(interaction):
        return True
    if interaction.response.is_done():
        await interaction.followup.send(
            view=error_container("Seuls les **super-administrateurs** peuvent gérer les permissions."),
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            view=error_container("Seuls les **super-administrateurs** peuvent gérer les permissions."),
            ephemeral=True,
        )
    return False


# ============================================================
# 🧱 Vue principale
# ============================================================

async def create_permissions_view(bot, author_id: int) -> LayoutView:
    data = await list_all()

    view = LayoutView(timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay("# 🔐 Gestion des permissions"))
    total = sum(len(v) for v in data.values())
    container.add_item(TextDisplay(f"-# {total} attribution(s) au total"))
    container.add_item(Separator())

    for role in PermissionRole:
        ids = data.get(role.value, [])
        # Affichage : on mentionne les users (Discord résout l'ID en pseudo)
        if ids:
            liste = "\n".join(f"• <@{i}> · `{i}`" for i in ids)
        else:
            liste = "-# *aucun membre*"

        btn_add = Button(label="Ajouter", emoji="➕", style=discord.ButtonStyle.success)
        btn_add.callback = _cb_add(bot, author_id, role)
        container.add_item(Section(
            TextDisplay(f"### {role.value}  ({len(ids)})\n{liste}"),
            accessory=btn_add,
        ))

        if ids:
            btn_remove = Button(label="Retirer", emoji="➖", style=discord.ButtonStyle.danger)
            btn_remove.callback = _cb_remove(bot, author_id, role)
            container.add_item(ActionRow(btn_remove))

        container.add_item(Separator())

    container.add_item(TextDisplay("-# Les super-admins (.env) ne sont pas listés ici."))
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📝 Modals
# ============================================================

class IdModal(Modal):
    def __init__(self, role: PermissionRole, action: str, bot, author_id: int):
        super().__init__(title=f"{action} — {role.value}")
        self.role = role
        self.action = action  # "add" | "remove"
        self.bot = bot
        self.author_id = author_id
        self.id_input = TextInput(
            label="ID Discord",
            placeholder="123456789012345678",
            required=True,
            min_length=15,
            max_length=25,
        )
        self.add_item(self.id_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not await _guard_super(interaction):
            return

        raw = self.id_input.value.strip()
        if not raw.isdigit():
            await interaction.response.send_message(
                view=error_container("L'ID doit être numérique."), ephemeral=True
            )
            return

        if self.action == "add":
            created = await add_entry(self.role, raw)
            txt = (f"<@{raw}> ajouté à **{self.role.value}**." if created
                   else f"<@{raw}> est déjà dans **{self.role.value}**.")
        else:
            deleted = await remove_entry(self.role, raw)
            txt = (f"<@{raw}> retiré de **{self.role.value}**." if deleted
                   else f"<@{raw}> n'était pas dans **{self.role.value}**.")

        # Rafraîchit la vue principale
        new_view = await create_permissions_view(self.bot, self.author_id)
        await interaction.response.edit_message(view=new_view)
        await interaction.followup.send(view=success_container(txt), ephemeral=True)


# ============================================================
# 🔄 Callbacks
# ============================================================

def _cb_add(bot, author_id: int, role: PermissionRole):
    async def cb(interaction: discord.Interaction):
        if not await _guard_super(interaction):
            return
        await interaction.response.send_modal(IdModal(role, "add", bot, author_id))
    return cb


def _cb_remove(bot, author_id: int, role: PermissionRole):
    async def cb(interaction: discord.Interaction):
        if not await _guard_super(interaction):
            return
        await interaction.response.send_modal(IdModal(role, "remove", bot, author_id))
    return cb


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="permissions", description="🔐 [DEV] Gérer les permissions internes du bot")
async def permissions(interaction: Interaction):
    # 🔐 Restreint aux super-admins
    if not await _guard_super(interaction):
        return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "dev_permissions"):
        return

    await tracker_commande(interaction, "dev_permissions")

    try:
        view = await create_permissions_view(interaction.client, interaction.user.id)
    except Exception:
        log.exception("Erreur interface permissions")
        await interaction.followup.send(
            view=error_container("Impossible de charger l'interface des permissions."),
            ephemeral=True,
        )
        return

    await interaction.followup.send(view=view, ephemeral=True)


@permissions.error
async def permissions_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)