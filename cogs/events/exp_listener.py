"""
cogs/events/exp_listener.py — Gain automatique d'EXP.

commands.Cog avec setup() → chargé automatiquement par _load_cogs_from_directory
(rglob récursif sur cogs/). Pas de pipeline de commande (verifier_commande /
tracker_commande) : ce sont des listeners d'évènements bruts, pas des
interactions slash.

  - on_message : +EXP par message (avec cooldown anti-spam en mémoire)
  - on_voice_state_update : +EXP proportionnel au temps passé en vocal
  - Notification de level-up (Components V2), désormais une annonce
    PERMANENTE dans un salon dédié configurable (cf. _notify_level_up) —
    plus le message éphémère de 8s dans le salon d'origine (2026-09, cf.
    docstring de views/exp/levelup_view.py pour le détail du changement)
  - Rôle boost configuré par serveur (bonus en pourcentage)

Repris de la V3, stockage migré en DB (utils.managers.exp_manager) : le
verrou asyncio par guild protégeant les mutations est maintenant interne
au manager (plus de utils/exp_lock.py séparé).
"""
from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from utils.managers.exp_manager import add_exp, load_exp_config, tier_name_for_level
from views.exp.levelup_view import build_levelup_view

log = logging.getLogger(__name__)

MESSAGE_COOLDOWN = 60  # Cooldown anti-spam (1 minute) entre deux gains par message.


class ExpListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Cooldowns par serveur → {guild_id: {user_id: timestamp}}
        self._cooldowns: dict[int, dict[int, float]] = {}

        # Sessions vocales → {guild_id: {user_id: join_timestamp}}
        self._voice_sessions: dict[int, dict[int, float]] = {}

    # ----------------------------------------------------
    # Vérification cooldown message
    # ----------------------------------------------------
    def _can_gain_exp(self, guild_id: int, user_id: int) -> bool:
        now = time.monotonic()
        guild_cd = self._cooldowns.setdefault(guild_id, {})
        last = guild_cd.get(user_id, 0.0)

        if now - last >= MESSAGE_COOLDOWN:
            guild_cd[user_id] = now
            return True
        return False

    # ----------------------------------------------------
    # Vérification rôle boost
    # ----------------------------------------------------
    def _has_boost_role(self, member: discord.Member, boost_role_id: int | None) -> bool:
        if not boost_role_id:
            return False
        return any(r.id == boost_role_id for r in member.roles)

    # ----------------------------------------------------
    # Notification de level-up (annonce permanente, salon dédié)
    # ----------------------------------------------------
    async def _notify_level_up(
        self, guild: discord.Guild, member: discord.Member, old_level: int, new_level: int, config: dict,
    ) -> None:
        """N'envoie RIEN par défaut : l'annonce est une option explicite
        (`levelup_announce_enabled`) qui ne fait quoi que ce soit que si un
        salon a en plus été configuré (`levelup_channel_id`) — cf.
        views/exp/config_view.py. Appelée aussi bien depuis on_message que
        depuis on_voice_state_update : un salon d'annonce dédié n'a
        d'intérêt que s'il centralise TOUTES les montées de niveau, pas
        seulement celles déclenchées par un message."""
        if not config.get("levelup_announce_enabled"):
            return

        channel_id = config.get("levelup_channel_id")
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            log.warning(
                "[EXP] Salon d'annonce de level-up introuvable/invalide (guild=%s, channel_id=%s)",
                guild.id, channel_id,
            )
            return

        tier = tier_name_for_level(new_level) or "Niveau"
        tier_changed = tier_name_for_level(old_level) != tier
        view = build_levelup_view(member, new_level, tier, tier_changed=tier_changed)

        try:
            await channel.send(view=view)
        except (discord.Forbidden, discord.HTTPException):
            log.warning(
                "[EXP] Annonce de level-up impossible (guild=%s, channel=%s)", guild.id, channel.id,
            )

    # ----------------------------------------------------
    # Gain d'EXP via message
    # ----------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        if not message.content.strip():
            return

        guild_id = message.guild.id
        user_id = message.author.id

        config = await load_exp_config(guild_id)
        if not config.get("enabled", False):
            return

        if not self._can_gain_exp(guild_id, user_id):
            return

        base_exp = config.get("exp_per_message", 10)
        boost_role_id = config.get("boost_role_id")
        boost_percent = config.get("boost_percent", 0)
        has_boost = self._has_boost_role(message.author, boost_role_id)

        try:
            result = await add_exp(
                guild_id, user_id, base_exp,
                has_boost_role=has_boost, boost_percent=boost_percent,
            )
        except Exception:
            log.exception("[EXP] Échec du gain d'EXP par message (guild=%s, user=%s)", guild_id, user_id)
            return

        if result.leveled_up:
            await self._notify_level_up(message.guild, message.author, result.old_level, result.new_level, config)

    # ----------------------------------------------------
    # Gain d'EXP via vocal
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

        # Fin de session vocale.
        if before.channel is not None and after.channel is None:
            join_time = sessions.pop(user_id, None)
            if join_time is None:
                return

            config = await load_exp_config(guild_id)
            if not config.get("enabled", False):
                return

            elapsed_minutes = int((time.monotonic() - join_time) / 60)
            if elapsed_minutes <= 0:
                return

            exp_per_minute = config.get("exp_per_voice_minute", 2)
            boost_role_id = config.get("boost_role_id")
            boost_percent = config.get("boost_percent", 0)
            has_boost = self._has_boost_role(member, boost_role_id)
            gained = elapsed_minutes * exp_per_minute

            try:
                result = await add_exp(
                    guild_id, user_id, gained,
                    has_boost_role=has_boost, boost_percent=boost_percent,
                )
            except Exception:
                log.exception("[EXP] Échec du gain d'EXP vocal (guild=%s, user=%s)", guild_id, user_id)
                return

            if result.leveled_up:
                await self._notify_level_up(member.guild, member, result.old_level, result.new_level, config)


# ----------------------------------------------------
# Setup du cog
# ----------------------------------------------------
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExpListener(bot))
