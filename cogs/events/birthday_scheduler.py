"""
cogs/events/birthday_scheduler.py — Gestion du système d'anniversaire.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from utils.managers.birthday_manager import all_active_configs, get_birthdays_today, save_birthday_config

log = logging.getLogger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")
MORNING = time(hour=7, minute=0, tzinfo=PARIS_TZ)
MIDNIGHT = time(hour=0, minute=0, tzinfo=PARIS_TZ)


def _build_birthday_message(mentions: list[str]) -> str:
    """Création du message d'anniversaire."""

    if len(mentions) == 1:
        return (f"🎉 Joyeux anniversaire à {mentions[0]} !")
    
    joined = ", ".join(mentions[:-1]) + f" et {mentions[-1]}"

    return (f"🎉 Joyeux anniversaire à {joined} !")


class BirthdayScheduler(commands.Cog):
    """Planificateur du birthday du jour."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.morning_task.start()
        self.midnight_task.start()

        log.info( "[Birthday] Scheduler démarré (morning=%s, midnight=%s, tz=%s)", MORNING.strftime("%H:%M"), MIDNIGHT.strftime("%H:%M"), PARIS_TZ)

    async def cog_unload(self) -> None:
        self.morning_task.cancel()
        self.midnight_task.cancel()

    # ==================================================
    # 🌅 Tâche matinale (7h00) — vœux + rôle
    # ==================================================

    @tasks.loop(time=MORNING)
    async def morning_task(self) -> None:
        today = datetime.now(PARIS_TZ).date()
        log.info("[Birthday] Morning task — today=%s", today)

        try:
            configs = await all_active_configs()

        except Exception:
            log.exception("[Birthday] morning_task : échec all_active_configs")
            return

        for cfg in configs:
            try:
                await self._process_morning(cfg, today)

            except Exception:
                log.exception("[Birthday] morning_task : exception pour guild=%s", cfg.get("guild_id"))

    @morning_task.before_loop
    async def _before_morning(self) -> None:
        await self.bot.wait_until_ready()

    async def _process_morning(self, cfg: dict, today) -> None:
        guild_id = cfg["guild_id"]
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        channel_id = cfg.get("channel_id")
        if channel_id is None:
            log.warning(
                "[Birthday] guild=%s activée sans salon configuré", guild_id
            )
            return

        channel = guild.get_channel(channel_id)
        if channel is None:

            log.warning("[Birthday] Salon %s introuvable pour guild=%s → désactivation", channel_id, guild_id)

            try:
                await save_birthday_config(
                    guild_id, {"enabled": False, "channel_id": None}
                )

            except Exception:
                log.exception("[Birthday] Échec désactivation auto guild=%s", guild_id)
            return

        me = guild.me
        if me is None or not channel.permissions_for(me).send_messages:

            log.warning("[Birthday] Pas de permission d'écrire dans #%s guild=%s", channel_id, guild_id)
            return

        users = await get_birthdays_today(guild_id, today)
        if not users:
            return

        valid: list[tuple[dict, discord.Member]] = []
        for u in users:
            m = guild.get_member(u["user_id"])
            if m is None:
                log.info(
                    "[Birthday] Membre %s parti — skip guild=%s",
                    u["user_id"], guild_id,
                )
                continue
            if m.bot:
                continue
            valid.append((u, m))

        if not valid:
            return

        mentions = [m.mention for _, m in valid]
        message = _build_birthday_message(mentions)
        try:
            await channel.send(
                message,
                allowed_mentions=discord.AllowedMentions(users=True),
            )

            log.info("[Birthday] Message envoyé guild=%s — %d membre(s) fêté(s)", guild_id, len(valid))

        except discord.Forbidden:
            log.warning("[Birthday] Forbidden envoi message guild=%s salon=%s", guild_id, channel_id)
            return
        
        except discord.HTTPException:
            log.exception("[Birthday] Erreur HTTP envoi message guild=%s", guild_id)
            return

        role_id = cfg.get("role_id")
        if role_id is None:
            return
        
        role = guild.get_role(role_id)
        if role is None:
            log.warning("[Birthday] Rôle %s introuvable guild=%s", role_id, guild_id)
            return
        
        if role.is_default() or role.managed:
            log.warning("[Birthday] Rôle %s non attribuable (everyone/managed) guild=%s", role_id, guild_id)
            return
        
        if role >= me.top_role:
            log.warning("[Birthday] Rôle %s au-dessus du bot guild=%s — skip", role_id, guild_id)
            return

        for _, member in valid:
            if role in member.roles:
                continue
            try:
                await member.add_roles(role, reason="Anniversaire du jour")

            except discord.Forbidden:
                log.warning("[Birthday] Forbidden add_role %s → %s guild=%s", role.id, member.id, guild_id)

            except discord.HTTPException:
                log.exception("[Birthday] Erreur HTTP add_role %s → %s", role.id, member.id)

    # ==================================================
    # 🌙 Tâche minuit (00h00) — retrait du rôle
    # ==================================================

    @tasks.loop(time=MIDNIGHT)
    async def midnight_task(self) -> None:
        log.info("[Birthday] Midnight task — retrait des rôles anniversaire")

        try:
            configs = await all_active_configs()

        except Exception:
            log.exception("[Birthday] midnight_task : échec all_active_configs")
            return

        for cfg in configs:
            try:
                await self._process_midnight(cfg)

            except Exception:
                log.exception("[Birthday] midnight_task : exception pour guild=%s", cfg.get("guild_id"))

    @midnight_task.before_loop
    async def _before_midnight(self) -> None:
        await self.bot.wait_until_ready()

    async def _process_midnight(self, cfg: dict) -> None:
        guild_id = cfg["guild_id"]
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        role_id = cfg.get("role_id")
        if role_id is None:
            return
        role = guild.get_role(role_id)
        if role is None:
            return

        me = guild.me
        if me is not None and role >= me.top_role:
            log.warning("[Birthday] Rôle %s au-dessus du bot — retrait impossible guild=%s", role_id, guild_id)
            return

        members_with_role = list(role.members)
        if not members_with_role:
            return

        log.info("[Birthday] Retrait rôle %s à %d membre(s) guild=%s", role_id, len(members_with_role), guild_id)

        for member in members_with_role:
            try:
                await member.remove_roles(role, reason="Fin de la journée d'anniversaire")

            except discord.Forbidden:
                log.warning("[Birthday] Forbidden remove_role %s → %s guild=%s", role.id, member.id, guild_id)

            except discord.HTTPException:
                log.exception("[Birthday] Erreur HTTP remove_role %s → %s", role.id, member.id)


# ----------------------------------------------------
# 🔧 Setup
# ----------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BirthdayScheduler(bot))