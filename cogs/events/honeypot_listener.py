"""
cogs/events/honeypot_listener.py — Système HoneyPot / "Piège" (/mod piege).

Écoute on_message : si un message est envoyé dans le salon-piège configuré
et actif pour ce serveur, le membre est automatiquement :
  1. Expulsé (kick) — via utils.managers.mod_sanction_manager.kick, qui
     alimente aussi /mod historique sans plomberie supplémentaire (décision
     explicite de Paul : pas de sanction/durée configurable, réaction fixe).
  2. Purgé — ses derniers messages dans le salon-piège sont supprimés
     (utils.managers.mod_clear_manager.clear_messages), pour garder le
     piège "propre" pour la prochaine victime.

Exemptions (rôles/membres ignorés, cf. utils.managers.honeypot_manager) :
volontairement PAS de bypass pour les comptes bot — un salon-piège sert
justement à détecter des comptes automatisés (RaidProtect : "This channel
is used to detect automated accounts"), donc un bot qui y poste n'est pas
mieux traité qu'un humain. Le SEUL bypass systématique est le bot lui-même
(son propre message d'avertissement posté à la création du salon ne doit
jamais se déclencher lui-même).
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.managers import honeypot_manager as hp_mgr
from utils.managers.mod_clear_manager import ClearError, clear_messages
from utils.managers.mod_sanction_manager import SanctionError, kick

log = logging.getLogger(__name__)

# Nombre de messages récents scannés (et purgés s'ils viennent du membre
# sanctionné) dans le salon-piège après un déclenchement — cf.
# utils.managers.mod_clear_manager.clear_messages (borné à 500 côté manager,
# 25 suffit largement ici : le salon-piège ne contient normalement QUE le
# message d'avertissement du bot + celui(ceux) du membre qui vient de se
# faire piéger).
_PURGE_SCAN_AMOUNT = 25

_KICK_REASON = "Message envoyé dans le salon-piège HoneyPot (détection automatique)."


class HoneypotListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        guild = message.guild
        if guild is None:
            return

        # Jamais s'auto-déclencher sur son propre message d'avertissement.
        if self.bot.user is not None and message.author.id == self.bot.user.id:
            return

        try:
            cfg = await hp_mgr.load_config(guild.id)
            if not cfg["enabled"] or not cfg["channel_id"]:
                return
            if message.channel.id != cfg["channel_id"]:
                return

            member = message.author
            if not isinstance(member, discord.Member):
                # Auteur qui a quitté entre l'envoi et le traitement de
                # l'event — plus rien à sanctionner.
                return

            if hp_mgr.is_ignored(cfg, member):
                log.info(
                    "[HONEYPOT] Déclenchement ignoré (exemption) guild=%s membre=%s",
                    guild.id, member.id,
                )
                return

            await self._trigger(guild, message.channel, member)
        except Exception:
            log.exception(
                "[HONEYPOT] Erreur traitement on_message guild=%s salon=%s auteur=%s",
                guild.id, message.channel.id, message.author.id,
            )

    async def _trigger(self, guild: discord.Guild, channel: discord.TextChannel, member: discord.Member) -> None:
        moderator_id = guild.me.id if guild.me is not None else (self.bot.user.id if self.bot.user else member.id)

        try:
            sanction = await kick(guild.id, member, moderator_id, _KICK_REASON, dm_sent=False)
            log.info(
                "[HONEYPOT] Membre expulsé guild=%s membre=%s sanction=%s",
                guild.id, member.id, sanction["id"],
            )
        except SanctionError as e:
            log.warning(
                "[HONEYPOT] Expulsion impossible guild=%s membre=%s erreur=%s",
                guild.id, member.id, e.message,
            )
        except Exception:
            log.exception("[HONEYPOT] Échec inattendu de l'expulsion guild=%s membre=%s", guild.id, member.id)

        try:
            deleted = await clear_messages(channel, _PURGE_SCAN_AMOUNT, author_filter=member)
            log.info(
                "[HONEYPOT] %s message(s) purgé(s) guild=%s salon=%s membre=%s",
                deleted, guild.id, channel.id, member.id,
            )
        except ClearError as e:
            log.warning(
                "[HONEYPOT] Purge impossible guild=%s salon=%s erreur=%s",
                guild.id, channel.id, e.message,
            )
        except Exception:
            log.exception("[HONEYPOT] Échec inattendu de la purge guild=%s salon=%s", guild.id, channel.id)


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HoneypotListener(bot))
