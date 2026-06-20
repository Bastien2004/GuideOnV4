"""
cogs/dev/nota_debug.py — Debug du système de notations Alpha
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

from utils.managers.alpha_nota_manager import (
    load_nota_config,
    load_nota_state,
    now_paris,
    is_time_now,
    is_past_deadline,
)


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(
    name="nota_debug",
    description="🔍 [OP] Debug du système de notations"
)
async def nota_debug(interaction: Interaction) -> None:

    # 🔐 Permissions
    if not await check_dev(interaction, "**consulter le debug des notations**"):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande
    if not await verifier_commande(interaction, "dev_nota_debug"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "dev_nota_debug")

    cfg = await load_nota_config(interaction.guild_id)
    state = await load_nota_state(interaction.guild_id)

    now = now_paris()

    presence_trigger = is_time_now(
        cfg.get("send_presence_weekday"),
        cfg.get("send_presence_hour"),
        cfg.get("send_presence_minute"),
    )

    deadline_trigger = is_past_deadline(
        cfg.get("deadline_weekday"),
        cfg.get("deadline_hour"),
        cfg.get("deadline_minute"),
    )

    public_trigger = is_time_now(
        cfg.get("send_public_weekday"),
        cfg.get("send_public_hour"),
        cfg.get("send_public_minute"),
    )

    text = (
        "# 🔍 Debug Notations Alpha\n\n"

        f"### 🕒 Heure actuelle\n"
        f"⇝ `{now}`\n\n"

        f"### ⚙️ Configuration\n"
        f"⇝ enabled : `{cfg.get('enabled')}`\n"
        f"⇝ channel_staff_id : `{cfg.get('channel_staff_id')}`\n"
        f"⇝ channel_public_id : `{cfg.get('channel_public_id')}`\n"
        f"⇝ channel_logs_id : `{cfg.get('channel_logs_id')}`\n\n"

        f"### 📅 Présence\n"
        f"⇝ weekday : `{cfg.get('send_presence_weekday')}`\n"
        f"⇝ hour : `{cfg.get('send_presence_hour')}`\n"
        f"⇝ minute : `{cfg.get('send_presence_minute')}`\n"
        f"⇝ trigger_now : `{presence_trigger}`\n\n"

        f"### ⛔ Deadline\n"
        f"⇝ weekday : `{cfg.get('deadline_weekday')}`\n"
        f"⇝ hour : `{cfg.get('deadline_hour')}`\n"
        f"⇝ minute : `{cfg.get('deadline_minute')}`\n"
        f"⇝ past_deadline : `{deadline_trigger}`\n\n"

        f"### 🌍 Publication\n"
        f"⇝ weekday : `{cfg.get('send_public_weekday')}`\n"
        f"⇝ hour : `{cfg.get('send_public_hour')}`\n"
        f"⇝ minute : `{cfg.get('send_public_minute')}`\n"
        f"⇝ trigger_now : `{public_trigger}`\n\n"

        f"### 📊 State\n"
        f"⇝ availability_message_id : `{state.get('availability_message_id')}`\n"
        f"⇝ public_message_id : `{state.get('public_message_id')}`\n"
        f"⇝ reminder_sent : `{state.get('reminder_sent')}`\n"
        f"⇝ assigned_ranges : `{state.get('assigned_ranges')}`\n"
    )

    await interaction.followup.send(text, ephemeral=True)


@nota_debug.error
async def nota_debug_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)