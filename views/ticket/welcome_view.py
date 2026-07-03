"""
views/ticket/welcome_view.py — Message d'accueil + toolbar staff d'un ticket.
"""
from __future__ import annotations

import discord
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container, success_container
from utils.managers import ticket_manager as tm

from views.ticket._helpers import is_staff

ADD_PREFIX = "ticket_add:"
CLOSE_PREFIX = "ticket_close:"
WAKE_PREFIX = "ticket_wake:"

# ============================================================
# 🛠️ Vue Welcome (persistante)
# ============================================================

class WelcomeView(LayoutView):
    def __init__(
        self,
        *,
        channel_id: int,
        guild_id: int,
        ticket_number: str = "",
        creator_mention: str | None = None,
        raison: str | None = None,
        ping_role_id: int | None = None,
    ):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.guild_id = guild_id

        if creator_mention:
            c = Container()
            ping = f" <@&{ping_role_id}>" if ping_role_id else ""
            c.add_item(TextDisplay(f"# 🎫 Ticket #{ticket_number}{ping}"))
            c.add_item(Separator())
            c.add_item(TextDisplay(
                f"👤 **Utilisateur :** {creator_mention}\n"
                f"🧾 **Raison :** `{raison}`\n"
                f"*Votre ticket sera pris en charge le plus vite possible.*"
            ))
            c.add_item(Separator())
            c.add_item(TextDisplay("-# GuideOn Studio"))
            self.add_item(c)

        # Toolbar staff
        toolbar = Container()
        toolbar.add_item(TextDisplay("**🛠️ __ToolBar Staff__ :**"))
        toolbar.add_item(ActionRow(
            AddUserButton(channel_id),
            CloseButton(channel_id),
            WakeUpButton(channel_id),
        ))
        self.add_item(toolbar)


# ============================================================
# ➕ Ajouter un membre
# ============================================================

class AddUserButton(Button):
    def __init__(self, channel_id: int):
        super().__init__(
            label="Ajouter", emoji="➕", style=discord.ButtonStyle.secondary,
            custom_id=f"{ADD_PREFIX}{channel_id}",
        )
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        ticket = await tm.get_ticket(self.channel_id)
        if not ticket:
            return await interaction.response.send_message(
                view=error_container("Ce salon n'est pas un ticket."), ephemeral=True
            )
        if not await is_staff(interaction, ticket, interaction.guild_id):
            return await interaction.response.send_message(
                view=error_container("Vous n'avez pas la permission d'ajouter un membre."),
                ephemeral=True,
            )
        await interaction.response.send_modal(AddUserModal(self.channel_id))


class AddUserModal(discord.ui.Modal):
    def __init__(self, channel_id: int):
        super().__init__(title="Ajouter un membre")
        self.channel_id = channel_id
        self.u_input = discord.ui.TextInput(label="ID Discord", required=True)
        self.add_item(self.u_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        raw = self.u_input.value.strip()
        if not raw.isdigit():
            return await interaction.followup.send(
                view=error_container("ID invalide."), ephemeral=True
            )
        try:
            member = await interaction.guild.fetch_member(int(raw))
        except discord.HTTPException:
            return await interaction.followup.send(
                view=error_container("Utilisateur introuvable."), ephemeral=True
            )
        try:
            await interaction.channel.set_permissions(
                member, view_channel=True, send_messages=True,
                read_message_history=True, attach_files=True,
            )
        except discord.HTTPException:
            return await interaction.followup.send(
                view=error_container("Impossible de modifier les accès du salon."),
                ephemeral=True,
            )
        await interaction.followup.send(
            view=success_container(f"{member.mention} a été ajouté au ticket."),
            ephemeral=True,
        )


# ============================================================
# 🔒 Fermer
# ============================================================

class CloseButton(Button):
    def __init__(self, channel_id: int):
        super().__init__(
            label="Fermer", emoji="🔒", style=discord.ButtonStyle.danger,
            custom_id=f"{CLOSE_PREFIX}{channel_id}",
        )
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        from views.ticket.lifecycle import handle_close
        await handle_close(interaction, self.channel_id)


# ============================================================
# 🔔 Wake-up (relance)
# ============================================================

class WakeUpButton(Button):
    def __init__(self, channel_id: int):
        super().__init__(
            label="Relancer", emoji="🔔", style=discord.ButtonStyle.secondary,
            custom_id=f"{WAKE_PREFIX}{channel_id}",
        )
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        from views.ticket.lifecycle import handle_wakeup
        await handle_wakeup(interaction, self.channel_id)