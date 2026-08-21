"""
cogs/events/mod_voice_log_listener.py — Logs vocaux imposés par un
modérateur : mise en sourdine serveur et déplacement de salon (pack
Chercheur, event_key "voice_mute" / "voice_move").

Écoute on_voice_state_update et ne logge QUE les changements imposés par
un tiers :
  - "voice_mute"  : bascule de VoiceState.mute (sourdine SERVEUR, imposée
    par un modérateur — distinct de self_mute qui est l'action volontaire
    du membre lui-même et n'est pas loggée ici). Ignoré si le membre vient
    tout juste de rejoindre le vocal (before.channel is None), pour éviter
    de confondre une connexion avec un état de sourdine préexistant.
  - "voice_move"  : before.channel et after.channel sont tous les deux
    définis et différents — un déplacement d'un salon à un autre, distinct
    d'un simple join/leave (déjà couverts par voice_join/voice_leave).

on_voice_state_update ne fournit jamais l'auteur de l'action : on va le
chercher dans l'audit log juste après l'évènement (member_update pour le
mute, member_move pour le déplacement), avec quelques tentatives espacées
car l'audit log Discord met parfois quelques centaines de ms à être
disponible après l'évènement gateway.
"""
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from utils.managers.mod_log_manager import send_log

log = logging.getLogger(__name__)

# Tentatives + délai entre 2 lectures d'audit log (latence de propagation).
_AUDIT_LOOKUP_ATTEMPTS = 3
_AUDIT_LOOKUP_DELAY = 0.6


# ============================================================
# 🧩 Cog
# ============================================================

class ModVoiceLogListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        guild = member.guild
        if guild is None or member.bot:
            return

        try:
            # 🔕 Sourdine serveur — uniquement si le membre était déjà
            # connecté (évite de confondre avec un join où l'état de
            # sourdine serait déjà présent dans `after`).
            if before.channel is not None and before.mute != after.mute:
                await self._log_mute(guild, member, muted=after.mute)

            # ↔️ Déplacement d'un salon vocal à un autre (pas join/leave).
            if (
                before.channel is not None
                and after.channel is not None
                and before.channel.id != after.channel.id
            ):
                await self._log_move(guild, member, before.channel, after.channel)
        except Exception:
            log.exception(
                "[MOD_LOG][VOICE] Erreur traitement voice_state_update guild=%s membre=%s",
                guild.id, member.id,
            )

    # ────────────────────────────────────────────────────────
    # 🔎 Résolution de l'auteur via l'audit log (avec retry)
    # ────────────────────────────────────────────────────────

    async def _find_moderator(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        *,
        match,
    ) -> discord.abc.User | None:
        """
        Cherche dans les dernières entrées d'audit log correspondant à
        `action` une entrée qui vérifie `match(entry) -> bool`, avec
        quelques tentatives espacées (l'audit log Discord n'est pas
        toujours immédiatement disponible juste après l'évènement).
        Retourne None si non trouvé, permission manquante, ou erreur API.
        """
        if guild.me is None or not guild.me.guild_permissions.view_audit_log:
            return None

        for attempt in range(_AUDIT_LOOKUP_ATTEMPTS):
            try:
                async for entry in guild.audit_logs(action=action, limit=5):
                    if match(entry):
                        return entry.user
            except (discord.Forbidden, discord.HTTPException) as exc:
                log.warning(
                    "[MOD_LOG][VOICE] Lecture audit log impossible guild=%s erreur=%s",
                    guild.id, exc,
                )
                return None
            if attempt < _AUDIT_LOOKUP_ATTEMPTS - 1:
                await asyncio.sleep(_AUDIT_LOOKUP_DELAY)
        return None

    # ────────────────────────────────────────────────────────
    # 🔕 Mute / unmute serveur
    # ────────────────────────────────────────────────────────

    async def _log_mute(self, guild: discord.Guild, member: discord.Member, *, muted: bool) -> None:
        moderator = await self._find_moderator(
            guild, discord.AuditLogAction.member_update,
            match=lambda e: (
                e.target is not None
                and e.target.id == member.id
                and getattr(e.after, "mute", None) == muted
            ),
        )
        moderator_display = moderator.mention if moderator else "`Modérateur inconnu`"
        action_label = "Mise en sourdine" if muted else "Sourdine retirée"

        fields = [
            ("Modérateur", moderator_display, True),
            ("Membre", member.mention, True),
            ("Action", action_label, True),
        ]
        if member.voice is not None and member.voice.channel is not None:
            fields.append(("Salon vocal", member.voice.channel.mention, False))

        await send_log(
            guild.id, "voice_mute", fields,
            thumbnail_url=member.display_avatar.url,
        )

    # ────────────────────────────────────────────────────────
    # ↔️ Déplacement de salon
    # ────────────────────────────────────────────────────────

    async def _log_move(
        self,
        guild: discord.Guild,
        member: discord.Member,
        before_channel: discord.abc.GuildChannel,
        after_channel: discord.abc.GuildChannel,
    ) -> None:
        moderator = await self._find_moderator(
            guild, discord.AuditLogAction.member_move,
            match=lambda e: (
                getattr(e.extra, "channel", None) is not None
                and e.extra.channel.id == after_channel.id
            ),
        )
        moderator_display = moderator.mention if moderator else "`Modérateur inconnu`"

        fields = [
            ("Modérateur", moderator_display, True),
            ("Membre", member.mention, True),
            ("Depuis", before_channel.mention, True),
            ("Vers", after_channel.mention, True),
        ]

        await send_log(
            guild.id, "voice_move", fields,
            thumbnail_url=member.display_avatar.url,
        )


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModVoiceLogListener(bot))