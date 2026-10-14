"""
views/rappel/creer_view.py — Interface de création d'un rappel personnel.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, send_ephemeral, success_container, warning_container
from utils.datetime_utils import format_duration, now_utc, parse_duration
from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal
from utils.managers.reminder_manager import (
    ReminderDurationError,
    ReminderLimitError,
    create_reminder,
    max_duration_seconds_for,
    max_pending_for,
)


log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

MIN_REMINDER_SECONDS = 10
MAX_MESSAGE_LENGTH = 500

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"


def _truncate(s: str, n: int = 100) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ============================================================
# 🧩 Class principale
# ============================================================

class RappelCreerView(BaseLayoutView):
    """Interface de création d'un rappel personnel."""

    def __init__(self, *, user_id: int, guild_id: int, channel_id: int):
        super().__init__(owner_id=user_id, timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id

        self.duration_seconds: int | None = None
        self.reminder_message: str | None = None
        self.destination: str = "mp"

        self.max_duration_seconds: int = max_duration_seconds_for(user_id)
        self.max_pending: int = max_pending_for(user_id)

        self._build()

    def _is_complete(self) -> bool:
        return self.duration_seconds is not None and bool(self.reminder_message)

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# <:time:1559978913739047052> Création nouveau rappel"))
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# <:AI:1547703102273093633> Limité à **{self.max_pending}** rappels simultanés"))
        container.add_item(Separator())

        # ── Temps ──────────────────────────────────────────
        temps_display = (
            format_duration(timedelta(seconds=self.duration_seconds))
            if self.duration_seconds else "`Non défini`"
        )
        btn_temps = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_temps.callback = self._on_click_temps
        container.add_item(Section(
            TextDisplay(f"**<:time2:1559978943564619786> Dans combien de temps ?**\n-# {temps_display}"),
            accessory=btn_temps,
        ))
        container.add_item(Separator())

        # ── Message ────────────────────────────────────────
        message_display = f"« {_truncate(self.reminder_message)} »" if self.reminder_message else "`Non défini`"
        btn_message = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_message.callback = self._on_click_message
        container.add_item(Section(
            TextDisplay(f"**<:dialoguer:1495444451244511403> Message**\n-# {message_display}"),
            accessory=btn_message,
        ))
        container.add_item(Separator())

        # ── Destination ──
        is_mp = self.destination == "mp"
        btn_mp = Button(
            label="MP", style=ButtonStyle.primary if is_mp else ButtonStyle.secondary,
            emoji="📩", disabled=is_mp,
        )
        btn_salon = Button(
            label="Ce salon", style=ButtonStyle.primary if not is_mp else ButtonStyle.secondary,
            emoji="💬", disabled=not is_mp,
        )
        btn_mp.callback = self._make_cb_set_destination("mp")
        btn_salon.callback = self._make_cb_set_destination("salon")
        container.add_item(TextDisplay("**<:envoyer:1495444217718374580> Destination**"))
        container.add_item(ActionRow(btn_mp, btn_salon))
        container.add_item(Separator())

        btn_confirm = Button(
            label="Créer le rappel",
            emoji=ICON_VALIDER,
            style=ButtonStyle.success,
            disabled=not self._is_complete(),
        )
        btn_confirm.callback = self._on_confirm
        container.add_item(ActionRow(btn_confirm))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self._build()
        await self.push_update(interaction)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_click_temps(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            try:
                duration_seconds = int(parse_duration(value).total_seconds())
            except ValueError:
                await inter.response.send_message(
                    view=warning_container(
                        "Format de durée invalide. Exemples valides : `10m`, `2h`, `1d2h30m`."
                    ),
                    ephemeral=True,
                )
                return
            if duration_seconds < MIN_REMINDER_SECONDS or duration_seconds > self.max_duration_seconds:
                max_label = format_duration(timedelta(seconds=self.max_duration_seconds))
                await inter.response.send_message(
                    view=warning_container(
                        f"La durée doit être comprise entre **{MIN_REMINDER_SECONDS} secondes** et **{max_label}**."
                    ),
                    ephemeral=True,
                )
                return
            self.duration_seconds = duration_seconds
            await self._refresh(inter)

        current = format_duration(timedelta(seconds=self.duration_seconds)) if self.duration_seconds else ""
        modal = TextModal(
            title="Dans combien de temps ?",
            label="Durée",
            placeholder="Ex : 10m, 2h, 1d2h30m",
            default=current,
            min_length=2,
            max_length=20,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_click_message(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            value = value.strip()
            if not value:
                await inter.response.send_message(
                    view=warning_container("Le **message** du rappel ne peut pas être vide."),
                    ephemeral=True,
                )
                return
            if len(value) > MAX_MESSAGE_LENGTH:
                await inter.response.send_message(
                    view=warning_container(f"Le **message** ne peut pas dépasser **{MAX_MESSAGE_LENGTH}** caractères."),
                    ephemeral=True,
                )
                return
            self.reminder_message = value
            await self._refresh(inter)

        modal = TextModal(
            title="Message du rappel",
            label="Texte du rappel",
            placeholder="Ex : Penser à relancer le client X",
            default=self.reminder_message or "",
            min_length=1,
            max_length=MAX_MESSAGE_LENGTH,
            style=discord.TextStyle.paragraph,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    def _make_cb_set_destination(self, value: str):
        async def _cb(interaction: discord.Interaction) -> None:
            self.destination = value
            await self._refresh(interaction)
        return _cb

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        if not self._is_complete():
            await interaction.response.send_message(
                view=warning_container("Veuillez compléter tous les champs avant de confirmer."),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        due_at = now_utc() + timedelta(seconds=self.duration_seconds)

        try:
            reminder = await create_reminder(
                user_id=self.user_id,
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                destination=self.destination,
                message=self.reminder_message,
                due_at=due_at,
            )
        except ReminderLimitError as exc:
            await send_ephemeral(
                interaction,
                error_container(
                    f"Limite de rappel atteinte, patiente avant d'en créer un nouveau."
                ),
            )
            return
        except ReminderDurationError as exc:
            max_label = format_duration(timedelta(seconds=exc.max_seconds))
            await send_ephemeral(
                interaction,
                error_container(f"La durée maximale autorisée est de **{max_label}**."),
            )
            return
        except Exception:
            log.exception("[RAPPEL CRÉER] Échec de création (guild=%s, user=%s)", self.guild_id, self.user_id)
            await send_ephemeral(interaction, error_container("Impossible de créer ce **rappel**."))
            return

        due_ts = int(reminder["due_at"].timestamp())
        done_view = success_container(
            f"Rappel **#{reminder['id']}** programmé pour <t:{due_ts}:f> (<t:{due_ts}:R>).\n"
            f"-# ➥ Envoyé en {'MP' if self.destination == 'mp' else 'salon'}."
        )
        await self.push_update(interaction, view=done_view)
        self.stop()