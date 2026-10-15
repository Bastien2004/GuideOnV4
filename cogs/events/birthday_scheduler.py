"""
cogs/events/birthday_scheduler.py — Gestion du système d'anniversaire.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from utils.birthday import strip_birthday_role
from utils.managers.birthday_manager import (
    all_active_configs,
    all_configs_with_role,
    get_birthdays_today,
    save_birthday_config,
)

log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

PARIS_TZ = ZoneInfo("Europe/Paris")
MORNING = time(hour=7, minute=0, tzinfo=PARIS_TZ)
MIDNIGHT = time(hour=0, minute=0, tzinfo=PARIS_TZ)


# ============================================================
# 🛠️ Fonction utilitaire
# ============================================================

def _build_birthday_message(mentions: list[str]) -> str:
    """Création du message d'anniversaire."""

    if len(mentions) == 1:
        return (f"🎉 Joyeux anniversaire à {mentions[0]} !")
    
    joined = ", ".join(mentions[:-1]) + f" et {mentions[-1]}"

    return (f"🎉 Joyeux anniversaire à {joined} !")


# ============================================================
#  🧩 Class principale
# ============================================================

class BirthdayScheduler(commands.Cog):
    """Planificateur du birthday du jour."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.morning_task.start()
        self.midnight_task.start()

        log.info( "[LISTENER BIRTHDAY] Scheduler démarré | (morning=%s, midnight=%s, tz=%s)", MORNING.strftime("%H:%M"), MIDNIGHT.strftime("%H:%M"), PARIS_TZ)

    async def cog_unload(self) -> None:
        self.morning_task.cancel()
        self.midnight_task.cancel()

    # 🌅 Tâche matinale
    @tasks.loop(time=MORNING)
    async def morning_task(self) -> None:
        today = datetime.now(PARIS_TZ).date()
        log.info("[LISTENER BIRTHDAY] Tâche matinale — today=%s", today)

        try:
            configs = await all_active_configs()

        except Exception:
            log.exception("[LISTENER BIRTHDAY] Erreur tâche matinale | échec all_active_configs")
            return

        for cfg in configs:
            try:
                await self._process_morning(cfg, today)

            except Exception:
                log.exception("[LISTENER BIRTHDAY] Erreur tâche matinale | exception pour guild=%s", cfg.get("guild_id"))

    @morning_task.before_loop
    async def _before_morning(self) -> None:
        await self.bot.wait_until_ready()

    async def _process_morning(self, cfg: dict, today) -> None:
        guild_id = cfg["guild_id"]
        guild = self.bot.get_guild(guild_id)
        if guild is None:
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

        # 📢 Annonce dans le salon configuré et 🎈 attribution du rôle anniversaire :
        # DEUX fonctionnalités indépendantes (le panneau de config permet de régler
        # l'une sans l'autre), donc l'une ne doit jamais bloquer l'autre — avant ce
        # correctif (audit 2026-10-15), l'absence de salon faisait sortir la fonction
        # avant même de regarder le rôle, qui n'était alors JAMAIS attribué si un
        # admin configurait uniquement le rôle sans salon d'annonce.
        await self._announce(guild, guild_id, cfg.get("channel_id"), valid)
        await self._grant_role(guild, guild_id, cfg.get("role_id"), valid)

    async def _announce(
        self,
        guild: discord.Guild,
        guild_id: int,
        channel_id: int | None,
        valid: list[tuple[dict, discord.Member]],
    ) -> None:
        """Envoie le message d'anniversaire dans le salon configuré (best-effort)."""

        if channel_id is None:
            # Configuration valide : un admin peut n'activer que le rôle, sans salon.
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            log.warning("[LISTENER BIRTHDAY] Salon %s introuvable pour guild=%s — nettoyage de la config", channel_id, guild_id)
            try:
                # On retire uniquement la référence au salon : on ne désactive plus
                # tout le système (le rôle anniversaire, lui, reste indépendant et
                # continue de fonctionner normalement — cf. docstring _process_morning).
                await save_birthday_config(guild_id, {"channel_id": None})
            except Exception:
                log.exception("[LISTENER BIRTHDAY] Échec du nettoyage du salon | guild=%s", guild_id)
            return

        me = guild.me
        if me is None or not channel.permissions_for(me).send_messages:
            log.warning("[LISTENER BIRTHDAY] Permission insuffisante d'écrire | #%s guild=%s", channel_id, guild_id)
            return

        mentions = [m.mention for _, m in valid]
        message = _build_birthday_message(mentions)
        try:
            await channel.send(
                message,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            log.info("[LISTENER BIRTHDAY] Message envoyé guild=%s — %d membre(s) fêté(s)", guild_id, len(valid))
        except discord.Forbidden:
            log.warning("[LISTENER BIRTHDAY] Forbidden envoi message guild=%s salon=%s", guild_id, channel_id)
        except discord.HTTPException:
            log.exception("[LISTENER BIRTHDAY] Erreur HTTP envoi message guild=%s", guild_id)

    async def _grant_role(
        self,
        guild: discord.Guild,
        guild_id: int,
        role_id: int | None,
        valid: list[tuple[dict, discord.Member]],
    ) -> None:
        """Attribue le rôle anniversaire aux membres fêtés aujourd'hui (best-effort)."""

        if role_id is None:
            return

        role = guild.get_role(role_id)
        if role is None:
            log.warning("[LISTENER BIRTHDAY] Rôle %s introuvable guild=%s — nettoyage de la config", role_id, guild_id)
            try:
                await save_birthday_config(guild_id, {"role_id": None})
            except Exception:
                log.exception("[LISTENER BIRTHDAY] Échec du nettoyage du rôle | guild=%s", guild_id)
            return

        if role.is_default() or role.managed:
            log.warning("[LISTENER BIRTHDAY] Rôle %s non attribuable (everyone/managed) guild=%s", role_id, guild_id)
            return

        me = guild.me
        if me is None or role >= me.top_role:
            log.warning("[LISTENER BIRTHDAY] Rôle %s au-dessus du bot guild=%s — skip", role_id, guild_id)
            return

        for _, member in valid:
            if role in member.roles:
                continue
            try:
                await member.add_roles(role, reason="Anniversaire du jour")
            except discord.Forbidden:
                log.warning("[LISTENER BIRTHDAY] Forbidden add_role %s → %s guild=%s", role.id, member.id, guild_id)
            except discord.HTTPException:
                log.exception("[LISTENER BIRTHDAY] Erreur HTTP add_role %s → %s", role.id, member.id)

    # ==================================================
    # 🌙 Tâche minuit (00h00) — retrait du rôle
    # ==================================================

    @tasks.loop(time=MIDNIGHT)
    async def midnight_task(self) -> None:
        log.info("[LISTENER BIRTHDAY] Midnight task — retrait des rôles anniversaire")

        try:
            # ⚠️ Volontairement all_configs_with_role() et PAS all_active_configs() :
            # le retrait doit avoir lieu même si le système a été désactivé (bouton
            # ON/OFF) entre 7h00 et minuit — sans quoi le rôle reste accroché aux
            # membres indéfiniment (cf. docstring all_configs_with_role, audit 2026-10-15).
            configs = await all_configs_with_role()

        except Exception:
            log.exception("[LISTENER BIRTHDAY] midnight_task : échec all_configs_with_role")
            return

        for cfg in configs:
            try:
                await self._process_midnight(cfg)

            except Exception:
                log.exception("[LISTENER BIRTHDAY] midnight_task : exception pour guild=%s", cfg.get("guild_id"))

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

        removed = await strip_birthday_role(guild, role_id)
        if removed:
            log.info("[LISTENER BIRTHDAY] Retrait rôle %s : %d membre(s) guild=%s", role_id, removed, guild_id)


# ============================================================
#  💻 Setup BOT
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BirthdayScheduler(bot))