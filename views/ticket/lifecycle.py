"""
views/ticket/lifecycle.py — Logique de cycle de vie d'un ticket.
"""

from __future__ import annotations

import asyncio
import logging
import time

import discord
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container, info_container, success_container, warning_container
from utils.managers import ticket_manager as tm
from utils.ticket_limits import WAKEUP_COOLDOWN_SECONDS
from views.ticket._helpers import (
    closed_name,
    is_staff,
    is_staff_or_creator,
    pick_ticket_category,
    rename_cooldown_remaining,
    strip_closed_prefix,
    try_rename,
)
from views.ticket.transcript import do_delete_ticket

log = logging.getLogger(__name__)

REOPEN_PREFIX = "ticket_reopen:"
DELCLOSED_PREFIX = "ticket_delclosed:"

# ============================================================
# 🔐 Verrou par salon (fermeture / réouverture)
# ============================================================

# Empêche deux fermetures/réouvertures concurrentes du MÊME salon (double-clic,
# créateur et staff qui cliquent en même temps, etc.) de passer toutes les
# deux les vérifications (closed=False, cooldown) avant que l'une d'elles
# n'ait eu le temps d'écrire son résultat en base. Sans ce verrou, les deux
# appels concurrents déclenchent chacun leurs propres requêtes Discord
# (renommage + déplacement de catégorie) sur le même salon, ce qui épuise en
# un instant le quota Discord de 2 modifications de salon / 10 min et
# déclenche une cascade de 429 — parfois assez longue pour faire expirer le
# token de l'interaction (15 min) et provoquer un "Invalid Webhook Token" sur
# la réponse suivante.
_channel_locks: dict[int, asyncio.Lock] = {}


def _get_channel_lock(channel_id: int) -> asyncio.Lock:
    lock = _channel_locks.get(channel_id)
    if lock is None:
        lock = asyncio.Lock()
        _channel_locks[channel_id] = lock
    return lock


# ============================================================
# 🔒 Fermeture
# ============================================================

async def handle_close(interaction: discord.Interaction, channel_id: int, *, staff_only: bool = False) -> None:
    """Ferme un ticket."""

    if not interaction.response.is_done():
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return
    guild_id = interaction.guild_id

    async with _get_channel_lock(channel_id):
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
                view=error_container("Vous n'êtes pas autorisé à réaliser cette action."), ephemeral=True
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

    creator = interaction.guild.get_member(ticket["creator_id"])
    if creator:
        try:
            await channel.set_permissions(creator, view_channel=False)
        except discord.HTTPException:
            pass

    closed_cat = interaction.guild.get_channel(panel.get("closed_category_id")) if panel else None
    target_name = closed_name(ticket["original_name"])

    # Un seul appel PATCH pour le renommage + le déplacement de catégorie
    # (au lieu de deux appels séparés) : ces deux opérations partagent le
    # même quota Discord de modifications de salon (2 / 10 min), donc les
    # regrouper réduit de moitié la consommation de ce quota à chaque
    # fermeture.
    edit_kwargs: dict = {}
    if channel.name != target_name:
        edit_kwargs["name"] = target_name
    if closed_cat is not None:
        edit_kwargs["category"] = closed_cat
    if edit_kwargs:
        try:
            await channel.edit(**edit_kwargs)
        except discord.HTTPException:
            log.warning(
                "[TICKET] Fermeture : édition de salon refusée par Discord "
                "guild=%s channel=%s", guild_id, channel.id,
            )

    await tm.update_ticket(channel.id, closed=True, last_rename_at=int(time.time()))
    await interaction.followup.send(view=ReopenView(channel.id))


# ============================================================
# 🔓 Réouverture
# ============================================================

class ReopenView(LayoutView):
    """Ré ouverture d'un ticket fermé."""

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
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return
        guild_id = interaction.guild_id

        async with _get_channel_lock(self.channel_id):
            await self._do_reopen(interaction, guild_id)

    async def _do_reopen(self, interaction: discord.Interaction, guild_id: int) -> None:
        ticket = await tm.get_ticket(self.channel_id)
        if not ticket:
            return await interaction.followup.send(
                view=error_container("Le ticket est introuvable."), ephemeral=True
            )

        if not ticket.get("closed"):
            return await interaction.followup.send(
                view=error_container("Ce ticket est déjà ouvert."), ephemeral=True
            )

        if not await is_staff(interaction, ticket, guild_id):
            return await interaction.followup.send(
                view=error_container("Vous n'avez pas la permission de réaliser cette action."),
                ephemeral=True,
            )

        rem = rename_cooldown_remaining(ticket)
        if rem > 0:
            return await interaction.followup.send(
                view=error_container(f"Limite Discord : attendez **{rem // 60}m {rem % 60}s**."),
                ephemeral=True,
            )

        panel = await tm.get_panel(guild_id, ticket["panel_id"])

        # Catégorie de destination (principale, ou secours si pleine/absente) —
        # même logique de secours qu'à la création. Si le salon ne peut pas
        # être replacé (aucune catégorie disponible, ou édition Discord
        # refusée), on réouvre tout de même le ticket (permissions + renommage)
        # mais on le signale clairement au staff plutôt que de laisser le
        # salon rester silencieusement dans la catégorie fermée.
        category = None
        used_backup = False
        move_status = "no_panel"  # no_panel | no_category | move_failed | ok
        if panel:
            category, used_backup = pick_ticket_category(interaction.guild, panel)
            if category is None:
                move_status = "no_category"
            else:
                move_status = "ok"

        # Un seul appel PATCH pour le renommage + le déplacement de catégorie
        # (au lieu de deux appels séparés) : ces deux opérations partagent le
        # même quota Discord de modifications de salon (2 / 10 min).
        edit_kwargs: dict = {}
        if interaction.channel.name != ticket["original_name"]:
            edit_kwargs["name"] = ticket["original_name"]
        if category is not None:
            edit_kwargs["category"] = category
        if edit_kwargs:
            try:
                await interaction.channel.edit(**edit_kwargs)
            except discord.HTTPException:
                log.exception(
                    "[TICKET] Réouverture : édition de salon refusée par Discord "
                    "guild=%s channel=%s category=%s", guild_id, self.channel_id,
                    getattr(category, "id", None),
                )
                if category is not None:
                    move_status = "move_failed"

        creator = interaction.guild.get_member(ticket["creator_id"])
        if creator:
            try:
                await interaction.channel.set_permissions(
                    creator, view_channel=True, send_messages=True,
                    read_message_history=True, attach_files=True,
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

        if move_status == "ok" and used_backup:
            log.warning(
                "[TICKET] Réouverture : catégorie principale pleine/indisponible, "
                "salon déplacé vers la catégorie de secours %s | guild=%s channel=%s",
                category.id, guild_id, self.channel_id,
            )
            await interaction.followup.send(
                view=warning_container(
                    "Le ticket est de nouveau **ouvert**, mais la catégorie principale était "
                    "pleine : il a été replacé dans la **catégorie de secours**."
                )
            )
        elif move_status in ("no_category", "move_failed"):
            await interaction.followup.send(
                view=warning_container(
                    "Le ticket est de nouveau **ouvert**, mais il n'a **pas pu être replacé** "
                    "dans une catégorie de tickets (principale et secours pleines/indisponibles, "
                    "ou modification refusée par Discord). Déplacez-le manuellement."
                )
            )
        else:
            await interaction.followup.send(
                view=success_container("Le ticket est de nouveau **ouvert**.")
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
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return
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
        c.add_item(TextDisplay("# <:erreur:1495443907281031359> Confirmation"))
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
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return
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
# 🔔 Wakeup
# ============================================================

_wake_cooldowns: dict[tuple[int, int], int] = {}


async def handle_wakeup(interaction: discord.Interaction, channel_id: int) -> None:
    if not interaction.response.is_done():
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return
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
            view=error_container("Veuillez patienter avant d'effectuer une nouvelle relance."),
            ephemeral=True,
        )
    _wake_cooldowns[key] = int(time.time())

    await interaction.channel.send(
        view=info_container(f"<@{ticket['creator_id']}> Le staff attend votre réponse !")
    )
    await interaction.followup.send(
        view=success_container("Relance envoyée."), ephemeral=True
    )