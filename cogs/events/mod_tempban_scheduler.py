"""
cogs/events/mod_tempban_scheduler.py — Levée automatique des tempbans expirés.

commands.Cog avec setup() → chargé automatiquement par _load_cogs_from_directory
(rglob récursif sur cogs/). Boucle toutes les 5 minutes : cherche les
tempbans actifs dont l'expiration est dépassée, débannit côté Discord puis
marque la sanction comme terminée (expiration naturelle, PAS une révocation
staff — cf. utils.managers.mod_sanction_manager.mark_tempban_expired).
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands, tasks

from utils.managers.mod_sanction_manager import get_due_tempbans, mark_tempban_expired

log = logging.getLogger(__name__)

CHECK_INTERVAL_MINUTES = 5


class ModTempbanScheduler(commands.Cog):
    """Planificateur de levée des bannissements temporaires expirés."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_expired_tempbans.start()

    async def cog_unload(self) -> None:
        self.check_expired_tempbans.cancel()

    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_expired_tempbans(self) -> None:
        try:
            due = await get_due_tempbans()
        except Exception:
            log.exception("[MOD_TEMPBAN] Échec récupération des tempbans expirés")
            return

        for sanction in due:
            guild = self.bot.get_guild(sanction["guild_id"])
            if guild is None:
                log.warning(
                    "[MOD_TEMPBAN] Guild %s introuvable (bot absent) — sanction %s marquée expirée sans unban Discord",
                    sanction["guild_id"], sanction["id"],
                )
                await mark_tempban_expired(sanction["id"])
                continue

            try:
                await guild.unban(
                    discord.Object(id=sanction["user_id"]),
                    reason="Tempban expiré (levée automatique)",
                )
            except discord.NotFound:
                # Déjà débanni manuellement — on nettoie quand même la DB.
                pass
            except discord.Forbidden:
                log.warning(
                    "[MOD_TEMPBAN] Permission manquante pour débannir user=%s guild=%s",
                    sanction["user_id"], sanction["guild_id"],
                )
            except discord.HTTPException:
                log.exception(
                    "[MOD_TEMPBAN] Échec unban user=%s guild=%s", sanction["user_id"], sanction["guild_id"]
                )
                continue  # on retentera au prochain passage, sanction pas encore marquée expirée

            await mark_tempban_expired(sanction["id"])
            log.info(
                "[MOD_TEMPBAN] Tempban levé automatiquement user=%s guild=%s (sanction=%s)",
                sanction["user_id"], sanction["guild_id"], sanction["id"],
            )

    @check_expired_tempbans.before_loop
    async def _before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModTempbanScheduler(bot))
