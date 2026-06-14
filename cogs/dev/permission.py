"""
Commande /dev permissions — Gére les permissions internes (DEV, STAFF, OP_ALPHA).
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Modal, Section, Separator, TextDisplay, TextInput

from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

from utils.managers.permission_manager import PermissionRole, add_entry, list_all, remove_entry
from utils.createur import is_creator


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 300


# ============================================================
# 🔐 Vérifications créateurs
# ============================================================

def _is_creator(interaction: discord.Interaction) -> bool:
    return is_creator(interaction.user.id)


async def _guard_creator(interaction: discord.Interaction) -> bool:
    if _is_creator(interaction):
        return True
    
    if interaction.response.is_done():
        await interaction.followup.send(
            view=error_container("Seuls les **créateurs** peuvent gérer les permissions."),
            ephemeral=True,
        )

    else:
        await interaction.response.send_message(
            view=error_container("Seuls les **créateurs** peuvent gérer les permissions."),
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

    container.add_item(TextDisplay("# <:erreur_cad:1495446243957018684> Gestion des permissions"))
    total = sum(len(v) for v in data.values())
    container.add_item(TextDisplay(f"-# {total} attribution(s) au total"))
    container.add_item(Separator())

    for role in PermissionRole:
        ids = data.get(role.value, [])
        if ids:
            liste = "\n".join(f"• <@{i}> · `{i}`" for i in ids)
        else:
            liste = "-# *aucun membre*"

        btn_add = Button(label="Ajouter", emoji="<:plus:1495444111505752154>", style=discord.ButtonStyle.success)
        btn_add.callback = _cb_add(bot, author_id, role)
        container.add_item(Section(
            TextDisplay(f"### {role.value}  ({len(ids)})\n{liste}"),
            accessory=btn_add,
        ))

        if ids:
            btn_remove = Button(label="Retirer", emoji="<:moins:1508532114465882285>", style=discord.ButtonStyle.danger)
            btn_remove.callback = _cb_remove(bot, author_id, role)
            container.add_item(ActionRow(btn_remove))

        container.add_item(Separator())

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
        self.action = action
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
        if not await _guard_creator(interaction):
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

        new_view = await create_permissions_view(self.bot, self.author_id)
        await interaction.response.edit_message(view=new_view)
        await interaction.followup.send(view=success_container(txt), ephemeral=True)


# ============================================================
# 🔄 Callbacks
# ============================================================

def _cb_add(bot, author_id: int, role: PermissionRole):
    async def cb(interaction: discord.Interaction):
        if not await _guard_creator(interaction):
            return
        await interaction.response.send_modal(IdModal(role, "add", bot, author_id))
    return cb


def _cb_remove(bot, author_id: int, role: PermissionRole):
    async def cb(interaction: discord.Interaction):
        if not await _guard_creator(interaction):
            return
        await interaction.response.send_modal(IdModal(role, "remove", bot, author_id))
    return cb


# ============================================================
# 🧭 Commande principale
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="permissions", description="🔐 [DEV] Gérer les permissions internes du bot")
async def permissions(interaction: Interaction):

    # 🔐 Vérification des permissions.
    if not await _guard_creator(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_permissions"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_permissions")

    # 🧩 Création interface.
    try:
        view = await create_permissions_view(interaction.client, interaction.user.id)

    except Exception:
        log.exception("[DEV PERMISSIONS] Erreur interface permissions")
        await interaction.followup.send(
            view=error_container("Impossible de charger l'**interface des permissions**."),
            ephemeral=True,
        )
        return

    # 📤 Envoi de l'interface.
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@permissions.error
async def permissions_error(interaction: Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)