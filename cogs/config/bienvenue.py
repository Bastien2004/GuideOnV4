"""
cogs/config/bienvenue.py — Commande /config bienvenue (V4).

Pipeline standard V4 :
    verifier_ban_utilisateur → defer → verifier_commande → tracker_commande

Différences vs V3 :
- Config en DB (bienvenue_manager) au lieu de JSON.
- Vue modulaire class-based (views/bienvenue/config_view.py).
- Groupe /config porté par le cog (app_commands.Group).
- Gestion d'erreur via utils.error_handler.

NB ordre du pipeline : on suit la convention V4 (ban → defer → verif → track).
La vérif admin se fait après le defer, sur réponse ephemeral.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.track_commande import tracker_commande
from views.bienvenue.config_view import BienvenueConfigView

log = logging.getLogger(__name__)


class ConfigBienvenue(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Groupe /config (porté par le cog). Si d'autres /config existent déjà,
    # discord.py fusionne les sous-commandes au sync tant qu'un seul cog
    # déclare le groupe parent ; sinon, factoriser ce groupe ailleurs.
    config_group = app_commands.Group(
        name="config",
        description="⚙️ Configuration des systèmes du serveur",
        guild_only=True,
    )

    @config_group.command(name="bienvenue", description="👋 Configure le système de bienvenue")
    @app_commands.checks.cooldown(1, 10)
    async def bienvenue(self, interaction: discord.Interaction) -> None:
        # 🔒 Ban global
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer (ephemeral) — la suite répond en followup
        await interaction.response.defer(ephemeral=True)

        # ⚙️ Maintenance
        if not await verifier_commande(interaction, "config_bienvenue"):
            return

        # 📊 Tracking
        await tracker_commande(interaction, "config_bienvenue")

        # 🔐 Admin requis
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            await interaction.followup.send(
                view=error_container(
                    "Vous devez être **Administrateur** pour configurer le système de bienvenue."
                ),
                ephemeral=True,
            )
            return

        # 🪟 Vue (charge la config DB)
        try:
            view = await BienvenueConfigView.create(
                guild_id=interaction.guild.id,
                author_id=interaction.user.id,
                bot=self.bot,
            )
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception:
            log.exception("Ouverture config bienvenue échouée (guild=%s)", interaction.guild.id)
            await interaction.followup.send(
                view=error_container(
                    "Impossible d'ouvrir la configuration. L'incident a été enregistré."
                ),
                ephemeral=True,
            )

    @bienvenue.error
    async def bienvenue_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await handle_app_command_error(interaction, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfigBienvenue(bot))