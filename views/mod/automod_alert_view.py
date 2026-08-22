"""
views/mod/automod_alert_view.py — Système d'alerte staff automod.
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_alert_manager as alert_mgr

log = logging.getLogger(__name__)

DISPLAY_TZ = ZoneInfo("Europe/Paris")

# ============================================================
# 🎨 Construction du message d'alerte
# ============================================================

def build_alert_container(*, system_display: str, user_id: int, channel_id: int, matched_term: str | None, message_excerpt: str | None,
    alert_id: int, taken_by_user_id: int | None = None, taken_at: datetime | None = None, staff_role_id: int | None = None) -> LayoutView:
    """Construction du message d'alerte."""

    view = AutomodAlertView(alert_id=alert_id, is_taken=taken_by_user_id is not None)

    c = Container()
    c.add_item(TextDisplay(f"# <:sanctionner:1495444382587949086> Alerte automod · {system_display}\n"))
    c.add_item(TextDisplay("-# L'utilisateur est mute en attendant un membre du staff."))
    c.add_item(Separator())

    body = (
        f"**Membre** : <@{user_id}> (`{user_id}`)\n"
        f"**Salon** : <#{channel_id}>\n"
        f"**Motif** : récidive malgré avertissement (**{system_display}**)"
    )
    if matched_term:
        body += f"\n**Terme détecté** : `{matched_term}`"
    c.add_item(TextDisplay(body))
    c.add_item(Separator())

    if message_excerpt:
        c.add_item(TextDisplay(f"**Message d'origine** :\n> {message_excerpt[:500]}"))
        c.add_item(Separator())

    if taken_by_user_id is not None and taken_at is not None:
        taken_local = taken_at.astimezone(DISPLAY_TZ)
        c.add_item(TextDisplay(
            f"✅ **Pris en charge** par <@{taken_by_user_id}> "
            f"le {taken_local:%d/%m/%Y à %Hh%M}"
        ))

    else:
        c.add_item(TextDisplay(
            "-# En attente d'une prise en charge par un staff."
        ))
        if staff_role_id is not None:
            c.add_item(TextDisplay(f"-# <@&{staff_role_id}>"))

    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.attach_container(c)
    return view


# ============================================================
# 🧩 View persistante
# ============================================================

class AutomodAlertView(LayoutView):
    """View persistante portant le bouton "Je m'en occupe"."""

    def __init__(self, *, alert_id: int | None = None, is_taken: bool = False) -> None:
        super().__init__(timeout=None)
        self._alert_id = alert_id
        self._is_taken = is_taken

    def attach_container(self, container: Container) -> None:
        button = _make_button(self._alert_id, self._is_taken)
        button.callback = self._on_click_take
        container.add_item(ActionRow(button))
        self.add_item(container)

    async def _on_click_take(self, interaction: Interaction) -> None:
        await _handle_take_click(interaction)


def _make_button(alert_id: int | None, is_taken: bool) -> Button:
    """Gestion du bouton."""

    if alert_id is None:
        return Button(label="Prendre en charge", style=ButtonStyle.primary, emoji="🤚", custom_id="automod_alert:pending")
    
    if is_taken:
        return Button(label="Pris en charge", style=ButtonStyle.secondary, emoji="✅", disabled=True, custom_id=f"automod_alert:{alert_id}")
    
    return Button(label="Prendre en charge", style=ButtonStyle.primary, emoji="🤚", custom_id=f"automod_alert:{alert_id}")


# ============================================================
# 🎯 Handler du clic (extrait pour testabilité)
# ============================================================

async def _handle_take_click(interaction: Interaction) -> None:

    custom_id = getattr(interaction.data, "custom_id", None) if interaction.data else None
    if not custom_id and isinstance(interaction.data, dict):
        custom_id = interaction.data.get("custom_id")
    if not custom_id:
        return

    parts = custom_id.split(":", 1)
    if len(parts) != 2 or parts[0] != "automod_alert":
        return

    if parts[1] == "pending":
        alert = await alert_mgr.get_alert_by_message(interaction.message.id)
        if alert is None:
            await interaction.response.send_message(
                view=error_container("Cette alerte est **obsolète**."),
                ephemeral=True,
            )
            return
        alert_id = alert["id"]

    else:
        try:
            alert_id = int(parts[1])
        except ValueError:
            return
        alert = await alert_mgr.get_alert_by_message(interaction.message.id)

        if alert is None:
            await interaction.response.send_message(
                view=error_container("Cette alerte n'existe plus dans la base de donnée."),
                ephemeral=True,
            )
            return

    if not isinstance(interaction.user, discord.Member):
        return
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message(
            view=error_container("Vous n'avez pas la permission de **prendre en charge** cette alerte."), ephemeral=True)
        return

    updated = await alert_mgr.mark_taken(alert_id, interaction.user.id)
    if updated is None:
        await interaction.response.send_message(
            view=error_container("Cette alerte a déjà été **prise en charge**."), ephemeral=True,
        )
        return

    if updated["taken_by_user_id"] != interaction.user.id:
        await interaction.response.send_message(
            view=warning_container(f"Alerte déjà prise en charge par <@{updated['taken_by_user_id']}>."),
            ephemeral=True,
        )
        return

    guild = interaction.guild
    if guild is not None:
        member = guild.get_member(updated["user_id"])
        if member is None:
            try:
                member = await guild.fetch_member(updated["user_id"])
            except (discord.NotFound, discord.HTTPException):
                member = None
        if member is not None:
            try:
                await member.timeout(None, reason=f"Alerte automod prise en charge par {interaction.user}")

            except (discord.Forbidden, discord.HTTPException):
                log.warning("[AUTOMOD] Levée du timeout échouée guild=%s user=%s", updated["guild_id"], updated["user_id"])


    from cogs.events.mod_automod_listener import get_system_display
    from utils.managers import mod_automod_general_manager as general_mgr

    general = await general_mgr.load_general(updated["guild_id"])

    new_view = build_alert_container(
        system_display=get_system_display(updated["system_key"]),
        user_id=updated["user_id"],
        channel_id=updated["channel_id"],
        matched_term=updated["matched_term"],
        message_excerpt=updated["message_excerpt"],
        alert_id=updated["id"],
        taken_by_user_id=updated["taken_by_user_id"],
        taken_at=updated["taken_at"],
        staff_role_id=general.get("staff_role_id"),
    )
    await interaction.response.edit_message(view=new_view)