"""
cogs/events/ngstaff_rolereact.py — Listener du système Rôle réaction NGSTAFF.
"""

from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands

from utils.managers.ng_role_react_manager import get_rr_entries
from utils.managers.ng_server_manager import get_server_by_guild

log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

CUSTOM_ID_PREFIX = "role_react_"
COOLDOWN_SECONDS = 5


# ============================================================
#  🧩 Class principale
# ============================================================

class NGSTAFF_RoleReactListener(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_click: dict[tuple[int, int], float] = {}

    @commands.Cog.listener("on_interaction")
    async def on_role_react_click(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return

        custom_id: str = interaction.data.get("custom_id", "")
        if not custom_id.startswith(CUSTOM_ID_PREFIX):
            return

        # Extraire le role_id
        try:
            role_id = int(custom_id[len(CUSTOM_ID_PREFIX):])
        except ValueError:
            return

        guild = interaction.guild
        if guild is None:
            return

        ng_server = get_server_by_guild(guild.id)
        if ng_server is None:
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            return

        key = (member.id, role_id)
        now = time.monotonic()
        last = self._last_click.get(key)

        if last is not None and (now - last) < COOLDOWN_SECONDS:
            remaining = COOLDOWN_SECONDS - (now - last)
            return await interaction.response.send_message(f"⏳ Doucement ! Réessaie dans {remaining:.1f}s.", ephemeral=True)
        self._last_click[key] = now

        # Vérifier que ce rôle est bien dans la liste configurée
        entries = await get_rr_entries(ng_server.name)
        entry = next((e for e in entries if e["role_id"] == role_id), None)
        if entry is None:
            return await interaction.response.send_message("Ce rôle n'est plus dans la liste des rôles disponibles", ephemeral=True)

        role = guild.get_role(role_id)
        if role is None:
            try:
                await interaction.response.send_message("Rôle introuvable sur le serveur. Contactez un membre du staff.", ephemeral=True)
            except discord.HTTPException:
                pass
            return

        # Toggle
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Rôle réaction NGSTAFF — retrait volontaire")
                emoji_str = f"{entry['emoji']} " if entry.get("emoji") else ""
                await interaction.response.send_message(
                    f"🔕 Le rôle **{emoji_str}{role.name}** a été **retiré**.",
                    ephemeral=True,
                )
            else:
                await member.add_roles(role, reason="Rôle réaction NGSTAFF — ajout volontaire")
                emoji_str = f"{entry['emoji']} " if entry.get("emoji") else ""
                await interaction.response.send_message(
                    f"🔔 Le rôle **{emoji_str}{role.name}** a été **attribué** !",
                    ephemeral=True,
                )

        except discord.Forbidden:
            await interaction.response.send_message("Je n'ai pas la permission de modifier vos rôles.", ephemeral=True)

        except discord.HTTPException as e:
            log.warning("[NGSTAFF ROLEREACT] Erreur Discord (HTTP) lors de la gestion du rôle | role_id=%d : %s", role_id, e)
            await interaction.response.send_message("Une **erreur Discord** est survenue. Réessayez dans un instant.", ephemeral=True)


# ============================================================
#  💻 Setup BOT
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NGSTAFF_RoleReactListener(bot))