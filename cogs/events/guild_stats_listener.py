"""
cogs/events/guild_stats_listener.py — Statistiques serveur pour le
dashboard GuideOn Iris (arrivées/départs/vocal/messages).

commands.Cog avec setup() → chargé automatiquement par
_load_cogs_from_directory (rglob récursif sur cogs/, cf. bot.py) — même
principe que cogs/events/exp_listener.py. Écoute des évènements bruts,
toujours actif : contrairement à l'EXP ou aux invitations, il n'y a pas
de config "enabled" par serveur ici — ces stats sont une donnée
d'infrastructure destinée au site (via une future route côté
cogs/api/*, lue depuis utils/managers/guild_stats_manager.py), pas une
fonctionnalité que les admins de serveur activent/désactivent.

  - on_member_join / on_member_remove : +1 arrivée / +1 départ (jour UTC)
  - on_message : +1 message pour (guild, membre, jour UTC)
  - on_voice_state_update : cumul du temps passé en vocal pour le
    serveur — même mécanique de session en mémoire que
    ExpListener._voice_sessions (cf. cogs/events/exp_listener.py) :
    join_timestamp par (guild, user), crédité au moment où le membre
    quitte totalement le vocal ; changer de salon vocal ne coupe pas la
    session. Comme pour l'EXP, une session en cours est perdue si le
    bot redémarre pendant qu'un membre est en vocal (limitation déjà
    acceptée côté EXP, pas une régression introduite ici).

Chaque écriture est isolée dans son propre try/except : un échec DB sur
un évènement ne doit jamais faire planter le listener ni bloquer les
autres cogs qui écoutent les mêmes évènements (bienvenue, invites, EXP...).
"""
from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from utils.managers.guild_stats_manager import (
    record_arrival,
    record_departure,
    record_message,
    record_voice_minutes,
)

log = logging.getLogger(__name__)


class GuildStatsListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Sessions vocales en cours → {guild_id: {user_id: join_timestamp}}
        self._voice_sessions: dict[int, dict[int, float]] = {}

    # ----------------------------------------------------
    # Arrivées / départs
    # ----------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        try:
            await record_arrival(member.guild.id)
        except Exception:
            log.exception(
                "[GUILD STATS] Échec enregistrement arrivée (guild=%s, user=%s)", member.guild.id, member.id,
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return
        try:
            await record_departure(member.guild.id)
        except Exception:
            log.exception(
                "[GUILD STATS] Échec enregistrement départ (guild=%s, user=%s)", member.guild.id, member.id,
            )

    # ----------------------------------------------------
    # Messages
    # ----------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        try:
            await record_message(message.guild.id, message.author.id)
        except Exception:
            log.exception(
                "[GUILD STATS] Échec enregistrement message (guild=%s, user=%s)",
                message.guild.id, message.author.id,
            )

    # ----------------------------------------------------
    # Vocal
    # ----------------------------------------------------
    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        if member.bot:
            return

        guild_id = member.guild.id
        user_id = member.id
        sessions = self._voice_sessions.setdefault(guild_id, {})

        # Début de session vocale.
        if before.channel is None and after.channel is not None:
            sessions[user_id] = time.monotonic()
            return

        # Fin de session vocale (changer de salon ne coupe pas la session).
        if before.channel is not None and after.channel is None:
            join_time = sessions.pop(user_id, None)
            if join_time is None:
                return

            elapsed_minutes = int((time.monotonic() - join_time) / 60)
            if elapsed_minutes <= 0:
                return

            try:
                await record_voice_minutes(guild_id, elapsed_minutes)
            except Exception:
                log.exception(
                    "[GUILD STATS] Échec enregistrement vocal (guild=%s, user=%s)", guild_id, user_id,
                )


# ----------------------------------------------------
# Setup du cog
# ----------------------------------------------------
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuildStatsListener(bot))