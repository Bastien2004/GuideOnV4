"""
Commande /wiki — Lien vers la documentation interne du bot.

Affiche un lien vers le site web wiki avec les principales sections.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.settings import settings
from utils.track_commande import tracker_commande


class Wiki(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="wiki",
        description="📚 Accéder à la documentation du bot",
    )
    @app_commands.checks.cooldown(1, 5)
    async def wiki(self, interaction: discord.Interaction) -> None:
        # 🔒 Vérif ban
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Maintenance
        if not await verifier_commande(interaction, "wiki"):
            return

        # 📊 Tracking
        await tracker_commande(interaction, "wiki")

        # 📚 Construction de la réponse
        try:
            embed = discord.Embed(
                title="📚 Documentation GuideON",
                description=(
                    "Toute la documentation du bot est disponible en ligne.\n"
                    "Tu y trouveras :\n\n"
                    "🎫 **Système de tickets**\n"
                    "🎁 **Giveaways**\n"
                    "🧩 **EXP & Niveaux**\n"
                    "🛡️ **Modération**\n"
                    "🌍 **NationsGlory**\n"
                    "⚙️ **Configuration**\n"
                    "🎂 **Anniversaire**\n"
                ),
                color=discord.Color.from_rgb(255, 181, 71),
            )
            embed.set_footer(text="GuideON Studio")

            # Bouton qui ouvre le wiki dans le navigateur
            view = View()
            view.add_item(
                Button(
                    label="Ouvrir le wiki",
                    emoji="🔗",
                    url=settings.website_url,
                    style=discord.ButtonStyle.link,
                )
            )

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                view=error_container(f"Erreur : `{e}`"),
                ephemeral=True,
            )

    @wiki.error
    async def wiki_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        await handle_app_command_error(interaction, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Wiki(bot))