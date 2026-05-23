"""
views/ticket/panel_public_view.py — Vue publique persistante d'un panel.
"""

from __future__ import annotations

import logging
import time

import discord
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.boutique.gold_manager import is_gold
from utils.boutique.vip_manager import is_vip
from utils.container_universel import error_container, success_container

from utils.managers import ticket_manager as tm
from views.ticket._helpers import (
    MAX_TICKETS_PANEL_DEFAULT,
    MAX_TICKETS_PANEL_GOLD,
    MAX_TICKETS_USER_DEFAULT,
    MAX_TICKETS_USER_VIP,
    TICKET_COOLDOWN_SECONDS,
)

log = logging.getLogger(__name__)

OPEN_PREFIX = "ticket_open:"

_open_cooldowns: dict[tuple[int, str, int], int] = {}


# ============================================================
# 🎫 Vue publique du panel (persistante)
# ============================================================

class PanelPublicView(LayoutView):
    """Vue persistante : titre + message + bouton d'ouverture."""

    def __init__(self, panel_id: str, guild_id: int, title: str = "", message: str = ""):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        self.guild_id = guild_id

        container = Container()
        if title:
            container.add_item(TextDisplay(f"# 🎫 {title}"))
            container.add_item(Separator())
        if message:
            container.add_item(TextDisplay(message))
            container.add_item(Separator())

        row = ActionRow(OpenTicketButton(panel_id))
        container.add_item(row)
        self.add_item(container)

    @classmethod
    def from_panel(cls, panel: dict) -> "PanelPublicView":
        """Construit la vue depuis un dict panel (manager.to_dict())."""
        return cls(
            panel_id=panel["panel_id"],
            guild_id=panel["guild_id"],
            title=panel.get("title", "Support"),
            message=panel.get("panel_message", "Cliquez ci-dessous pour ouvrir un ticket."),
        )


class OpenTicketButton(Button):
    """Bouton persistant d'ouverture. panel_id encodé dans le custom_id."""

    def __init__(self, panel_id: str):
        super().__init__(
            label="Ouvrir un ticket",
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id=f"{OPEN_PREFIX}{panel_id}",
        )
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        panel = await tm.get_panel(guild_id, self.panel_id)
        if not panel:
            return await interaction.response.send_message(
                view=error_container("Panel introuvable."), ephemeral=True
            )

        user = interaction.user
        now = int(time.time())

        # ── Cooldown ouverture (mémoire) ──
        key = (guild_id, self.panel_id, user.id)
        last = _open_cooldowns.get(key, 0)
        rem = TICKET_COOLDOWN_SECONDS - (now - last)
        if rem > 0:
            return await interaction.response.send_message(
                view=error_container(
                    f"⏳ Merci d'attendre **{rem}s** avant d'ouvrir un nouveau ticket."
                ),
                ephemeral=True,
            )

        # ── Limite tickets simultanés / utilisateur ──
        max_user = MAX_TICKETS_USER_VIP if is_vip(user.id) else MAX_TICKETS_USER_DEFAULT
        user_count = await tm.count_user_tickets_on_panel(guild_id, self.panel_id, user.id)
        if user_count >= max_user:
            return await interaction.response.send_message(
                view=error_container(
                    f"Vous avez déjà **{user_count}** ticket(s) ouvert(s) sur ce panel.\n"
                    f"-# Limite : {max_user} ticket(s) simultané(s)."
                ),
                ephemeral=True,
            )

        # ── Limite tickets ouverts / panel ──
        max_panel = MAX_TICKETS_PANEL_GOLD if is_gold(guild_id) else MAX_TICKETS_PANEL_DEFAULT
        if panel.get("open_tickets_count", 0) >= max_panel:
            return await interaction.response.send_message(
                view=error_container(
                    f"Ce panel a atteint sa limite de **{max_panel}** tickets ouverts.\n"
                    f"-# Merci de revenir plus tard."
                ),
                ephemeral=True,
            )

        # ── Modal de création ──
        await interaction.response.send_modal(CreateTicketModal(self.panel_id))
        _open_cooldowns[key] = now


# ============================================================
# 📝 Modal de création
# ============================================================

class CreateTicketModal(discord.ui.Modal):
    def __init__(self, panel_id: str):
        super().__init__(title="Ouverture de ticket")
        self.panel_id = panel_id
        self.raison = discord.ui.TextInput(
            label="Raison",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500,
        )
        self.add_item(self.raison)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        guild, user = interaction.guild, interaction.user
        guild_id = guild.id
        panel = await tm.get_panel(guild_id, self.panel_id)
        if not panel:
            return await interaction.followup.send(
                view=error_container("Panel introuvable."), ephemeral=True
            )

        # ── Vérif ban ticket (rôle Discord) ──
        ban_role_id = panel.get("role_ban_ticket_id")
        if ban_role_id:
            ban_role = guild.get_role(int(ban_role_id))
            if ban_role is None:
                try:
                    ban_role = discord.utils.get(await guild.fetch_roles(), id=int(ban_role_id))
                except discord.HTTPException:
                    ban_role = None
            if ban_role and isinstance(user, discord.Member) and ban_role in user.roles:
                return await interaction.followup.send(
                    view=error_container("Vous êtes actuellement banni des tickets sur ce panel."),
                    ephemeral=True,
                )

        # ── Réservation du numéro de ticket ──
        ticket_num = await tm.reserve_ticket_number(guild_id, self.panel_id)
        if ticket_num is None:
            return await interaction.followup.send(
                view=error_container("Impossible de réserver un numéro de ticket."),
                ephemeral=True,
            )
        ticket_name = f"ticket-{ticket_num}"

        # ── Overwrites du salon ──
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, read_message_history=True,
            ),
        }
        for rid in panel.get("staff_roles", []):
            role = guild.get_role(int(rid))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                )

        category = guild.get_channel(panel.get("ticket_category_id"))
        try:
            channel = await guild.create_text_channel(
                name=ticket_name, category=category, overwrites=overwrites
            )
        except discord.HTTPException as e:
            return await interaction.followup.send(
                view=error_container(f"Impossible de créer le salon : `{e}`"),
                ephemeral=True,
            )

        # ── Message welcome + toolbar ──
        from views.ticket.welcome_view import WelcomeView

        ping_role_id = panel.get("ping_role_id")
        welcome = WelcomeView(
            channel_id=channel.id,
            guild_id=guild_id,
            ticket_number=ticket_num,
            creator_mention=user.mention,
            raison=self.raison.value,
            ping_role_id=ping_role_id,
        )
        msg = await channel.send(view=welcome)
        try:
            await msg.pin()
        except discord.HTTPException:
            pass

        # ── Persistance DB (insert + incr open_count atomique) ──
        try:
            await tm.create_ticket(
                channel_id=channel.id,
                guild_id=guild_id,
                panel_id=self.panel_id,
                creator_id=user.id,
                ticket_number=ticket_num,
                original_name=ticket_name,
                pseudo=str(user),
                raison=self.raison.value,
                opened_at=int(time.time()),
                welcome_message_id=msg.id,
            )
        except ValueError:
            try:
                await channel.delete(reason="Création de ticket annulée (panel introuvable)")
            except discord.HTTPException:
                pass
            return await interaction.followup.send(
                view=error_container("Le panel a été supprimé pendant l'ouverture."),
                ephemeral=True,
            )

        await interaction.followup.send(
            view=success_container(f"Ticket ouvert : {channel.mention}"),
            ephemeral=True,
        )