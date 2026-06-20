"""
views/ticket/lifecycle.py — Logique de cycle de vie d'un ticket.
"""
from __future__ import annotations

import logging
import time

import discord
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container, info_container, success_container
from utils.managers import ticket_manager as tm
from views.ticket._helpers import (
    WAKEUP_COOLDOWN_SECONDS,
    closed_name,
    is_staff,
    is_staff_or_creator,
    rename_cooldown_remaining,
    strip_closed_prefix,
    try_rename,
)
from views.ticket.transcript import do_delete_ticket

log = logging.getLogger(__name__)

REOPEN_PREFIX = "ticket_reopen:"
DELCLOSED_PREFIX = "ticket_delclosed:"


# ============================================================
# 🔒 Fermeture
# ============================================================

async def handle_close(
    interaction: discord.Interaction, channel_id: int, *, staff_only: bool = False
) -> None:
    """Ferme un ticket : vérifs → rename closed- → catégorie fermée → vue Réouvrir.

    staff_only=True (commande /ticket close) : seul le staff peut fermer.
    staff_only=False (bouton Fermer du welcome) : staff OU créateur, comme V3.
    """
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id

    ticket = await tm.get_ticket(channel_id)
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Vous n'êtes pas dans un **ticket**."), ephemeral=True
        )
    if ticket.get("closed"):
        return await interaction.followup.send(
            view=error_container("Ce ticket est déjà fermé."), ephemeral=True
        )

    allowed = (
        await is_staff(interaction, ticket, guild_id)
        if staff_only
        else await is_staff_or_creator(interaction, ticket, guild_id)
    )
    if not allowed:
        return await interaction.followup.send(
            view=error_container("Action non autorisée."), ephemeral=True
        )

    rem = rename_cooldown_remaining(ticket)
    if rem > 0:
        return await interaction.followup.send(
            view=error_container(f"Limite Discord : attendez **{rem // 60}m {rem % 60}s**."),
            ephemeral=True,
        )

    await _close_ticket(interaction, ticket, guild_id)


async def _close_ticket(interaction: discord.Interaction, ticket: dict, guild_id: int) -> None:
    channel = interaction.channel
    panel = await tm.get_panel(guild_id, ticket["panel_id"])

    # Masquer le créateur
    creator = interaction.guild.get_member(ticket["creator_id"])
    if creator:
        try:
            await channel.set_permissions(creator, view_channel=False)
        except discord.HTTPException:
            pass

    await try_rename(channel, closed_name(ticket["original_name"]))

    # Déplacer en catégorie fermée
    closed_cat = interaction.guild.get_channel(panel.get("closed_category_id")) if panel else None
    if closed_cat:
        try:
            await channel.edit(category=closed_cat)
        except discord.HTTPException:
            pass

    await tm.update_ticket(channel.id, closed=True, last_rename_at=int(time.time()))
    # open_count est décrémenté à la suppression définitive (comme V3). À la
    # fermeture on garde le ticket comptabilisé "ouvert" jusqu'au delete final.

    await interaction.followup.send(view=ReopenView(channel.id))


# ============================================================
# 🔓 Réouverture
# ============================================================

class ReopenView(LayoutView):
    """Vue postée après fermeture : Réouvrir / Supprimer (persistante)."""

    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        c = Container()
        c.add_item(TextDisplay("# 🔒 Ticket Fermé"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Le salon a été archivé. Réouvrez-le ou supprimez-le ci-dessous."
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(
            ReopenButton(channel_id),
            DeleteFromClosedButton(channel_id),
        ))
        self.add_item(c)


class ReopenButton(Button):
    def __init__(self, channel_id: int):
        super().__init__(
            label="Réouvrir", emoji="🔓", style=discord.ButtonStyle.success,
            custom_id=f"{REOPEN_PREFIX}{channel_id}",
        )
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id

        ticket = await tm.get_ticket(self.channel_id)
        if not ticket:
            return await interaction.followup.send(
                view=error_container("Ticket introuvable."), ephemeral=True
            )
        if not ticket.get("closed"):
            return await interaction.followup.send(
                view=error_container("Ce ticket est déjà ouvert."), ephemeral=True
            )
        if not await is_staff(interaction, ticket, guild_id):
            return await interaction.followup.send(
                view=error_container("La réouverture est réservée au staff."),
                ephemeral=True,
            )

        rem = rename_cooldown_remaining(ticket)
        if rem > 0:
            return await interaction.followup.send(
                view=error_container(f"Limite Discord : attendez **{rem // 60}m {rem % 60}s**."),
                ephemeral=True,
            )

        panel = await tm.get_panel(guild_id, ticket["panel_id"])
        cat = interaction.guild.get_channel(panel.get("ticket_category_id")) if panel else None
        if cat:
            try:
                await interaction.channel.edit(category=cat)
            except discord.HTTPException:
                pass

        await try_rename(interaction.channel, ticket["original_name"])

        creator = interaction.guild.get_member(ticket["creator_id"])
        if creator:
            try:
                await interaction.channel.set_permissions(
                    creator, view_channel=True, send_messages=True, read_message_history=True
                )
            except discord.HTTPException:
                pass

        await tm.update_ticket(
            self.channel_id, closed=False, last_rename_at=int(time.time())
        )

        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            view=success_container("Le ticket est réouvert.")
        )


# ============================================================
# 🗑️ Suppression depuis l'état fermé
# ============================================================

class DeleteFromClosedButton(Button):
    def __init__(self, channel_id: int):
        super().__init__(
            label="Supprimer", emoji="🗑️", style=discord.ButtonStyle.danger,
            custom_id=f"{DELCLOSED_PREFIX}{channel_id}",
        )
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        ticket = await tm.get_ticket(self.channel_id)
        if not ticket:
            return await interaction.followup.send(
                view=error_container("Ticket introuvable."), ephemeral=True
            )
        if not await is_staff(interaction, ticket, interaction.guild_id):
            return await interaction.followup.send(
                view=error_container("Cette action est __restreinte__ au **staff**."), ephemeral=True
            )
        await interaction.followup.send(
            view=DeleteConfirmView(self.channel_id), ephemeral=True
        )


# ============================================================
# ⚠️ Confirmation de suppression
# ============================================================

class DeleteConfirmView(LayoutView):
    def __init__(self, channel_id: int):
        super().__init__(timeout=120)
        self.channel_id = channel_id

        c = Container()
        c.add_item(TextDisplay("# ⚠️ Confirmation"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Supprimer définitivement ce ticket ?\n"
            "-# Action irréversible. Le transcript sera envoyé automatiquement."
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(
            _ConfirmDeleteBtn(channel_id),
            _CancelDeleteBtn(),
        ))
        self.add_item(c)


class _ConfirmDeleteBtn(Button):
    def __init__(self, channel_id: int):
        super().__init__(label="Confirmer", style=discord.ButtonStyle.danger, emoji="🗑️")
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        ticket = await tm.get_ticket(self.channel_id)
        if not ticket:
            return await interaction.followup.send(
                view=error_container("Ticket introuvable."), ephemeral=True
            )
        await do_delete_ticket(interaction, interaction.channel, ticket)


class _CancelDeleteBtn(Button):
    def __init__(self):
        super().__init__(label="Annuler", style=discord.ButtonStyle.secondary, emoji="✖️")

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=info_container("Suppression annulée.")
        )


# ============================================================
# 🔔 Wakeup (relance staff-only + cooldown 1h)
# ============================================================

# {(channel_id, staff_id): ts} — cooldown mémoire (perte au redémarrage = ok)
_wake_cooldowns: dict[tuple[int, int], int] = {}


async def handle_wakeup(interaction: discord.Interaction, channel_id: int) -> None:
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild_id

    ticket = await tm.get_ticket(channel_id)
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Ce ticket n'existe plus."), ephemeral=True
        )
    if not await is_staff(interaction, ticket, guild_id):
        return await interaction.followup.send(
            view=error_container("Cette action est réservée aux staffs !"), ephemeral=True
        )

    key = (channel_id, interaction.user.id)
    last = _wake_cooldowns.get(key, 0)
    if (int(time.time()) - last) < WAKEUP_COOLDOWN_SECONDS:
        return await interaction.followup.send(
            view=error_container("Veuillez patienter avant de relancer à nouveau."),
            ephemeral=True,
        )
    _wake_cooldowns[key] = int(time.time())

    await interaction.channel.send(
        view=info_container(f"<@{ticket['creator_id']}> Le staff attend votre réponse !")
    )
    await interaction.followup.send(
        view=success_container("Relance envoyée."), ephemeral=True
    )