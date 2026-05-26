"""
cogs/events/reaction_role_listener.py — Attribution de rôles via réactions.

Écoute on_raw_reaction_add / on_raw_reaction_remove et applique/retire le rôle
associé à l'emoji sur un message rôle-réaction configuré (via /config role_reaction).

commands.Cog avec setup() → chargé automatiquement par _load_cogs_from_directory
(cohérent avec autorole_listener). Le lookup emoji→rôle passe par le manager (cache),
donc pas de requête DB à chaque réaction.

Anti-spam log : 1 log max par utilisateur et par seconde (repris de V3, en logging).
"""
from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from utils.managers.reaction_role_manager import obtenir_role_par_message_emoji

log = logging.getLogger(__name__)


class ReactionRoleListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_log: dict[int, float] = {}  # {user_id: timestamp}

    def _safe_log(self, user_id: int, message: str) -> None:
        """Log anti-spam : au plus 1 message par utilisateur et par seconde."""
        now = time.time()
        last = self._last_log.get(user_id, 0)
        if now - last < 1:
            return
        self._last_log[user_id] = now
        log.info(message)

    async def _resolve(self, payload: discord.RawReactionActionEvent):
        """Résout (guild, member, role) depuis un payload, ou None si non concerné."""
        if self.bot.user and payload.user_id == self.bot.user.id:
            return None
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        if guild is None:
            return None

        role_id = await obtenir_role_par_message_emoji(
            guild.id, payload.message_id, str(payload.emoji)
        )
        if not role_id:
            return None

        member = guild.get_member(payload.user_id)
        role = guild.get_role(role_id)
        if member is None or role is None or member.bot:
            return None
        return guild, member, role

    # ============================================================
    # ➕ Ajout de réaction → ajout de rôle
    # ============================================================
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        resolved = await self._resolve(payload)
        if resolved is None:
            return
        guild, member, role = resolved
        if role in member.roles:
            return
        try:
            await member.add_roles(role, reason="Rôle réaction")
            self._safe_log(member.id, f"RR: rôle '{role.name}' ajouté à {member} ({member.id})")
        except discord.Forbidden:
            self._safe_log(
                member.id,
                f"RR: permissions insuffisantes pour ajouter '{role.name}' à {member.id}",
            )
        except discord.HTTPException:
            log.exception("RR: échec ajout rôle %s à %s (guild=%s)", role.id, member.id, guild.id)

    # ============================================================
    # ➖ Retrait de réaction → retrait de rôle
    # ============================================================
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        resolved = await self._resolve(payload)
        if resolved is None:
            return
        guild, member, role = resolved
        if role not in member.roles:
            return
        try:
            await member.remove_roles(role, reason="Rôle réaction retiré")
            self._safe_log(member.id, f"RR: rôle '{role.name}' retiré de {member} ({member.id})")
        except discord.Forbidden:
            self._safe_log(
                member.id,
                f"RR: permissions insuffisantes pour retirer '{role.name}' à {member.id}",
            )
        except discord.HTTPException:
            log.exception("RR: échec retrait rôle %s de %s (guild=%s)", role.id, member.id, guild.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRoleListener(bot))