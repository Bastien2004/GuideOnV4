"""
Commande /id — Récupère l'ID Discord d'un élément.

Permet de demander l'ID d'un user, d'un rôle ou d'un salon.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container, info_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.track_commande import tracker_commande


class Id(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="id", description="🔢 Récupère l'ID d'un membre, rôle ou salon")
    @app_commands.describe(
        membre="Membre dont tu veux l'ID",
        role="Rôle dont tu veux l'ID",
        salon="Salon dont tu veux l'ID",
    )
    @app_commands.checks.cooldown(1, 3)
    async def id(
        self,
        interaction: discord.Interaction,
        membre: discord.Member | None = None,
        role: discord.Role | None = None,
        salon: discord.abc.GuildChannel | None = None,
    ) -> None:
        # 🔒 Vérif ban
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Maintenance
        if not await verifier_commande(interaction, "id"):
            return

        # 📊 Tracking
        await tracker_commande(interaction, "id")

        # 🧠 Construction de la réponse
        try:
            lignes = []

            if membre is None and role is None and salon is None:
                # Aucun paramètre → on renvoie l'ID de l'utilisateur appelant
                lignes.append(f"👤 **Toi** : `{interaction.user.id}`")
            else:
                if membre is not None:
                    lignes.append(f"👤 {membre.mention} → `{membre.id}`")
                if role is not None:
                    lignes.append(f"🎭 {role.mention} → `{role.id}`")
                if salon is not None:
                    lignes.append(f"📍 {salon.mention} → `{salon.id}`")

            await interaction.followup.send(
                view=info_container("\n".join(lignes)),
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(
                view=error_container(f"Erreur : `{e}`"),
                ephemeral=True,
            )

    @id.error
    async def id_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        await handle_app_command_error(interaction, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Id(bot))