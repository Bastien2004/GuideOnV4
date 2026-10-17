"""
cogs/events/autorole_listener.py — Attribution automatique de rôles à l'arrivée.
"""

from __future__ import annotations

import logging
import discord
from discord.ext import commands

from utils.managers.autorole_manager import load_autorole_config

log = logging.getLogger(__name__)


# ============================================================
#  🧩 Class principale
# ============================================================

class AutoRoleListener(commands.Cog):
    """Attribution automatique de rôle."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Action à faire lorsqu'un membre rejoint le serveur."""

        if member.bot:
            return

        guild = member.guild
        cfg = await load_autorole_config(guild.id)

        if not cfg.get("auto_role_active"):
            return

        role_ids = [
            cfg[key] for key in ("role_id_1", "role_id_2", "role_id_3")
            if cfg.get(key)
        ]
        if not role_ids:
            return

        me = guild.me
        roles_to_add: list[discord.Role] = []

        for role_id in role_ids:
            role = guild.get_role(role_id)
            if role is None:
                log.warning("[AUTOROLE_LISTENER] Rôle %d introuvable (guild=%d)", role_id, guild.id)
                continue

            if me is not None and me.top_role <= role:
                log.warning("[AUTOROLE_LISTENER] Rôle %s (%d) inaccessible | Permissions inssufisante (guild=%d)", role.name, role_id, guild.id)
                continue

            roles_to_add.append(role)

        if not roles_to_add:
            return

        try:
            await member.add_roles(*roles_to_add, reason="AutoRôle — arrivée sur le serveur")
            log.info("[AUTOROLE_LISTENER] %d rôle(s) attribués à %s (%d) sur guild=%d : %s", len(roles_to_add), member.display_name, member.id, guild.id, [r.name for r in roles_to_add])

        except discord.Forbidden:
            log.warning("[AUTOROLE_LISTENER] Permission refusée pour attribuer les rôles à %d (guild=%d)", member.id, guild.id)

        except discord.HTTPException:
            log.exception("[AUTOROLE_LISTENER] Erreur HTTP lors de l'attribution des rôles à %d (guild=%d)", member.id, guild.id)


# ============================================================
#  💻 Setup BOT
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoRoleListener(bot))