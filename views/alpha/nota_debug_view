"""
views/dev/nota_debug_view.py — Vue de debug du système de notations Alpha.
"""

from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay


def build_nota_debug_view(
    now,
    cfg: dict,
    state: dict,
    presence_trigger: bool,
    deadline_trigger: bool,
    public_trigger: bool,
) -> LayoutView:
    """Construction de la view de debug."""
    view = LayoutView()
    c = Container()

    c.add_item(TextDisplay("# 🔍 Debug Notations Alpha"))
    c.add_item(Separator())

    c.add_item(TextDisplay(f"### 🕒 Heure actuelle\n⇝ `{now}`"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        "### ⚙️ Configuration\n"
        f"⇝ enabled : `{cfg.get('enabled')}`\n"
        f"⇝ channel_staff_id : `{cfg.get('channel_staff_id')}`\n"
        f"⇝ channel_public_id : `{cfg.get('channel_public_id')}`\n"
        f"⇝ channel_logs_id : `{cfg.get('channel_logs_id')}`"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        "### 📅 Présence\n"
        f"⇝ weekday : `{cfg.get('send_presence_weekday')}`\n"
        f"⇝ hour : `{cfg.get('send_presence_hour')}`\n"
        f"⇝ minute : `{cfg.get('send_presence_minute')}`\n"
        f"⇝ trigger_now : `{presence_trigger}`"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        "### ⛔ Deadline\n"
        f"⇝ weekday : `{cfg.get('deadline_weekday')}`\n"
        f"⇝ hour : `{cfg.get('deadline_hour')}`\n"
        f"⇝ minute : `{cfg.get('deadline_minute')}`\n"
        f"⇝ past_deadline : `{deadline_trigger}`"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        "### 🌍 Publication\n"
        f"⇝ weekday : `{cfg.get('send_public_weekday')}`\n"
        f"⇝ hour : `{cfg.get('send_public_hour')}`\n"
        f"⇝ minute : `{cfg.get('send_public_minute')}`\n"
        f"⇝ trigger_now : `{public_trigger}`"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        "### 📊 State\n"
        f"⇝ availability_message_id : `{state.get('availability_message_id')}`\n"
        f"⇝ public_message_id : `{state.get('public_message_id')}`\n"
        f"⇝ reminder_sent : `{state.get('reminder_sent')}`\n"
        f"⇝ assigned_ranges : `{state.get('assigned_ranges')}`"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view