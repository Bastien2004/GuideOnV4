"""
cogs/events/reminder_scheduler.py — Déclenchement des rappels personnels (/rappel).

Même patron que cogs/events/giveaway_listener.py : polling périodique de
la DB (pas d'event Discord à écouter ici), set en mémoire anti double-
traitement pendant une même fenêtre de poll, before_loop qui attend que
le bot soit prêt, start()/cancel() dans __init__/cog_unload.

Livraison : MP d'abord si destination=mp, sinon direct dans le salon
d'origine (channel_id). Si le MP échoue (DMs fermés — Forbidden/HTTPException),
on retombe sur le salon d'origine avec une note "DMs fermés". Dans tous
les cas, une fois une tentative de livraison effectuée (réussie ou non),
le rappel est supprimé — pas de retry : un rappel raté silencieusement
(ex: salon supprimé ET DMs fermés) reste loggé en warning mais n'est pas
rejoué, pour éviter qu'un rappel cassé ne pollue indéfiniment la table.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands, tasks
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.datetime_utils import now_utc
from utils.managers.reminder_manager import delete_reminder, get_due_reminders

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30


# ======================================================
# =================== HELPERS ==========================
# ======================================================

def _build_reminder_message(reminder: dict, *, fallback_used: bool = False) -> LayoutView:
    """Container V2 envoyé au déclenchement du rappel."""
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"# ⏰ Rappel — <@{reminder['user_id']}>"))
    c.add_item(Separator())
    c.add_item(TextDisplay(reminder["message"]))
    c.add_item(Separator())
    footer = f"-# 🆔 ID `{reminder['id']}`"
    if fallback_used:
        footer += "\n-# 📪 Envoyé ici car tes DMs sont fermés."
    c.add_item(TextDisplay(footer))
    view.add_item(c)
    return view


async def _fetch_channel(bot: discord.Client, channel_id: int):
    try:
        return bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def _send_to_channel(bot: discord.Client, channel_id: int, view: LayoutView) -> bool:
    channel = await _fetch_channel(bot, channel_id)
    if channel is None:
        return False
    try:
        await channel.send(view=view)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


async def _send_dm(bot: discord.Client, user_id: int, view: LayoutView) -> bool:
    try:
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
    except (discord.NotFound, discord.HTTPException):
        return False
    try:
        await user.send(view=view)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


# ======================================================
# =============== COG : ReminderScheduler ===============
# ======================================================

class ReminderScheduler(commands.Cog):
    """Cog responsable du déclenchement des rappels personnels /rappel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Anti double-envoi pour les rappels encore en traitement entre deux polls.
        self._sending: set[int] = set()
        self.check_reminders.start()
        log.info("[Rappel] Scheduler démarré (intervalle: %ds)", CHECK_INTERVAL_SECONDS)

    async def cog_unload(self) -> None:
        self.check_reminders.cancel()

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def check_reminders(self) -> None:
        try:
            due = await get_due_reminders(now_utc())
        except Exception:
            log.exception("[Rappel] check_reminders : échec lecture")
            return

        for reminder in due:
            rid = reminder["id"]
            if rid in self._sending:
                continue
            self._sending.add(rid)
            try:
                await self._fire_reminder(reminder)
            except Exception:
                log.exception("[Rappel] Erreur déclenchement rappel %s", rid)
            finally:
                self._sending.discard(rid)

    @check_reminders.before_loop
    async def _before_check(self) -> None:
        await self.bot.wait_until_ready()

    async def _fire_reminder(self, reminder: dict) -> None:
        """Livre un rappel (MP puis secours salon, ou direct salon), puis le supprime."""
        rid = reminder["id"]
        delivered = False

        if reminder["destination"] == "mp":
            delivered = await _send_dm(
                self.bot, reminder["user_id"], _build_reminder_message(reminder)
            )
            if not delivered:
                delivered = await _send_to_channel(
                    self.bot, reminder["channel_id"],
                    _build_reminder_message(reminder, fallback_used=True),
                )
        else:
            delivered = await _send_to_channel(
                self.bot, reminder["channel_id"], _build_reminder_message(reminder)
            )

        if not delivered:
            log.warning(
                "[Rappel] Impossible de livrer le rappel %s (user=%s) — ni MP, ni salon %s.",
                rid, reminder["user_id"], reminder["channel_id"],
            )

        # Une seule tentative : succès ou échec, le rappel ne reste pas en DB.
        await delete_reminder(rid)
        if delivered:
            log.info("[Rappel] Rappel %s livré (user=%s)", rid, reminder["user_id"])


# ----------------------------------------------------
# 🔧 Setup
# ----------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReminderScheduler(bot))
